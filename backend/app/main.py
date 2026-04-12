import asyncio
import logging
import time
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from sqlalchemy import inspect
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.api.v1.endpoints.interview_ws import router as ws_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.request_context import reset_request_id, set_request_id
from app.db.session import SessionLocal
from app.rag.indexer import rebuild_knowledge_base
from app.rag.vector_store import get_shared_milvus_store
from app.services.interview_service import InterviewService


settings = get_settings()
configure_logging()
access_logger = logging.getLogger("app.access")
worker_logger = logging.getLogger("app.history_report_worker")
startup_logger = logging.getLogger("app.startup")
HISTORY_REPORT_SCAN_INTERVAL_SECONDS = 30
HISTORY_REPORT_STARTUP_DELAY_SECONDS = 60
HISTORY_REPORT_BATCH_SIZE = 3


def process_pending_history_reports_once() -> None:
    db = SessionLocal()
    try:
        if not inspect(db.get_bind()).has_table("interview_sessions"):
            worker_logger.debug("history report worker waiting for interview tables to be initialized")
            return
        processed = InterviewService(db).process_pending_history_reports(limit=HISTORY_REPORT_BATCH_SIZE)
        if processed:
            worker_logger.info("history report worker processed pending sessions | count=%s", processed)
    except SQLAlchemyError as exc:
        db.rollback()
        worker_logger.warning("history report worker skipped because database is not ready yet | detail=%s", exc)
    except Exception:
        db.rollback()
        worker_logger.exception("history report worker failed")
    finally:
        db.close()


async def history_report_worker() -> None:
    await asyncio.sleep(HISTORY_REPORT_STARTUP_DELAY_SECONDS)
    while True:
        await asyncio.to_thread(process_pending_history_reports_once)
        await asyncio.sleep(HISTORY_REPORT_SCAN_INTERVAL_SECONDS)


def warm_runtime_dependencies_once() -> None:
    store = get_shared_milvus_store()
    try:
        store.initialize_runtime()
        startup_logger.info(
            "milvus runtime initialized | uri=%s collection=%s",
            settings.milvus_uri,
            settings.milvus_collection,
        )
    except RuntimeError as exc:
        if "collection not found" in str(exc).lower() and settings.embedding_ready:
            startup_logger.warning(
                "milvus collection missing at startup, rebuilding knowledge base | uri=%s collection=%s",
                settings.milvus_uri,
                settings.milvus_collection,
            )
            rebuild_knowledge_base(settings=settings, milvus_store=store)
            store.initialize_runtime()
            startup_logger.info(
                "milvus collection rebuilt and runtime initialized | uri=%s collection=%s",
                settings.milvus_uri,
                settings.milvus_collection,
            )
            return
        startup_logger.exception(
            "milvus runtime initialization failed | uri=%s collection=%s",
            settings.milvus_uri,
            settings.milvus_collection,
        )
    except Exception:
        startup_logger.exception(
            "milvus runtime initialization failed | uri=%s collection=%s",
            settings.milvus_uri,
            settings.milvus_collection,
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime_warmup_task = asyncio.create_task(asyncio.to_thread(warm_runtime_dependencies_once))
    worker_task = asyncio.create_task(history_report_worker())
    try:
        yield
    finally:
        runtime_warmup_task.cancel()
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await runtime_warmup_task
        with suppress(asyncio.CancelledError):
            await worker_task

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    openapi_url=f"{settings.api_prefix}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    # 每个请求都绑定唯一 request_id，后续排查时可以直接串联访问日志、业务日志和异常日志。
    request_id = request.headers.get("X-Request-ID") or uuid4().hex
    request.state.request_id = request_id
    token = set_request_id(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.exception(
            "request failed | method=%s path=%s status=%s client=%s duration_ms=%s",
            request.method,
            request.url.path,
            500,
            request.client.host if request.client else "unknown",
            duration_ms,
        )
        reset_request_id(token)
        raise

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    access_logger.info(
        "request completed | method=%s path=%s status=%s client=%s duration_ms=%s",
        request.method,
        request.url.path,
        response.status_code,
        request.client.host if request.client else "unknown",
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    reset_request_id(token)
    return response


register_exception_handlers(app)
app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(ws_router)  # WebSocket 端点（不带 API 前缀）

if settings.upload_dir.exists():
    app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running"}

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.request_context import get_request_id


logger = logging.getLogger(__name__)


class AppException(Exception):
    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _build_error_response(request: Request, status_code: int, message: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "") or get_request_id()
    return JSONResponse(
        status_code=status_code,
        headers={"X-Request-ID": request_id},
        content={"code": status_code, "message": message, "data": None, "request_id": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        logger.warning(
            "business exception | method=%s path=%s status=%s message=%s",
            request.method,
            request.url.path,
            exc.status_code,
            exc.message,
        )
        return _build_error_response(request, exc.status_code, exc.message)

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError) -> JSONResponse:
        logger.exception(
            "database integrity error | method=%s path=%s detail=%s",
            request.method,
            request.url.path,
            exc.orig,
        )
        return _build_error_response(request, status.HTTP_409_CONFLICT, "数据写入冲突，请检查输入后重试。")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unexpected exception | method=%s path=%s exc_type=%s",
            request.method,
            request.url.path,
            type(exc).__name__,
        )
        return _build_error_response(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "服务器内部错误，请查看日志排查。")
import logging
from logging.handlers import TimedRotatingFileHandler

from app.core.config import get_settings
from app.core.request_context import get_request_id


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


def _build_file_handler(path, level: int, formatter: logging.Formatter) -> TimedRotatingFileHandler:
    settings = get_settings()
    handler = TimedRotatingFileHandler(
        filename=str(path),
        when="midnight",
        interval=1,
        backupCount=settings.log_retention_days,
        encoding="utf-8",
        delay=True,
    )
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.addFilter(RequestContextFilter())
    return handler


def configure_logging() -> None:
    settings = get_settings()
    root_logger = logging.getLogger()
    if getattr(root_logger, "_interview_logging_configured", False):
        return

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    standard_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | request_id=%(request_id)s | %(message)s"
    )

    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(standard_formatter)
    console_handler.addFilter(RequestContextFilter())

    app_handler = _build_file_handler(settings.log_dir / "app.log", log_level, standard_formatter)
    error_handler = _build_file_handler(settings.log_dir / "error.log", logging.ERROR, standard_formatter)

    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(app_handler)
    root_logger.addHandler(error_handler)
    root_logger._interview_logging_configured = True  # type: ignore[attr-defined]

    access_logger = logging.getLogger("app.access")
    access_logger.handlers.clear()
    access_logger.setLevel(logging.INFO)
    access_logger.propagate = True
    access_logger.addHandler(_build_file_handler(settings.log_dir / "access.log", logging.INFO, standard_formatter))

    logging.getLogger("passlib").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.propagate = False
    uvicorn_access_logger.setLevel(logging.WARNING)
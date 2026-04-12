from pathlib import Path
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402


MYSQL_RETRY_ATTEMPTS = 30
MYSQL_RETRY_DELAY_SECONDS = 2


def run_with_mysql_retry(action, *, action_name: str):
    last_exc: OperationalError | None = None
    for attempt in range(1, MYSQL_RETRY_ATTEMPTS + 1):
        try:
            return action()
        except OperationalError as exc:
            last_exc = exc
            if attempt == MYSQL_RETRY_ATTEMPTS:
                break
            print(f"{action_name} waiting for mysql ({attempt}/{MYSQL_RETRY_ATTEMPTS}): {exc}")
            time.sleep(MYSQL_RETRY_DELAY_SECONDS)
    if last_exc is not None:
        raise last_exc


def ensure_database_exists() -> None:
    settings = get_settings()
    database_url = make_url(settings.effective_database_url)

    if not database_url.drivername.startswith("mysql"):
        return

    database_name = database_url.database or settings.mysql_db
    safe_database_name = database_name.replace("`", "``")
    admin_url = database_url.set(database="mysql")
    admin_engine = create_engine(admin_url, future=True, pool_pre_ping=True)

    try:
        def create_database() -> None:
            with admin_engine.connect() as conn:
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.execute(
                    text(
                        f"CREATE DATABASE IF NOT EXISTS `{safe_database_name}` "
                        "DEFAULT CHARACTER SET utf8mb4 "
                        "DEFAULT COLLATE utf8mb4_unicode_ci"
                    )
                )

        run_with_mysql_retry(create_database, action_name="create database")
    finally:
        admin_engine.dispose()


def init_database() -> None:
    ensure_database_exists()
    run_with_mysql_retry(lambda: Base.metadata.create_all(bind=engine), action_name="create tables")


if __name__ == "__main__":
    init_database()
    print("database and tables initialized")

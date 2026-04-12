from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GrowthSnapshot, SystemConfig


class SystemRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_config(self, key: str) -> SystemConfig | None:
        return self.db.scalar(select(SystemConfig).where(SystemConfig.key == key))

    def upsert_config(self, key: str, value: dict) -> SystemConfig:
        config = self.get_config(key)
        if config:
            config.value = value
            self.db.flush()
            return config

        config = SystemConfig(key=key, value=value)
        self.db.add(config)
        self.db.flush()
        return config

    def add_growth_snapshot(self, **kwargs) -> GrowthSnapshot:
        snapshot = GrowthSnapshot(**kwargs)
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

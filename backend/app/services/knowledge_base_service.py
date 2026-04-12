from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rag.corpus import SOURCE_SCOPE, load_static_corpus
from app.rag.indexer import ACTIVE_STORAGE_MODE, build_result_to_status_payload, rebuild_knowledge_base
from app.rag.vector_store import MilvusVectorStore
from app.repositories.system_repository import SystemRepository
from app.schemas.position import KnowledgeBaseStatus


class KnowledgeBaseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SystemRepository(db)
        self.settings = get_settings()

    def get_status(self) -> KnowledgeBaseStatus:
        config = self.repo.get_config("kb_status")
        value = config.value if config else {}
        corpus = load_static_corpus(settings=self.settings)
        return KnowledgeBaseStatus(
            collection_name=self.settings.milvus_collection,
            configured=bool(corpus.source_files),
            indexed_docs=int(value.get("indexed_docs", len(corpus.source_files))),
            collection_entities=self._collection_entities(value),
            latest_build_at=value.get("latest_build_at"),
            storage_mode=self._storage_mode(value),
            source_scope=list(value.get("source_scope", SOURCE_SCOPE)),
        )

    def rebuild(self) -> KnowledgeBaseStatus:
        result = rebuild_knowledge_base(settings=self.settings)
        self.repo.upsert_config("kb_status", build_result_to_status_payload(result))
        self.db.commit()
        return self.get_status()

    def _collection_entities(self, cached_value: dict) -> int:
        try:
            return MilvusVectorStore(settings=self.settings).count_entities()
        except Exception:
            return int(cached_value.get("collection_entities", 0))

    def _storage_mode(self, cached_value: dict) -> str:
        storage_mode = str(cached_value.get("storage_mode") or ACTIVE_STORAGE_MODE)
        if storage_mode == "milvus-primary+local-fallback":
            return ACTIVE_STORAGE_MODE
        return storage_mode

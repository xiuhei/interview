from __future__ import annotations

import logging
from threading import Lock

from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility

from app.ai.embeddings import EmbeddingClient, get_embedding_client
from app.core.config import Settings, get_settings
from app.rag.corpus import Chunk


logger = logging.getLogger(__name__)
_SHARED_STORE: "MilvusVectorStore | None" = None
_SHARED_STORE_LOCK = Lock()


class MilvusVectorStore:
    def __init__(self, settings: Settings | None = None, embedding_client: EmbeddingClient | None = None) -> None:
        self.settings = settings or get_settings()
        self._embedding_client = embedding_client
        self.connected = False
        self._connect_lock = Lock()
        self._collection_lock = Lock()
        self._collection: Collection | None = None
        self._collection_loaded = False

    def connect(self) -> None:
        if self.connected:
            return
        with self._connect_lock:
            if self.connected:
                return
            connections.connect(alias="default", uri=self.settings.milvus_uri, token=self.settings.milvus_token or None)
            self.connected = True

    def ensure_collection(self) -> Collection:
        self.connect()
        with self._collection_lock:
            if self._collection is not None:
                return self._collection
            if utility.has_collection(self.settings.milvus_collection):
                self._collection = Collection(self.settings.milvus_collection)
                self._collection_loaded = False
                return self._collection
            schema = CollectionSchema(
                fields=[
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=120, is_primary=True),
                    FieldSchema(name="role_code", dtype=DataType.VARCHAR, max_length=50),
                    FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50),
                    FieldSchema(name="competency_code", dtype=DataType.VARCHAR, max_length=80),
                    FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=200),
                    FieldSchema(name="source_path", dtype=DataType.VARCHAR, max_length=255),
                    FieldSchema(name="snippet", dtype=DataType.VARCHAR, max_length=4000),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.settings.embedding_dimension),
                ],
                description="Interview knowledge base chunks",
            )
            collection = Collection(self.settings.milvus_collection, schema=schema)
            collection.create_index("embedding", {"metric_type": "COSINE", "index_type": "AUTOINDEX"})
            self._collection = collection
            self._collection_loaded = False
            return collection

    def rebuild(self, chunks: list[Chunk]) -> Collection:
        self.connect()
        self._reset_runtime_state(disconnect=False)
        if utility.has_collection(self.settings.milvus_collection):
            utility.drop_collection(self.settings.milvus_collection)
        collection = self.ensure_collection()
        if chunks:
            collection.insert(
                [
                    [chunk.doc_id for chunk in chunks],
                    [chunk.role_code for chunk in chunks],
                    [chunk.doc_type for chunk in chunks],
                    [chunk.competency_code for chunk in chunks],
                    [chunk.title for chunk in chunks],
                    [chunk.source_path for chunk in chunks],
                    [chunk.snippet[:3900] for chunk in chunks],
                    [chunk.embedding for chunk in chunks],
                ]
            )
            collection.flush()
        return collection

    def count_entities(self) -> int:
        collection = self.load_collection()
        try:
            iterator = collection.query_iterator(batch_size=1000, expr='id != ""', output_fields=["id"])
        except Exception:
            return collection.num_entities

        count = 0
        try:
            while True:
                batch = iterator.next()
                if not batch:
                    break
                count += len(batch)
        finally:
            try:
                iterator.close()
            except Exception:
                logger.debug("failed to close milvus query iterator", exc_info=True)
        return count

    def search(
        self,
        query: str,
        role_code: str,
        top_k: int = 6,
        allowed_doc_types: list[str] | None = None,
    ) -> list[Chunk]:
        collection = self.load_collection()
        query_vector = self.embedding_client.embed([query])[0]
        try:
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                limit=top_k,
                output_fields=["id", "role_code", "doc_type", "competency_code", "title", "source_path", "snippet"],
                param={"metric_type": "COSINE", "params": {}},
                expr=self._build_search_expr(role_code=role_code, allowed_doc_types=allowed_doc_types),
            )
        except Exception:
            self._reset_runtime_state()
            raise
        hits = results[0] if results else []
        payload: list[Chunk] = []
        for hit in hits:
            payload.append(
                Chunk(
                    doc_id=str(_field_from_hit(hit, "id", hit.id)),
                    role_code=str(_field_from_hit(hit, "role_code", "common")),
                    doc_type=str(_field_from_hit(hit, "doc_type", "knowledge")),
                    competency_code=str(_field_from_hit(hit, "competency_code", "general")),
                    title=str(_field_from_hit(hit, "title", "")),
                    snippet=str(_field_from_hit(hit, "snippet", "")),
                    source_path=str(_field_from_hit(hit, "source_path", "")),
                    section="milvus",
                    embedding=None,
                    score=float(getattr(hit, "score", getattr(hit, "distance", 0.0)) or 0.0),
                )
            )
        return payload

    @property
    def embedding_client(self) -> EmbeddingClient:
        if self._embedding_client is None:
            self._embedding_client = get_embedding_client()
        return self._embedding_client

    def initialize_runtime(self) -> None:
        self.load_collection()

    def get_existing_collection(self) -> Collection:
        self.connect()
        with self._collection_lock:
            if self._collection is not None:
                return self._collection
            if not utility.has_collection(self.settings.milvus_collection):
                raise RuntimeError(f"Milvus collection not found: {self.settings.milvus_collection}")
            self._collection = Collection(self.settings.milvus_collection)
            self._collection_loaded = False
            return self._collection

    def load_collection(self) -> Collection:
        with self._collection_lock:
            if self._collection is not None and self._collection_loaded:
                return self._collection
        collection = self.get_existing_collection()
        try:
            with self._collection_lock:
                if self._collection is None:
                    self._collection = collection
                if self._collection_loaded:
                    return self._collection
                self._collection.load()
                self._collection_loaded = True
                return self._collection
        except Exception:
            self._reset_runtime_state()
            raise

    def _build_search_expr(self, role_code: str, allowed_doc_types: list[str] | None = None) -> str:
        role_expr = f'(role_code == "{role_code}" or role_code == "common")'
        normalized_doc_types = [str(item).strip() for item in (allowed_doc_types or []) if str(item).strip()]
        if not normalized_doc_types:
            return role_expr
        doc_type_expr = " or ".join(f'doc_type == "{item}"' for item in normalized_doc_types)
        return f"{role_expr} and ({doc_type_expr})"

    def _reset_runtime_state(self, disconnect: bool = True) -> None:
        with self._collection_lock:
            self._collection = None
            self._collection_loaded = False
        if disconnect and self.connected:
            try:
                connections.disconnect(alias="default")
            except Exception:
                logger.debug("failed to disconnect milvus alias", exc_info=True)
            self.connected = False


def get_shared_milvus_store() -> MilvusVectorStore:
    global _SHARED_STORE
    if _SHARED_STORE is not None:
        return _SHARED_STORE
    with _SHARED_STORE_LOCK:
        if _SHARED_STORE is None:
            _SHARED_STORE = MilvusVectorStore()
        return _SHARED_STORE


def _field_from_hit(hit, name: str, default):
    entity = getattr(hit, "entity", None)
    if entity is not None and hasattr(entity, "get"):
        value = entity.get(name)
        if value is not None:
            return value
    fields = getattr(hit, "fields", None)
    if isinstance(fields, dict) and name in fields:
        return fields[name]
    value = getattr(hit, name, None)
    if value is not None:
        return value
    return default

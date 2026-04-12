from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.ai.embeddings import EmbeddingClient, get_embedding_client
from app.core.config import ROOT_DIR, Settings, get_settings
from app.rag.corpus import SOURCE_SCOPE, Chunk, chunk_to_snapshot_record, load_static_corpus
from app.rag.vector_store import MilvusVectorStore


SNAPSHOT_PATH = ROOT_DIR / "data" / "build_artifacts" / "kb_chunks.jsonl"
ACTIVE_STORAGE_MODE = "milvus"


@dataclass
class KnowledgeBaseBuildResult:
    indexed_docs: int
    collection_entities: int
    latest_build_at: str
    storage_mode: str
    source_scope: list[str]
    duplicate_records: int
    embedded_chunks: int = 0
    embedding_calls: int = 0
    embedding_duration_seconds: float = 0.0
    milvus_write_duration_seconds: float = 0.0
    total_duration_seconds: float = 0.0


def build_result_to_status_payload(result: KnowledgeBaseBuildResult) -> dict:
    return {
        "indexed_docs": result.indexed_docs,
        "collection_entities": result.collection_entities,
        "latest_build_at": result.latest_build_at,
        "storage_mode": result.storage_mode,
        "source_scope": result.source_scope,
    }


def rebuild_knowledge_base(
    settings: Settings | None = None,
    embedding_client: EmbeddingClient | None = None,
    milvus_store: MilvusVectorStore | None = None,
    snapshot_path: Path | None = None,
    root_dir: Path | None = None,
) -> KnowledgeBaseBuildResult:
    started_at = time.perf_counter()
    settings = settings or get_settings()
    embedding_client = embedding_client or get_embedding_client()
    milvus_store = milvus_store or MilvusVectorStore()
    snapshot_path = snapshot_path or SNAPSHOT_PATH
    root_dir = root_dir or ROOT_DIR

    corpus = load_static_corpus(settings=settings, root_dir=root_dir)
    chunks, embedding_calls, embedding_duration_seconds = _embed_chunks(corpus.chunks, embedding_client)
    _write_snapshot(chunks, snapshot_path)
    milvus_started_at = time.perf_counter()
    milvus_store.rebuild(chunks)
    milvus_write_duration_seconds = time.perf_counter() - milvus_started_at
    collection_entities = milvus_store.count_entities()

    return KnowledgeBaseBuildResult(
        indexed_docs=len(corpus.source_files),
        collection_entities=collection_entities,
        latest_build_at=datetime.now(timezone.utc).isoformat(),
        storage_mode=ACTIVE_STORAGE_MODE,
        source_scope=list(SOURCE_SCOPE),
        duplicate_records=corpus.duplicate_records,
        embedded_chunks=len(chunks),
        embedding_calls=embedding_calls,
        embedding_duration_seconds=round(embedding_duration_seconds, 3),
        milvus_write_duration_seconds=round(milvus_write_duration_seconds, 3),
        total_duration_seconds=round(time.perf_counter() - started_at, 3),
    )


def _embed_chunks(chunks: list[Chunk], embedding_client: EmbeddingClient) -> tuple[list[Chunk], int, float]:
    if not chunks:
        return [], 0, 0.0
    started_at = time.perf_counter()
    embeddings = embedding_client.embed([chunk.snippet for chunk in chunks])
    for chunk, embedding in zip(chunks, embeddings):
        chunk.embedding = embedding
    return chunks, 1, time.perf_counter() - started_at


def _write_snapshot(chunks: list[Chunk], snapshot_path: Path) -> None:
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", encoding="utf-8-sig") as fh:
        for chunk in chunks:
            fh.write(json.dumps(chunk_to_snapshot_record(chunk), ensure_ascii=False) + "\n")

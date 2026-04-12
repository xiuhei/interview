from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.rag.corpus import Chunk, load_static_corpus
from app.rag.indexer import rebuild_knowledge_base
from app.rag.service import RetrievalService
from app.rag.vector_store import MilvusVectorStore
from app.services.knowledge_base_service import KnowledgeBaseService


class FakeEmbeddingClient:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1), float(index + 2)] for index, _ in enumerate(texts)]


class FakeMilvusStore:
    def __init__(self) -> None:
        self.rebuild_calls: list[list[str]] = []
        self._count = 0

    def rebuild(self, chunks: list[Chunk]) -> None:
        self.rebuild_calls.append([chunk.doc_id for chunk in chunks])
        self._count = len(chunks)

    def count_entities(self) -> int:
        return self._count


class RaisingMilvusStore:
    def search(self, query: str, role_code: str, top_k: int = 6, allowed_doc_types: list[str] | None = None) -> list[Chunk]:
        _ = query, role_code, top_k, allowed_doc_types
        raise RuntimeError("milvus unavailable")


class MissingCollectionThenSearchStore:
    def __init__(self) -> None:
        self.search_calls = 0
        self.allowed_doc_types_history: list[list[str] | None] = []

    def search(self, query: str, role_code: str, top_k: int = 6, allowed_doc_types: list[str] | None = None) -> list[Chunk]:
        _ = query, role_code, top_k
        self.search_calls += 1
        self.allowed_doc_types_history.append(allowed_doc_types)
        if self.search_calls == 1:
            raise RuntimeError("Milvus collection not found: interview_kb_chunks")
        return [
            Chunk(
                doc_id="doc-1",
                role_code=role_code,
                doc_type="knowledge",
                competency_code="system_design",
                title="system design",
                snippet="cache and rate limiting are core to high concurrency.",
                source_path="data/runtime_corpus/records.jsonl",
                section="milvus",
                score=0.91,
            )
        ]

    def count_entities(self) -> int:
        raise RuntimeError("Milvus collection not found: interview_kb_chunks")


class FakeEntity:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def get(self, key: str):
        return self.payload.get(key)


class FakeHit:
    def __init__(self, payload: dict, score: float) -> None:
        self.entity = FakeEntity(payload)
        self.id = payload["id"]
        self.score = score


class FakeCollection:
    def __init__(self, hits: list[FakeHit]) -> None:
        self.hits = hits
        self.load_called = False
        self.load_calls = 0

    def load(self) -> None:
        self.load_called = True
        self.load_calls += 1

    def search(self, **kwargs):
        _ = kwargs
        return [self.hits]


class FakeQueryIterator:
    def __init__(self, batches: list[list[dict]]) -> None:
        self.batches = list(batches)
        self.closed = False

    def next(self) -> list[dict]:
        if not self.batches:
            return []
        return self.batches.pop(0)

    def close(self) -> None:
        self.closed = True


class CountingCollection(FakeCollection):
    def __init__(self, hits: list[FakeHit], batches: list[list[dict]], num_entities: int = 0) -> None:
        super().__init__(hits)
        self._batches = batches
        self.num_entities = num_entities
        self.iterator: FakeQueryIterator | None = None

    def query_iterator(self, **kwargs):
        _ = kwargs
        self.iterator = FakeQueryIterator(self._batches)
        return self.iterator


class FakeConfig:
    def __init__(self, value: dict) -> None:
        self.value = value


class FakeRepo:
    def __init__(self, value: dict) -> None:
        self.value = value

    def get_config(self, key: str):
        _ = key
        return FakeConfig(self.value)


def test_load_static_corpus_collects_supported_sources_and_deduplicates_jsonl(tmp_path):
    data_dir = tmp_path / "data"
    records = data_dir / "runtime_corpus" / "records.jsonl"
    seeds = data_dir / "content_source" / "question_seeds" / "cpp_backend.json"
    logs = tmp_path / "var" / "logs" / "app.log"
    artifacts = data_dir / "build_artifacts" / "kb_chunks.jsonl"

    records.parent.mkdir(parents=True, exist_ok=True)
    seeds.parent.mkdir(parents=True, exist_ok=True)
    logs.parent.mkdir(parents=True, exist_ok=True)
    artifacts.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "id": "cpp_knowledge_001",
        "role_code": "cpp_backend",
        "doc_type": "knowledge",
        "source_type": "knowledge",
        "topic": "smart_pointer",
        "title": "smart_pointer",
        "content": "smart pointer content",
        "embedding_text": "smart pointer embedding text",
    }
    records.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
    seeds.write_text(
        json.dumps(
            {
                "opening": [{"competency_code": "project_depth", "question": "Describe a project with real ownership."}],
                "competencies": {"system_design": [{"question": "How do you handle a bottleneck in system design?"}]},
                "follow_up": {"deepen": "Please go deeper on {competency}."},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    logs.write_text("should be ignored", encoding="utf-8")
    artifacts.write_text("should be ignored", encoding="utf-8")

    corpus = load_static_corpus(settings=get_settings(), root_dir=tmp_path)

    assert corpus.duplicate_records == 0
    # 1 jsonl record + 3 question seed chunks (opening, competency, follow_up)
    assert len(corpus.chunks) == 4
    assert all("var/logs" not in source for source in corpus.source_files)
    assert all("data/build_artifacts" not in source for source in corpus.source_files)
    assert any(chunk.doc_type == "question_seed" for chunk in corpus.chunks)
    assert any(chunk.doc_type == "knowledge" for chunk in corpus.chunks)
    assert any(chunk.source_path == "data/runtime_corpus/records.jsonl" for chunk in corpus.chunks if chunk.doc_type == "knowledge")


def test_rebuild_knowledge_base_is_stable_across_rebuilds(tmp_path):
    data_dir = tmp_path / "data" / "runtime_corpus"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "records.jsonl").write_text(
        json.dumps(
            {
                "id": "doc-1",
                "role_code": "cpp_backend",
                "doc_type": "knowledge",
                "source_type": "knowledge",
                "topic": "threading",
                "title": "threading",
                "content": "threading content",
                "embedding_text": "threading embedding",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    snapshot = tmp_path / "snapshot.jsonl"
    store = FakeMilvusStore()

    first = rebuild_knowledge_base(
        settings=get_settings(),
        embedding_client=FakeEmbeddingClient(),
        milvus_store=store,
        snapshot_path=snapshot,
        root_dir=tmp_path,
    )
    second = rebuild_knowledge_base(
        settings=get_settings(),
        embedding_client=FakeEmbeddingClient(),
        milvus_store=store,
        snapshot_path=snapshot,
        root_dir=tmp_path,
    )

    assert first.collection_entities == second.collection_entities == 1
    assert first.indexed_docs == second.indexed_docs == 1
    assert len(store.rebuild_calls) == 2
    assert store.rebuild_calls[0] == store.rebuild_calls[1]
    assert len(snapshot.read_text(encoding="utf-8-sig").strip().splitlines()) == 1
    snapshot_item = json.loads(snapshot.read_text(encoding="utf-8-sig").strip())
    assert snapshot_item["embedding_dim"] == 2
    assert "embedding" not in snapshot_item
    assert len(snapshot_item["snippet"]) <= 200


def test_milvus_vector_store_search_maps_hits(monkeypatch):
    fake_collection = FakeCollection(
        [
            FakeHit(
                {
                    "id": "doc-1",
                    "role_code": "cpp_backend",
                    "doc_type": "knowledge",
                    "competency_code": "system_design",
                    "title": "system design",
                    "source_path": "data/runtime_corpus/records.jsonl",
                    "snippet": "cache and rate limiting are core to high concurrency.",
                },
                score=0.88,
            )
        ]
    )
    store = MilvusVectorStore(settings=get_settings(), embedding_client=FakeEmbeddingClient())
    monkeypatch.setattr(store, "get_existing_collection", lambda: fake_collection)

    results = store.search("design an api", "cpp_backend", top_k=3)

    assert fake_collection.load_called is True
    assert len(results) == 1
    assert results[0].doc_id == "doc-1"
    assert results[0].role_code == "cpp_backend"
    assert results[0].score == 0.88


def test_milvus_vector_store_loads_collection_once(monkeypatch):
    fake_collection = FakeCollection(
        [
            FakeHit(
                {
                    "id": "doc-1",
                    "role_code": "cpp_backend",
                    "doc_type": "knowledge",
                    "competency_code": "system_design",
                    "title": "system design",
                    "source_path": "data/runtime_corpus/records.jsonl",
                    "snippet": "cache and rate limiting are core to high concurrency.",
                },
                score=0.88,
            )
        ]
    )
    store = MilvusVectorStore(settings=get_settings(), embedding_client=FakeEmbeddingClient())
    monkeypatch.setattr(store, "get_existing_collection", lambda: fake_collection)

    store.search("design an api", "cpp_backend", top_k=3)
    store.search("design an api", "cpp_backend", top_k=3)

    assert fake_collection.load_calls == 1


def test_milvus_vector_store_count_entities_prefers_live_query_count(monkeypatch):
    fake_collection = CountingCollection([], [[{"id": "doc-1"}], [{"id": "doc-2"}, {"id": "doc-3"}]], num_entities=99)
    store = MilvusVectorStore(settings=get_settings(), embedding_client=FakeEmbeddingClient())
    monkeypatch.setattr(store, "load_collection", lambda: fake_collection)

    count = store.count_entities()

    assert count == 3
    assert fake_collection.iterator is not None
    assert fake_collection.iterator.closed is True


def test_retrieval_service_raises_when_milvus_unavailable():
    service = RetrievalService()
    service.milvus_store = RaisingMilvusStore()

    with pytest.raises(AppException) as excinfo:
        service.retrieve_with_meta("how do you verify project impact", "cpp_backend")

    assert excinfo.value.status_code == 503
    assert "Milvus" in excinfo.value.message
    assert "Embedding" in excinfo.value.message


def test_retrieval_service_rebuilds_missing_collection_once(monkeypatch):
    service = RetrievalService()
    service.milvus_store = MissingCollectionThenSearchStore()
    monkeypatch.setattr(service.settings, "qwen_api_key", "test-key")
    monkeypatch.setattr(service.settings, "allow_rebuild_on_request", True)

    rebuild_calls: list[str] = []

    def fake_rebuild_knowledge_base(*, settings, milvus_store, **kwargs):
        _ = settings, milvus_store, kwargs
        rebuild_calls.append("rebuilt")
        return None

    monkeypatch.setattr("app.rag.service.rebuild_knowledge_base", fake_rebuild_knowledge_base)

    trace = service.retrieve_with_meta("how do you verify project impact", "cpp_backend")

    assert trace.backend == "milvus"
    assert len(trace.evidence) == 1
    assert trace.evidence[0].doc_id == "doc-1"
    assert rebuild_calls == ["rebuilt"]
    assert service.milvus_store.search_calls == 2
    assert service.milvus_store.allowed_doc_types_history[-1] == ["question", "knowledge", "competency", "scoring"]


def test_retrieval_service_fails_fast_when_request_rebuild_disabled(monkeypatch):
    service = RetrievalService()
    service.milvus_store = MissingCollectionThenSearchStore()
    monkeypatch.setattr(service.settings, "allow_rebuild_on_request", False)

    with pytest.raises(AppException) as excinfo:
        service.retrieve_with_meta("how do you verify project impact", "cpp_backend")

    assert excinfo.value.status_code == 503
    assert "Milvus" in excinfo.value.message
    assert service.milvus_store.search_calls == 1


def test_retrieval_service_reports_missing_collection_precisely(monkeypatch):
    service = RetrievalService()
    service.milvus_store = MissingCollectionThenSearchStore()
    monkeypatch.setattr(service.settings, "allow_rebuild_on_request", False)

    with pytest.raises(AppException) as excinfo:
        service.retrieve_with_meta("how do you verify project impact", "cpp_backend")

    assert "collection" in excinfo.value.message.lower()
    assert service.settings.milvus_collection in excinfo.value.message


def test_retrieval_service_applies_question_generation_doc_type_profile():
    captured: dict = {}

    class CapturingStore:
        def search(self, query: str, role_code: str, top_k: int = 6, allowed_doc_types: list[str] | None = None) -> list[Chunk]:
            captured["query"] = query
            captured["role_code"] = role_code
            captured["top_k"] = top_k
            captured["allowed_doc_types"] = allowed_doc_types
            return []

    service = RetrievalService(milvus_store=CapturingStore())

    trace = service.retrieve_with_meta("design an api", "cpp_backend", profile_name="question_generation")

    assert trace.backend == "milvus"
    assert trace.evidence == []
    assert captured["role_code"] == "cpp_backend"
    assert captured["allowed_doc_types"] == ["question", "knowledge", "competency"]
    assert captured["top_k"] == 48


def test_retrieval_service_reranks_and_deduplicates_by_title(monkeypatch):
    class CapturingStore:
        def search(self, query: str, role_code: str, top_k: int = 6, allowed_doc_types: list[str] | None = None) -> list[Chunk]:
            _ = query, top_k, allowed_doc_types
            return [
                Chunk(
                    doc_id="dup-low",
                    role_code=role_code,
                    doc_type="question",
                    competency_code="project_depth",
                    title="请结合项目讲讲 尾延迟治理 的落地经验",
                    snippet="尾延迟治理 和 指标 验证",
                    source_path="data/runtime_corpus/records.jsonl",
                    section="1",
                    score=0.51,
                ),
                Chunk(
                    doc_id="knowledge-top",
                    role_code=role_code,
                    doc_type="knowledge",
                    competency_code="p99_latency",
                    title="尾延迟治理：机制解释",
                    snippet="尾延迟治理 主要关注 p99、p999 和长尾请求的控制。",
                    source_path="data/runtime_corpus/records.jsonl",
                    section="2",
                    score=0.49,
                ),
                Chunk(
                    doc_id="dup-high",
                    role_code=role_code,
                    doc_type="question",
                    competency_code="project_depth",
                    title="请结合项目讲讲 尾延迟治理 的落地经验",
                    snippet="尾延迟治理 指标 验证 压测",
                    source_path="data/runtime_corpus/records.jsonl",
                    section="3",
                    score=0.53,
                ),
            ]

    service = RetrievalService(milvus_store=CapturingStore())
    monkeypatch.setattr(
        "app.rag.service.load_static_corpus",
        lambda settings: type("Corpus", (), {"chunks": []})(),
    )

    trace = service.retrieve_with_meta(
        "cpp_backend performance 请解释 尾延迟治理 的核心概念，并说明它主要解决什么问题。",
        "cpp_backend",
        profile_name="question_generation",
    )

    assert [item.doc_id for item in trace.evidence] == ["dup-high", "knowledge-top"]


def test_retrieval_service_merges_lexical_candidates_for_question_generation(monkeypatch):
    class CapturingStore:
        def search(self, query: str, role_code: str, top_k: int = 6, allowed_doc_types: list[str] | None = None) -> list[Chunk]:
            _ = query, role_code, top_k, allowed_doc_types
            return [
                Chunk(
                    doc_id="vector-copy-control",
                    role_code="cpp_backend",
                    doc_type="question",
                    competency_code="cpp_language",
                    title="围绕 拷贝控制 设计一个可落地方案",
                    snippet="如果在项目里遇到和拷贝控制相关的问题，你会如何判断是否采用它，并如何验证效果？",
                    source_path="data/runtime_corpus/records.jsonl",
                    section="1",
                    score=0.64,
                )
            ]

    service = RetrievalService(milvus_store=CapturingStore())

    monkeypatch.setattr(
        "app.rag.service.load_static_corpus",
        lambda settings: type(
            "Corpus",
            (),
            {
                "chunks": [
                    Chunk(
                        doc_id="lexical-project-auth",
                        role_code="cpp_backend",
                        doc_type="question",
                        competency_code="project_depth",
                        title="如果 项目真实性 出问题，你会怎么排查？",
                        snippet="如果线上出现和 项目真实性 相关的故障，请给出排查顺序、证据来源和止血策略，并结合并发压测说明。",
                        source_path="data/runtime_corpus/records.jsonl",
                        section="2",
                        score=None,
                    )
                ]
            },
        )(),
    )

    trace = service.retrieve_with_meta("cpp 后端 项目 真实性 并发 压测", "cpp_backend", profile_name="question_generation")

    assert trace.evidence[0].doc_id == "lexical-project-auth"


def test_milvus_vector_store_build_search_expr_applies_doc_type_filter():
    store = MilvusVectorStore(settings=get_settings(), embedding_client=FakeEmbeddingClient())

    expr = store._build_search_expr("cpp_backend", ["knowledge", "competency"])

    assert 'role_code == "cpp_backend"' in expr
    assert 'role_code == "common"' in expr
    assert 'doc_type == "knowledge"' in expr
    assert 'doc_type == "competency"' in expr


def test_knowledge_base_status_exposes_runtime_fields(monkeypatch):
    service = object.__new__(KnowledgeBaseService)
    service.db = None
    service.settings = get_settings()
    service.repo = FakeRepo(
        {
            "indexed_docs": 12,
            "collection_entities": 34,
            "latest_build_at": "2026-03-23T00:00:00+00:00",
            "storage_mode": "milvus-primary+local-fallback",
            "source_scope": ["data/runtime_corpus/records.jsonl"],
        }
    )
    monkeypatch.setattr(
        "app.services.knowledge_base_service.load_static_corpus",
        lambda settings: type("Corpus", (), {"source_files": ["data/runtime_corpus/records.jsonl"]})(),
    )
    monkeypatch.setattr(
        "app.services.knowledge_base_service.MilvusVectorStore.count_entities",
        lambda self: 34,
    )

    status = service.get_status()

    assert status.collection_entities == 34
    assert status.storage_mode == "milvus"
    assert status.source_scope == ["data/runtime_corpus/records.jsonl"]

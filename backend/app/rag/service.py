import logging
from dataclasses import replace
from dataclasses import dataclass
from threading import Lock

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.rag.corpus import Chunk, load_static_corpus
from app.rag.indexer import rebuild_knowledge_base
from app.rag.vector_store import MilvusVectorStore, get_shared_milvus_store
from app.schemas.interview import RetrievalEvidence
from app.services.metadata_service import get_retrieval_profile
from app.utils.text import extract_keywords, keyword_hits


logger = logging.getLogger(__name__)
_REBUILD_LOCK = Lock()


@dataclass
class RetrievalTrace:
    evidence: list[RetrievalEvidence]
    backend: str


class RetrievalService:
    def __init__(self, milvus_store: MilvusVectorStore | None = None) -> None:
        self.settings = get_settings()
        self.milvus_store = milvus_store or get_shared_milvus_store()

    def retrieve_with_meta(self, query: str, role_code: str, profile_name: str = "default") -> RetrievalTrace:
        profile = get_retrieval_profile(profile_name) or get_retrieval_profile("default")
        try:
            chunks = self._search_chunks(query=query, role_code=role_code, profile=profile)
        except Exception as exc:
            logger.exception(
                "milvus retrieval failed | role_code=%s profile=%s query_preview=%s",
                role_code,
                profile_name,
                query[:120],
            )
            raise AppException(self._build_runtime_error_message(exc), 503) from exc

        payload = [
            RetrievalEvidence(
                doc_id=chunk.doc_id,
                role_code=chunk.role_code,
                doc_type=chunk.doc_type,
                competency_code=chunk.competency_code,
                title=chunk.title,
                snippet=chunk.snippet[:240],
                score=round(chunk.score if chunk.score is not None else 1.0 - (index * 0.1), 4),
            )
            for index, chunk in enumerate(chunks)
        ]
        logger.info(
            "retrieval completed | backend=%s role_code=%s profile=%s result_count=%s query_preview=%s",
            "milvus",
            role_code,
            profile_name,
            len(payload),
            query[:120],
        )
        return RetrievalTrace(evidence=payload, backend="milvus")

    def _search_chunks(self, query: str, role_code: str, profile: dict):
        top_k = int(profile.get("top_k") or self.settings.retrieval_top_k)
        allowed_doc_types = self._normalize_allowed_doc_types(profile.get("allowed_doc_types"))
        search_multiplier = max(int(profile.get("search_multiplier") or 3), 1)
        search_limit = max(top_k * search_multiplier, top_k)
        try:
            chunks = self.milvus_store.search(
                query=query,
                role_code=role_code,
                top_k=search_limit,
                allowed_doc_types=allowed_doc_types,
            )
        except RuntimeError as exc:
            if not self._should_attempt_rebuild(exc):
                raise
            if not self.settings.allow_rebuild_on_request:
                logger.warning(
                    "milvus collection missing during request and request rebuild is disabled | role_code=%s query_preview=%s",
                    role_code,
                    query[:120],
                )
                raise RuntimeError(
                    "Milvus collection not found and request-time rebuild is disabled."
                ) from exc
            self._rebuild_collection_for_search()
            chunks = self.milvus_store.search(
                query=query,
                role_code=role_code,
                top_k=search_limit,
                allowed_doc_types=allowed_doc_types,
            )
        chunks = self._merge_chunk_candidates(
            chunks,
            self._lexical_candidates(
                query=query,
                role_code=role_code,
                allowed_doc_types=allowed_doc_types,
                limit=int(profile.get("lexical_candidate_limit") or 0),
            ),
        )
        return self._rerank_chunks(query=query, chunks=chunks, top_k=top_k, profile=profile)

    def _normalize_allowed_doc_types(self, payload) -> list[str] | None:
        if not isinstance(payload, list):
            return None
        values = [str(item).strip() for item in payload if str(item).strip()]
        return values or None

    def _rerank_chunks(self, query: str, chunks: list[Chunk], top_k: int, profile: dict) -> list[Chunk]:
        if not chunks:
            return []
        query_keywords = extract_keywords(query)[:16]
        doc_type_boost = self._normalize_doc_type_boost(profile.get("doc_type_boost"))
        ranked = sorted(
            chunks,
            key=lambda chunk: (
                -self._chunk_rank_score(chunk, query_keywords, doc_type_boost),
                -float(chunk.score or 0.0),
                chunk.title,
            ),
        )

        deduped: list[Chunk] = []
        seen_keys: set[tuple[str, str]] = set()
        for chunk in ranked:
            dedupe_key = (chunk.doc_type.strip().lower(), chunk.title.strip().lower())
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)
            deduped.append(chunk)
            if len(deduped) >= top_k:
                break
        return deduped

    def _lexical_candidates(
        self,
        query: str,
        role_code: str,
        allowed_doc_types: list[str] | None,
        limit: int,
    ) -> list[Chunk]:
        if limit <= 0:
            return []
        query_keywords = extract_keywords(query)[:16]
        if not query_keywords:
            return []

        unique_keywords = list(dict.fromkeys(query_keywords))
        min_hits = 2 if len(unique_keywords) >= 3 else 1
        corpus = load_static_corpus(settings=self.settings)
        candidates: list[tuple[float, int, Chunk]] = []

        for chunk in corpus.chunks:
            if chunk.role_code not in {role_code, "common"}:
                continue
            if allowed_doc_types and chunk.doc_type not in allowed_doc_types:
                continue
            text = f"{chunk.title}\n{chunk.snippet[:800]}"
            hits = keyword_hits(text, unique_keywords)
            if hits < min_hits:
                continue
            coverage = hits / max(len(unique_keywords), 1)
            lexical_score = round(0.35 + min(coverage, 1.0) * 0.5, 4)
            candidates.append((coverage, hits, replace(chunk, score=lexical_score)))

        candidates.sort(key=lambda item: (-item[0], -item[1], item[2].title))
        return [item[2] for item in candidates[:limit]]

    def _merge_chunk_candidates(self, primary: list[Chunk], secondary: list[Chunk]) -> list[Chunk]:
        if not secondary:
            return primary
        merged: dict[str, Chunk] = {}
        for chunk in [*primary, *secondary]:
            existing = merged.get(chunk.doc_id)
            if existing is None or float(chunk.score or 0.0) > float(existing.score or 0.0):
                merged[chunk.doc_id] = chunk
        return list(merged.values())

    def _chunk_rank_score(self, chunk: Chunk, query_keywords: list[str], doc_type_boost: dict[str, float]) -> float:
        base_score = float(chunk.score or 0.0)
        text = f"{chunk.title}\n{chunk.snippet[:400]}"
        keyword_overlap = keyword_hits(text, query_keywords)
        type_boost = doc_type_boost.get(chunk.doc_type.strip().lower(), 0.0)
        return base_score + (keyword_overlap * 0.08) + (type_boost * 0.12)

    def _normalize_doc_type_boost(self, payload) -> dict[str, float]:
        if not isinstance(payload, dict):
            return {}
        boosts: dict[str, float] = {}
        for key, value in payload.items():
            normalized_key = str(key).strip().lower()
            if not normalized_key:
                continue
            if isinstance(value, (int, float)):
                boosts[normalized_key] = float(value)
        return boosts

    def _should_attempt_rebuild(self, exc: RuntimeError) -> bool:
        return "collection not found" in str(exc).lower()

    def _build_runtime_error_message(self, exc: Exception) -> str:
        message = str(exc)
        lowered = message.lower()

        if "collection not found" in lowered:
            return (
                "Milvus collection 缺失："
                f"{self.settings.milvus_collection}。"
                "请先重建知识库，再重新开始面试。"
            )
        if "embedding" in lowered:
            return (
                "Embedding 配置不可用。"
                "请检查 QWEN_API_KEY、QWEN_EMBEDDING_MODEL 和向量维度配置。"
            )
        if "failed to connect" in lowered or "connect" in lowered or "channel" in lowered:
            return (
                "Milvus 服务不可达。"
                f"当前地址为 {self.settings.milvus_uri}，请检查容器状态和网络连通性。"
            )
        return (
            "向量知识库当前不可用。"
            "请检查 Milvus 服务、collection 和 Embedding 配置后重试。"
            f"({type(exc).__name__})"
        )

    def _rebuild_collection_for_search(self) -> None:
        if not self.settings.embedding_ready:
            raise RuntimeError(
                "Milvus collection not found and embedding client is not configured for automatic rebuild."
            )

        with _REBUILD_LOCK:
            try:
                self.milvus_store.count_entities()
                return
            except Exception:
                logger.warning(
                    "milvus collection missing during retrieval, attempting automatic rebuild | collection=%s",
                    self.settings.milvus_collection,
                )

            rebuild_knowledge_base(settings=self.settings, milvus_store=self.milvus_store)
            logger.info(
                "automatic knowledge base rebuild completed | collection=%s",
                self.settings.milvus_collection,
            )

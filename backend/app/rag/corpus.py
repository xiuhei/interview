from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.core.config import ROOT_DIR, Settings, get_settings


SOURCE_SCOPE = [
    "data/runtime_corpus/records.jsonl",
    "data/content_source/question_seeds/*.json",
]


@dataclass
class Chunk:
    doc_id: str
    role_code: str
    doc_type: str
    competency_code: str
    title: str
    snippet: str
    source_path: str
    section: str
    embedding: list[float] | None = None
    score: float | None = None


@dataclass
class CorpusLoadResult:
    chunks: list[Chunk]
    source_files: list[str]
    duplicate_records: int


def discover_static_source_files(
    settings: Settings | None = None,
    root_dir: Path | None = None,
) -> list[Path]:
    """Return the canonical corpus inputs.

    Single source of truth after the data refactor:
      - data/runtime_corpus/records.jsonl  (the only JSONL the indexer reads)
      - data/content_source/question_seeds/*.json
    """
    _ = settings  # kept for interface compatibility
    root_dir = root_dir or ROOT_DIR
    data_dir = root_dir / "data"

    candidates: list[Path] = []
    records_path = data_dir / "runtime_corpus" / "records.jsonl"
    if records_path.is_file():
        candidates.append(records_path)

    seeds_dir = data_dir / "content_source" / "question_seeds"
    if seeds_dir.is_dir():
        candidates.extend(sorted(seeds_dir.glob("*.json")))

    return sorted(
        {path for path in candidates if path.is_file()},
        key=lambda path: (_source_priority(path, root_dir), path.relative_to(root_dir).as_posix()),
    )


def load_static_corpus(
    settings: Settings | None = None,
    root_dir: Path | None = None,
) -> CorpusLoadResult:
    settings = settings or get_settings()
    root_dir = root_dir or ROOT_DIR
    chunks: list[Chunk] = []

    source_files = discover_static_source_files(settings=settings, root_dir=root_dir)
    for path in source_files:
        if path.suffix == ".jsonl":
            chunks.extend(_load_jsonl_chunks(path, root_dir))
            continue
        if path.suffix == ".json":
            chunks.extend(_load_question_seed_chunks(path, root_dir))
            continue

    return CorpusLoadResult(
        chunks=chunks,
        source_files=[path.relative_to(root_dir).as_posix() for path in source_files],
        duplicate_records=0,
    )


def chunk_to_snapshot_record(chunk: Chunk) -> dict:
    return {
        "id": chunk.doc_id,
        "role_code": chunk.role_code,
        "doc_type": chunk.doc_type,
        "competency_code": chunk.competency_code,
        "title": chunk.title,
        "section": chunk.section,
        "source_path": chunk.source_path,
        "snippet": chunk.snippet[:200],
        "embedding_dim": len(chunk.embedding or []),
    }


def _source_priority(path: Path, root_dir: Path) -> int:
    relative = path.relative_to(root_dir).as_posix()
    if relative == "data/runtime_corpus/records.jsonl":
        return 0
    if relative.startswith("data/runtime_corpus/"):
        return 1
    return 2


def _load_jsonl_chunks(path: Path, root_dir: Path) -> list[Chunk]:
    relative_path = path.relative_to(root_dir).as_posix()
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8-sig") as fh:
        for line_no, line in enumerate(fh, start=1):
            payload = line.strip()
            if not payload:
                continue
            try:
                item = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON in {relative_path} at line {line_no}: {exc.msg}"
                ) from exc
            record_id = str(item.get("id") or item.get("source_id") or _stable_id(relative_path, str(line_no), payload))
            snippet = str(item.get("embedding_text") or item.get("content") or "").strip()
            if not snippet:
                continue
            title = str(item.get("title") or item.get("keyword") or record_id).strip()
            chunks.append(
                Chunk(
                    doc_id=record_id,
                    role_code=str(item.get("role_code") or "common").strip() or "common",
                    doc_type=str(item.get("doc_type") or "knowledge").strip() or "knowledge",
                    competency_code=str(item.get("topic") or item.get("source_type") or item.get("doc_type") or "general").strip() or "general",
                    title=title[:200],
                    snippet=snippet[:3900],
                    source_path=str(item.get("source_path") or relative_path).strip() or relative_path,
                    section=str(line_no),
                )
            )
    return chunks


def _load_question_seed_chunks(path: Path, root_dir: Path) -> list[Chunk]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    relative_path = path.relative_to(root_dir).as_posix()
    role_code = path.stem
    chunks: list[Chunk] = []

    for index, item in enumerate(payload.get("opening", []), start=1):
        question = str(item.get("question") or "").strip()
        competency = str(item.get("competency_code") or "opening").strip() or "opening"
        if not question:
            continue
        chunks.append(
            Chunk(
                doc_id=_stable_id(relative_path, "opening", str(index), question),
                role_code=role_code,
                doc_type="question_seed",
                competency_code=competency,
                title=f"opening::{competency}::{index}",
                snippet=_question_seed_snippet(role_code, competency, "opening", question),
                source_path=relative_path,
                section=f"opening:{index}",
            )
        )

    competencies = payload.get("competencies", {})
    if isinstance(competencies, dict):
        for competency_code, items in competencies.items():
            for index, item in enumerate(items or [], start=1):
                question = str(item.get("question") or "").strip()
                if not question:
                    continue
                chunks.append(
                    Chunk(
                        doc_id=_stable_id(relative_path, "competency", competency_code, str(index), question),
                        role_code=role_code,
                        doc_type="question_seed",
                        competency_code=str(competency_code).strip() or "general",
                        title=f"competency::{competency_code}::{index}",
                        snippet=_question_seed_snippet(role_code, str(competency_code), "competency", question),
                        source_path=relative_path,
                        section=f"competency:{competency_code}:{index}",
                    )
                )

    follow_up = payload.get("follow_up", {})
    if isinstance(follow_up, dict):
        for follow_up_type, template in follow_up.items():
            text = str(template or "").strip()
            if not text:
                continue
            chunks.append(
                Chunk(
                    doc_id=_stable_id(relative_path, "follow_up", str(follow_up_type), text),
                    role_code=role_code,
                    doc_type="question_seed",
                    competency_code=str(follow_up_type).strip() or "follow_up",
                    title=f"follow_up::{follow_up_type}",
                    snippet=_question_seed_snippet(role_code, str(follow_up_type), "follow_up", text),
                    source_path=relative_path,
                    section=f"follow_up:{follow_up_type}",
                )
            )

    return chunks


def _question_seed_snippet(role_code: str, competency_code: str, seed_type: str, text: str) -> str:
    return (
        f"role: {role_code}\n"
        f"competency: {competency_code}\n"
        f"seed_type: {seed_type}\n"
        f"text: {text}"
    )[:3900]


def _stable_id(*parts: str) -> str:
    digest = hashlib.sha1("::".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"chunk-{digest}"

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from check_corpus_quality import build_duplicate_report
from generate_demo_rag_data import build_record


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.corpus import Chunk, _load_question_seed_chunks, chunk_to_snapshot_record

DATA_DIR = ROOT / "data"
CONTENT_SOURCE_DIR = DATA_DIR / "content_source"
RUNTIME_DIR = DATA_DIR / "runtime_corpus"
ARTIFACTS_DIR = DATA_DIR / "build_artifacts"
SCHEMA_DIR = DATA_DIR / "schemas"
METADATA_DIR = DATA_DIR / "metadata"
RECORDS_PATH = RUNTIME_DIR / "records.jsonl"
MANIFEST_PATH = RUNTIME_DIR / "manifest.json"
BUILD_REPORT_PATH = ARTIFACTS_DIR / "build_report.json"
DUPLICATE_REPORT_PATH = ARTIFACTS_DIR / "duplicate_report.json"
SNAPSHOT_PATH = ARTIFACTS_DIR / "kb_chunks.jsonl"
QUALITY_THRESHOLD = 0.85


class BuildError(RuntimeError):
    pass


@dataclass
class ParsedMarkdown:
    path: Path
    meta: dict
    title: str
    sections: list[tuple[str, str | list[str]]]

    @property
    def section_map(self) -> dict:
        return {
            heading.lower().replace(" ", "_"): body
            for heading, body in self.sections
        }


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def dump_json(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def dump_jsonl(items: list[dict]) -> str:
    return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)


def load_validator(filename: str) -> Draft202012Validator:
    return Draft202012Validator(load_json(SCHEMA_DIR / filename))


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def parse_markdown(path: Path) -> ParsedMarkdown:
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        raise BuildError(f"{rel(path)} missing YAML front matter")

    lines = text.splitlines()
    if len(lines) < 3:
        raise BuildError(f"{rel(path)} is not a valid markdown source document")

    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise BuildError(f"{rel(path)} front matter is not closed")

    front_matter = "\n".join(lines[1:end_index])
    meta = yaml.safe_load(front_matter) or {}
    if not isinstance(meta, dict):
        raise BuildError(f"{rel(path)} front matter must be a mapping")

    body_lines = lines[end_index + 1:]
    title = ""
    sections: list[tuple[str, str | list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush_section() -> None:
        nonlocal current_heading, current_lines
        if current_heading is None:
            return
        normalized = [line.rstrip() for line in current_lines]
        while normalized and not normalized[0].strip():
            normalized.pop(0)
        while normalized and not normalized[-1].strip():
            normalized.pop()
        if normalized and all(line.strip().startswith("- ") for line in normalized if line.strip()):
            body: str | list[str] = [line.strip()[2:].strip() for line in normalized if line.strip()]
        else:
            body = "\n".join(normalized).strip()
        sections.append((current_heading, body))
        current_heading = None
        current_lines = []

    for raw_line in body_lines:
        line = raw_line.rstrip("\n")
        if not title and line.startswith("# "):
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush_section()
            current_heading = line[3:].strip()
            current_lines = []
            continue
        if current_heading is not None:
            current_lines.append(line)

    flush_section()

    if not title:
        raise BuildError(f"{rel(path)} missing title")
    if not sections:
        raise BuildError(f"{rel(path)} missing structured sections")

    return ParsedMarkdown(path=path, meta=meta, title=title, sections=sections)


def discover_source_files() -> list[Path]:
    files: list[Path] = []
    for scope in ("roles", "common"):
        root = CONTENT_SOURCE_DIR / scope
        if root.is_dir():
            files.extend(sorted(root.rglob("*.md")))
    return files


def discover_question_seed_files() -> list[Path]:
    seed_dir = CONTENT_SOURCE_DIR / "question_seeds"
    if not seed_dir.is_dir():
        return []
    return sorted(seed_dir.glob("*.json"))


def build_source_payload(document: ParsedMarkdown) -> dict:
    payload = dict(document.meta)
    payload["title"] = document.title
    payload["sections"] = document.section_map
    return payload


def validate_with_schema(validator: Draft202012Validator, payload: dict, path: Path) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(item) for item in first.absolute_path) or "$"
    raise BuildError(f"{rel(path)} schema validation failed at {location}: {first.message}")


def infer_competency_code(role_map: dict[str, dict], role_code: str, meta: dict) -> str:
    for key in ("competency_code", "source_type"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value

    competencies = role_map.get(role_code, {}).get("competencies") or {}
    tags = meta.get("tags") or []
    for item in tags:
        if str(item) in competencies:
            return str(item)

    if role_code == "common":
        return str(meta.get("subcategory") or meta.get("category") or "common").strip() or "common"
    return str(meta.get("category") or "general").strip() or "general"


def resolve_topic(meta: dict, path: Path) -> str:
    for key in ("subcategory", "case_type", "weakness_type", "category"):
        value = str(meta.get(key) or "").strip()
        if value:
            return value
    return path.stem


def resolve_difficulty(doc_type: str, meta: dict) -> str:
    if doc_type in {"question", "scoring"}:
        return str(meta.get("difficulty") or "mixed").strip() or "mixed"
    if doc_type in {"knowledge", "competency"}:
        return str(meta.get("level") or "mixed").strip() or "mixed"
    if doc_type == "resume":
        return str(meta.get("level") or "mixed").strip() or "mixed"
    if doc_type == "growth":
        return str(meta.get("target_level") or "mixed").strip() or "mixed"
    return "mixed"


def build_parsed_meta(document: ParsedMarkdown, source_type: str) -> dict:
    doc_type = str(document.meta.get("doc_type") or "").strip()
    role = str(document.meta.get("role") or "").strip()
    sections = document.section_map
    if doc_type == "question":
        return {
            "题目": str(sections.get("question") or document.title),
            "岗位": role,
            "题型": str(document.meta.get("category") or ""),
            "知识点": str(document.meta.get("subcategory") or document.title),
        }
    if doc_type == "knowledge":
        return {
            "题目": str(sections.get("question") or document.title),
            "岗位": role,
            "知识域": str(document.meta.get("category") or ""),
        }
    if doc_type == "competency":
        payload = {"岗位": role}
        if document.meta.get("level"):
            payload["能力层级"] = str(document.meta.get("level"))
        if document.meta.get("subcategory"):
            payload["能力维度"] = str(document.meta.get("subcategory"))
        payload["文档"] = document.title
        return payload
    if doc_type == "resume":
        return {"岗位": role, "案例类型": str(document.meta.get("case_type") or source_type)}
    if doc_type == "growth":
        return {"岗位": role, "成长类型": str(document.meta.get("weakness_type") or source_type)}
    return {"岗位": role, "文档": document.title}


def build_extra_metadata(document: ParsedMarkdown, source_type: str) -> dict:
    meta = document.meta
    payload = {}
    for key in ("category", "subcategory", "case_type", "weakness_type", "level", "target_level"):
        value = meta.get(key)
        if value is not None:
            payload[key] = value
    if document.meta.get("doc_type") == "question":
        payload["competency_code"] = source_type
    return payload


def validate_tags(meta: dict, allowed_tags: set[str], path: Path) -> None:
    tags = meta.get("tags") or []
    invalid = [str(item) for item in tags if str(item) not in allowed_tags]
    if invalid:
        raise BuildError(f"{rel(path)} has unsupported tags: {', '.join(invalid)}")


def validate_difficulty(meta: dict, path: Path, question_levels: set[str], knowledge_levels: set[str]) -> None:
    doc_type = str(meta.get("doc_type") or "").strip()
    if doc_type == "question":
        difficulty = str(meta.get("difficulty") or "").strip()
        if difficulty not in question_levels:
            raise BuildError(f"{rel(path)} has unsupported question difficulty: {difficulty}")
    if doc_type == "knowledge":
        level = str(meta.get("level") or "").strip()
        if level not in knowledge_levels:
            raise BuildError(f"{rel(path)} has unsupported knowledge level: {level}")


def build_runtime_records(
    role_map: dict[str, dict],
    allowed_tags: set[str],
    question_levels: set[str],
    knowledge_levels: set[str],
) -> tuple[list[dict], int]:
    validators = {
        "question": load_validator("interview_question.schema.json"),
        "knowledge": load_validator("faq.schema.json"),
        "competency": load_validator("competency_item.schema.json"),
        "resume": load_validator("resume_case.schema.json"),
        "growth": load_validator("growth_advice.schema.json"),
        "scoring": load_validator("scoring_rule.schema.json"),
        "runtime": load_validator("runtime_record.schema.json"),
    }

    records: list[dict] = []
    validated_source_docs = 0
    for path in discover_source_files():
        document = parse_markdown(path)
        payload = build_source_payload(document)
        doc_type = str(payload.get("doc_type") or "").strip()
        validator = validators.get(doc_type)
        if validator is None:
            raise BuildError(f"{rel(path)} has unsupported doc_type: {doc_type}")
        validate_with_schema(validator, payload, path)
        validate_tags(document.meta, allowed_tags, path)
        validate_difficulty(document.meta, path, question_levels, knowledge_levels)

        role_code = str(document.meta.get("role") or "").strip()
        source_type = infer_competency_code(role_map, role_code, document.meta)
        topic = resolve_topic(document.meta, path)
        difficulty = resolve_difficulty(doc_type, document.meta)
        source_path = rel(path)
        record = build_record(
            doc_id=str(document.meta.get("id") or path.stem),
            role_code=role_code,
            doc_type=doc_type,
            source_type=source_type,
            topic=topic,
            difficulty=difficulty,
            title=document.title,
            source_path=source_path,
            tags=[str(item) for item in document.meta.get("tags") or []],
            sections=document.sections,
            parsed_meta=build_parsed_meta(document, source_type),
            keyword=document.title,
            extra_metadata=build_extra_metadata(document, source_type),
        )
        validate_with_schema(validators["runtime"], record, path)
        records.append(record)
        validated_source_docs += 1

    return records, validated_source_docs


def validate_question_seeds() -> tuple[int, int]:
    validator = load_validator("question_seed.schema.json")
    seed_count = 0
    file_count = 0
    for path in discover_question_seed_files():
        payload = load_json(path)
        validate_with_schema(validator, payload, path)
        file_count += 1
        opening = payload.get("opening") or []
        seed_count += len(opening)
        competencies = payload.get("competencies") or {}
        if isinstance(competencies, dict):
            for items in competencies.values():
                seed_count += len(items or [])
        follow_up = payload.get("follow_up") or {}
        if isinstance(follow_up, dict):
            seed_count += len([value for value in follow_up.values() if str(value or "").strip()])
    return file_count, seed_count


def get_git_commit() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def collect_content_source_stats() -> dict[str, dict]:
    stats: dict[str, dict] = {}
    if not CONTENT_SOURCE_DIR.is_dir():
        return stats
    for child in sorted(CONTENT_SOURCE_DIR.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        files = [path for path in child.rglob("*") if path.is_file()]
        stats[child.name] = {
            "file_count": len(files),
            "total_bytes": sum(path.stat().st_size for path in files),
        }
    return stats


def coverage_matrix(records: list[dict]) -> dict[str, dict[str, int]]:
    matrix: defaultdict[str, Counter] = defaultdict(Counter)
    for record in records:
        matrix[str(record.get("role_code") or "unknown")][str(record.get("doc_type") or "unknown")] += 1
    return {
        role: dict(sorted(counter.items()))
        for role, counter in sorted(matrix.items())
    }


def embedding_text_stats(records: list[dict]) -> dict:
    lengths = [len(str(record.get("embedding_text") or "")) for record in records]
    if not lengths:
        return {"avg": 0, "min": 0, "max": 0}
    return {
        "avg": round(sum(lengths) / len(lengths), 2),
        "min": min(lengths),
        "max": max(lengths),
    }


def build_manifest(records: list[dict], generated_at: str) -> dict:
    role_counter = Counter(str(item.get("role_code") or "unknown") for item in records)
    doc_counter = Counter(str(item.get("doc_type") or "unknown") for item in records)
    return {
        "dataset": "demo_rag_v2",
        "source_root": "data/content_source",
        "output_root": "data/runtime_corpus",
        "record_count": len(records),
        "roles": dict(role_counter),
        "doc_types": dict(doc_counter),
        "generated_at": generated_at,
        "source_note": "data/runtime_corpus/records.jsonl is the canonical runtime corpus; edit data/content_source/ and rerun scripts/build_runtime_corpus.py.",
    }


def build_report(
    *,
    records: list[dict],
    generated_at: str,
    validated_source_docs: int,
    validated_seed_files: int,
    question_seed_count: int,
    duplicate_pairs: list[dict],
    duration_seconds: float,
) -> dict:
    doc_counter = Counter(str(item.get("doc_type") or "unknown") for item in records)
    role_counter = Counter(str(item.get("role_code") or "unknown") for item in records)
    return {
        "generated_at": generated_at,
        "git_commit": get_git_commit(),
        "dataset": "demo_rag_v2",
        "record_count": len(records),
        "question_seed_count": question_seed_count,
        "doc_type_counts": dict(doc_counter),
        "role_counts": dict(role_counter),
        "content_source_stats": collect_content_source_stats(),
        "schema_validation": {
            "validated_source_docs": validated_source_docs,
            "validated_question_seed_files": validated_seed_files,
            "validated_runtime_records": len(records),
            "errors": 0,
        },
        "duplicate_report": {
            "threshold": QUALITY_THRESHOLD,
            "pair_count": len(duplicate_pairs),
        },
        "coverage_matrix": coverage_matrix(records),
        "embedding_text_stats": embedding_text_stats(records),
        "build_duration_seconds": round(duration_seconds, 3),
    }


def build_output_payloads() -> dict[str, str]:
    started_at = time.perf_counter()

    roles_catalog = load_json(METADATA_DIR / "taxonomies" / "roles.json")
    role_map = {
        str(item.get("code") or "").strip(): item
        for item in roles_catalog.get("roles", [])
        if str(item.get("code") or "").strip()
    }
    difficulty_rules = load_json(METADATA_DIR / "difficulty_rules" / "rules.json")
    question_levels = {str(item).strip() for item in (difficulty_rules.get("question") or {}).keys() if str(item).strip()}
    knowledge_levels = {str(item).strip() for item in (difficulty_rules.get("knowledge") or {}).keys() if str(item).strip()}
    tag_dictionary = load_json(METADATA_DIR / "tag_dictionary" / "tags.json")
    allowed_tags = {
        str(item).strip()
        for values in tag_dictionary.values()
        if isinstance(values, list)
        for item in values
        if str(item).strip()
    }

    records, validated_source_docs = build_runtime_records(role_map, allowed_tags, question_levels, knowledge_levels)
    validated_seed_files, question_seed_count = validate_question_seeds()
    duplicate_pairs = build_duplicate_report(records, threshold=QUALITY_THRESHOLD)
    generated_at = datetime.now(timezone.utc).isoformat()
    duration_seconds = time.perf_counter() - started_at

    duplicate_report = {
        "generated_at": generated_at,
        "threshold": QUALITY_THRESHOLD,
        "pair_count": len(duplicate_pairs),
        "pairs": duplicate_pairs,
    }
    snapshot = build_snapshot(records)
    manifest = build_manifest(records, generated_at)
    build_report_payload = build_report(
        records=records,
        generated_at=generated_at,
        validated_source_docs=validated_source_docs,
        validated_seed_files=validated_seed_files,
        question_seed_count=question_seed_count,
        duplicate_pairs=duplicate_pairs,
        duration_seconds=duration_seconds,
    )

    return {
        rel(RECORDS_PATH): dump_jsonl(records),
        rel(MANIFEST_PATH): dump_json(manifest),
        rel(BUILD_REPORT_PATH): dump_json(build_report_payload),
        rel(DUPLICATE_REPORT_PATH): dump_json(duplicate_report),
        rel(SNAPSHOT_PATH): dump_jsonl(snapshot),
    }


def write_outputs(outputs: dict[str, str]) -> None:
    for relative_path, content in outputs.items():
        path = ROOT / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check_outputs(outputs: dict[str, str]) -> int:
    stale: list[str] = []
    for relative_path, expected in outputs.items():
        path = ROOT / relative_path
        if not path.is_file():
            stale.append(relative_path)
            continue
        actual = path.read_text(encoding="utf-8-sig")
        if _normalize_check_payload(relative_path, actual) != _normalize_check_payload(relative_path, expected):
            stale.append(relative_path)
    if stale:
        print("runtime corpus drift detected:")
        for item in stale:
            print(f"- {item}")
        return 1
    print("runtime corpus is up to date")
    return 0


def _normalize_check_payload(relative_path: str, payload: str):
    if relative_path.endswith("kb_chunks.jsonl"):
        normalized = []
        for line in payload.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            item["embedding_dim"] = 0
            normalized.append(item)
        return normalized
    if relative_path.endswith(".jsonl"):
        return payload
    if not relative_path.endswith(".json"):
        return payload
    data = json.loads(payload)
    if relative_path.endswith("manifest.json"):
        data.pop("generated_at", None)
    if relative_path.endswith("build_report.json"):
        data.pop("generated_at", None)
        data.pop("build_duration_seconds", None)
    if relative_path.endswith("duplicate_report.json"):
        data.pop("generated_at", None)
    return data


def build_snapshot(records: list[dict]) -> list[dict]:
    snapshot: list[dict] = []
    for line_no, item in enumerate(records, start=1):
        snippet = str(item.get("embedding_text") or item.get("content") or "").strip()
        if not snippet:
            continue
        chunk = Chunk(
            doc_id=str(item.get("id") or item.get("source_id") or f"record-{line_no}"),
            role_code=str(item.get("role_code") or "common").strip() or "common",
            doc_type=str(item.get("doc_type") or "knowledge").strip() or "knowledge",
            competency_code=str(item.get("topic") or item.get("source_type") or item.get("doc_type") or "general").strip()
            or "general",
            title=str(item.get("title") or item.get("keyword") or f"record-{line_no}").strip()[:200],
            snippet=snippet[:3900],
            source_path=str(item.get("source_path") or "data/runtime_corpus/records.jsonl").strip()
            or "data/runtime_corpus/records.jsonl",
            section=str(line_no),
        )
        snapshot.append(chunk_to_snapshot_record(chunk))

    for path in discover_question_seed_files():
        snapshot.extend(chunk_to_snapshot_record(chunk) for chunk in _load_question_seed_chunks(path, ROOT))

    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser(description="Build validated runtime corpus artifacts from data/content_source.")
    parser.add_argument("--check", action="store_true", help="Only compare expected outputs without writing files.")
    args = parser.parse_args()

    outputs = build_output_payloads()
    if args.check:
        return check_outputs(outputs)
    write_outputs(outputs)
    print(
        "wrote "
        f"{rel(RECORDS_PATH)}, {rel(MANIFEST_PATH)}, {rel(BUILD_REPORT_PATH)}, "
        f"{rel(DUPLICATE_REPORT_PATH)}, and {rel(SNAPSHOT_PATH)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

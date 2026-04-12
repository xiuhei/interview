from __future__ import annotations

import json
import shutil
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from app.core.config import get_settings
from app.rag.corpus import load_static_corpus
import build_runtime_corpus as runtime_builder


def _copy_common_validation_inputs(tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "metadata", data_dir / "metadata")
    shutil.copytree(ROOT / "data" / "schemas", data_dir / "schemas")
    return data_dir


def _patch_runtime_builder(monkeypatch, tmp_path: Path) -> Path:
    data_dir = tmp_path / "data"
    monkeypatch.setattr(runtime_builder, "ROOT", tmp_path)
    monkeypatch.setattr(runtime_builder, "DATA_DIR", data_dir)
    monkeypatch.setattr(runtime_builder, "CONTENT_SOURCE_DIR", data_dir / "content_source")
    monkeypatch.setattr(runtime_builder, "RUNTIME_DIR", data_dir / "runtime_corpus")
    monkeypatch.setattr(runtime_builder, "ARTIFACTS_DIR", data_dir / "build_artifacts")
    monkeypatch.setattr(runtime_builder, "SCHEMA_DIR", data_dir / "schemas")
    monkeypatch.setattr(runtime_builder, "METADATA_DIR", data_dir / "metadata")
    monkeypatch.setattr(runtime_builder, "RECORDS_PATH", data_dir / "runtime_corpus" / "records.jsonl")
    monkeypatch.setattr(runtime_builder, "MANIFEST_PATH", data_dir / "runtime_corpus" / "manifest.json")
    monkeypatch.setattr(runtime_builder, "BUILD_REPORT_PATH", data_dir / "build_artifacts" / "build_report.json")
    monkeypatch.setattr(runtime_builder, "DUPLICATE_REPORT_PATH", data_dir / "build_artifacts" / "duplicate_report.json")
    monkeypatch.setattr(runtime_builder, "SNAPSHOT_PATH", data_dir / "build_artifacts" / "kb_chunks.jsonl")
    return data_dir


def _write_valid_question_source(data_dir: Path) -> None:
    source_dir = data_dir / "content_source" / "roles" / "cpp_backend" / "interview_questions" / "foundation"
    source_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "---\n"
        "id: q_cpp_backend_foundation_001\n"
        "doc_type: question\n"
        "role: cpp_backend\n"
        "category: foundation\n"
        "subcategory: raii\n"
        "question_type: foundation\n"
        "difficulty: easy\n"
        "tags: [cpp_backend, foundation, raii, language, cpp_language, cpp]\n"
        "source_priority: high\n"
        "applicable_features: [interview, scoring, practice, follow_up]\n"
        "---\n"
        "# RAII 的核心概念是什么？\n\n"
        "## question\n"
        "请解释 RAII 的核心概念，并说明它主要解决什么问题。\n\n"
        "## reference_answer\n"
        "先给定义，再讲机制、边界和真实场景。\n\n"
        "## key_points\n"
        "- 定义\n"
        "- 机制\n"
        "- 场景\n\n"
        "## common_mistakes\n"
        "- 只背概念\n\n"
        "## scoring_rubric\n"
        "- 90+: 讲清机制与边界\n\n"
        "## follow_up_questions\n"
        "- 真实项目里最难的取舍是什么？\n"
    )
    (source_dir / "q_cpp_backend_foundation_001_raii.md").write_text(content, encoding="utf-8")


def _write_valid_question_seed(data_dir: Path) -> None:
    seed_dir = data_dir / "content_source" / "question_seeds"
    seed_dir.mkdir(parents=True, exist_ok=True)
    (seed_dir / "cpp_backend.json").write_text(
        json.dumps(
            {
                "opening": [{"question": "请介绍一个真实项目。", "competency_code": "project_depth"}],
                "competencies": {"system_design": [{"question": "如何处理瓶颈？"}]},
                "follow_up": {
                    "deepen": "请继续围绕 {competency} 展开。",
                    "redirect": "请回到 {competency} 的关键点。",
                    "credibility": "请补充更可验证的细节。",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_load_static_corpus_gracefully_handles_missing_records_jsonl(tmp_path):
    corpus = load_static_corpus(settings=get_settings(), root_dir=tmp_path)
    assert corpus.source_files == []
    assert corpus.chunks == []


def test_load_static_corpus_ignores_extra_runtime_jsonl(tmp_path):
    data_dir = tmp_path / "data" / "runtime_corpus"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "records.jsonl").write_text(
        json.dumps(
            {
                "id": "doc-1",
                "role_code": "cpp_backend",
                "doc_type": "knowledge",
                "source_type": "knowledge",
                "topic": "cache",
                "title": "cache",
                "content": "cache content",
                "embedding_text": "cache embedding",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (data_dir / "extra.jsonl").write_text(
        json.dumps({"id": "should-not-load", "embedding_text": "ignored"}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    corpus = load_static_corpus(settings=get_settings(), root_dir=tmp_path)

    assert corpus.source_files == ["data/runtime_corpus/records.jsonl"]
    assert [chunk.doc_id for chunk in corpus.chunks] == ["doc-1"]


def test_load_static_corpus_reports_invalid_json_line_number(tmp_path):
    records_path = tmp_path / "data" / "runtime_corpus" / "records.jsonl"
    records_path.parent.mkdir(parents=True, exist_ok=True)
    records_path.write_text('{"id":"ok","embedding_text":"x"}\n{bad json}\n', encoding="utf-8")

    with pytest.raises(ValueError) as excinfo:
        load_static_corpus(settings=get_settings(), root_dir=tmp_path)

    assert "line 2" in str(excinfo.value)
    assert "records.jsonl" in str(excinfo.value)


def test_build_runtime_corpus_accepts_empty_question_seed_directory(tmp_path, monkeypatch):
    data_dir = _copy_common_validation_inputs(tmp_path)
    _patch_runtime_builder(monkeypatch, tmp_path)
    _write_valid_question_source(data_dir)
    (data_dir / "content_source" / "question_seeds").mkdir(parents=True, exist_ok=True)

    outputs = runtime_builder.build_output_payloads()

    assert "data/runtime_corpus/records.jsonl" in outputs
    assert '"record_count": 1' in outputs["data/runtime_corpus/manifest.json"]


def test_build_runtime_corpus_rejects_invalid_front_matter(tmp_path, monkeypatch):
    data_dir = _copy_common_validation_inputs(tmp_path)
    _patch_runtime_builder(monkeypatch, tmp_path)
    _write_valid_question_source(data_dir)
    _write_valid_question_seed(data_dir)

    source_file = next((data_dir / "content_source").rglob("*.md"))
    source_file.write_text(source_file.read_text(encoding="utf-8").replace("difficulty: easy\n", ""), encoding="utf-8")

    with pytest.raises(runtime_builder.BuildError) as excinfo:
        runtime_builder.build_output_payloads()

    assert "difficulty" in str(excinfo.value)


def test_build_runtime_corpus_rejects_invalid_question_seed(tmp_path, monkeypatch):
    data_dir = _copy_common_validation_inputs(tmp_path)
    _patch_runtime_builder(monkeypatch, tmp_path)
    _write_valid_question_source(data_dir)
    _write_valid_question_seed(data_dir)

    seed_path = data_dir / "content_source" / "question_seeds" / "cpp_backend.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    payload.pop("follow_up")
    seed_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(runtime_builder.BuildError) as excinfo:
        runtime_builder.build_output_payloads()

    assert "question_seeds" in str(excinfo.value)


def test_build_runtime_corpus_skips_personalization_assets(tmp_path, monkeypatch):
    data_dir = _copy_common_validation_inputs(tmp_path)
    _patch_runtime_builder(monkeypatch, tmp_path)
    _write_valid_question_source(data_dir)
    _write_valid_question_seed(data_dir)
    personalization = data_dir / "content_source" / "personalization" / "user_summary_templates"
    personalization.mkdir(parents=True, exist_ok=True)
    (personalization / "ignored.md").write_text(
        "---\nid: ignored\ndoc_type: growth\nrole: cpp_backend\n---\n# ignored\n",
        encoding="utf-8",
    )

    outputs = runtime_builder.build_output_payloads()
    records = outputs["data/runtime_corpus/records.jsonl"]

    assert "ignored" not in records


def test_build_runtime_corpus_check_detects_drift(tmp_path, monkeypatch):
    data_dir = _copy_common_validation_inputs(tmp_path)
    _patch_runtime_builder(monkeypatch, tmp_path)
    _write_valid_question_source(data_dir)
    _write_valid_question_seed(data_dir)

    outputs = runtime_builder.build_output_payloads()
    runtime_builder.write_outputs(outputs)
    assert runtime_builder.check_outputs(outputs) == 0

    records_path = data_dir / "runtime_corpus" / "records.jsonl"
    records_path.write_text(records_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    assert runtime_builder.check_outputs(outputs) == 1

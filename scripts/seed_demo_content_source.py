from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import yaml

from generate_demo_rag_data import (
    CPP_TOPICS,
    DATA_DIR,
    ROLE_SPECS,
    WEB_TOPICS,
    generate_common_docs,
    generate_competency_docs,
    generate_demo_data,
    generate_faq,
    generate_growth_docs,
    generate_questions,
    generate_resume_docs,
    normalize_topics,
    render_markdown,
    write_json,
    write_question_seeds,
    write_text,
)


ROOT = Path(__file__).resolve().parents[1]


def reset_seeded_dirs() -> None:
    for target in (
        DATA_DIR / "content_source",
        DATA_DIR / "metadata",
        DATA_DIR / "schemas",
        DATA_DIR / "demo" / "users",
        DATA_DIR / "demo" / "resumes",
        DATA_DIR / "demo" / "practice",
        DATA_DIR / "demo" / "interviews",
        DATA_DIR / "demo" / "growth",
    ):
        if target.exists():
            shutil.rmtree(target)
    legacy_users = DATA_DIR / "demo" / "users.json"
    if legacy_users.exists():
        legacy_users.unlink()


def write_metadata_and_schemas() -> None:
    write_json(
        DATA_DIR / "metadata" / "taxonomies" / "roles.json",
        {
            "roles": [
                {
                    "code": code,
                    "name": spec["display_name"],
                    "competencies": spec["competencies"],
                }
                for code, spec in ROLE_SPECS.items()
            ]
        },
    )
    write_json(
        DATA_DIR / "metadata" / "difficulty_rules" / "rules.json",
        {
            "question": {
                "easy": "单点概念清晰即可",
                "medium": "需要机制、场景或基本取舍说明",
                "hard": "需要 trade-off、证据链或设计能力",
            },
            "knowledge": {
                "beginner": "定义与基本边界",
                "intermediate": "机制、应用与常见误区",
                "advanced": "复杂场景、限制条件与验证路径",
            },
        },
    )
    write_json(
        DATA_DIR / "metadata" / "retrieval_profiles" / "default.json",
        {
            "default": {
                "top_k": 6,
                "allowed_doc_types": ["question", "knowledge", "competency", "scoring"],
                "question_filters": ["role_code", "category", "difficulty"],
                "resume_filters": ["role_code", "case_type"],
                "growth_filters": ["role_code", "weakness_type"],
            },
            "question_generation": {
                "top_k": 6,
                "search_multiplier": 8,
                "lexical_candidate_limit": 24,
                "allowed_doc_types": ["question", "knowledge", "competency"],
                "doc_type_boost": {"question": 3, "knowledge": 2, "competency": 1},
            },
            "answer_analysis": {
                "top_k": 6,
                "search_multiplier": 4,
                "lexical_candidate_limit": 12,
                "allowed_doc_types": ["knowledge", "competency"],
                "doc_type_boost": {"knowledge": 3, "competency": 2},
            },
            "answer_scoring": {
                "top_k": 6,
                "search_multiplier": 4,
                "lexical_candidate_limit": 12,
                "allowed_doc_types": ["knowledge", "competency", "scoring"],
                "doc_type_boost": {"scoring": 3, "competency": 2, "knowledge": 1},
            },
        },
    )
    write_json(
        DATA_DIR / "metadata" / "tag_dictionary" / "tags.json",
        {
            "core_tags": ["cpp_backend", "web_frontend", "common", "question", "knowledge", "resume", "growth", "competency", "scoring"],
            "role_tags": ["cpp_backend", "web_frontend", "common"],
            "doc_type_tags": ["question", "knowledge", "resume", "growth", "competency", "scoring"],
            "category_tags": [],
            "feature_tags": ["interview", "scoring", "practice", "follow_up", "search", "resume_review", "growth", "recommendation", "report", "rewrite", "jd_match"],
        },
    )

    string_array = {"type": "array", "items": {"type": "string"}, "minItems": 1}
    source_doc_base = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["id", "doc_type", "role", "title", "tags", "applicable_features", "sections"],
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "doc_type": {"type": "string", "minLength": 1},
            "role": {"type": "string", "minLength": 1},
            "title": {"type": "string", "minLength": 1},
            "tags": string_array,
            "applicable_features": string_array,
            "sections": {"type": "object"},
        },
    }

    write_json(
        DATA_DIR / "schemas" / "interview_question.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["category", "subcategory", "question_type", "difficulty", "source_priority"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "question"},
                "category": {"type": "string", "minLength": 1},
                "subcategory": {"type": "string", "minLength": 1},
                "question_type": {"type": "string", "minLength": 1},
                "difficulty": {"type": "string", "minLength": 1},
                "source_priority": {"type": "string", "minLength": 1},
                "sections": {
                    "type": "object",
                    "required": [
                        "question",
                        "reference_answer",
                        "key_points",
                        "common_mistakes",
                        "scoring_rubric",
                        "follow_up_questions",
                    ],
                    "properties": {
                        "question": {"type": "string", "minLength": 1},
                        "reference_answer": {"type": "string", "minLength": 1},
                        "key_points": string_array,
                        "common_mistakes": string_array,
                        "scoring_rubric": string_array,
                        "follow_up_questions": string_array,
                    },
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "faq.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["category", "subcategory", "level"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "knowledge"},
                "category": {"type": "string", "minLength": 1},
                "subcategory": {"type": "string", "minLength": 1},
                "level": {"type": "string", "minLength": 1},
                "sections": {
                    "type": "object",
                    "required": ["question", "answer", "extended_explanation", "follow_up_questions"],
                    "properties": {
                        "question": {"type": "string", "minLength": 1},
                        "answer": {"type": "string", "minLength": 1},
                        "extended_explanation": {"type": "string", "minLength": 1},
                        "follow_up_questions": string_array,
                    },
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "competency_item.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["category", "subcategory", "level"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "competency"},
                "category": {"type": "string", "minLength": 1},
                "subcategory": {"type": "string", "minLength": 1},
                "level": {"type": "string", "minLength": 1},
                "sections": {
                    "oneOf": [
                        {
                            "type": "object",
                            "required": ["summary", "signals", "interview_focus", "usage"],
                            "properties": {
                                "summary": {"type": "string", "minLength": 1},
                                "signals": string_array,
                                "interview_focus": string_array,
                                "usage": {"type": "string", "minLength": 1},
                            },
                        },
                        {
                            "type": "object",
                            "required": ["dimension", "qualified_signals", "unqualified_signals", "scoring_hint"],
                            "properties": {
                                "dimension": {"type": "string", "minLength": 1},
                                "qualified_signals": string_array,
                                "unqualified_signals": string_array,
                                "scoring_hint": {"type": "string", "minLength": 1},
                            },
                        },
                    ]
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "resume_case.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["level", "case_type"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "resume"},
                "level": {"type": "string", "minLength": 1},
                "case_type": {"type": "string", "minLength": 1},
                "sections": {"type": "object", "minProperties": 3},
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "growth_advice.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["target_level", "weakness_type"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "growth"},
                "target_level": {"type": "string", "minLength": 1},
                "weakness_type": {"type": "string", "minLength": 1},
                "sections": {
                    "type": "object",
                    "required": ["diagnosis", "improvement_advice", "recommended_practice", "expected_outcome"],
                    "properties": {
                        "diagnosis": {"type": "string", "minLength": 1},
                        "improvement_advice": {"type": "string", "minLength": 1},
                        "recommended_practice": {"type": "string", "minLength": 1},
                        "expected_outcome": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "scoring_rule.schema.json",
        {
            **source_doc_base,
            "required": source_doc_base["required"] + ["category", "subcategory", "difficulty"],
            "properties": {
                **source_doc_base["properties"],
                "doc_type": {"const": "scoring"},
                "category": {"type": "string", "minLength": 1},
                "subcategory": {"type": "string", "minLength": 1},
                "difficulty": {"type": "string", "minLength": 1},
                "sections": {
                    "type": "object",
                    "required": ["summary", "key_points", "usage"],
                    "properties": {
                        "summary": {"type": "string", "minLength": 1},
                        "key_points": string_array,
                        "usage": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "question_seed.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["opening", "competencies", "follow_up"],
            "properties": {
                "opening": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["question", "competency_code"],
                        "properties": {
                            "question": {"type": "string", "minLength": 1},
                            "competency_code": {"type": "string", "minLength": 1},
                        },
                    },
                },
                "competencies": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["question"],
                            "properties": {
                                "question": {"type": "string", "minLength": 1},
                            },
                        },
                    },
                },
                "follow_up": {
                    "type": "object",
                    "required": ["deepen", "redirect", "credibility"],
                    "properties": {
                        "deepen": {"type": "string", "minLength": 1},
                        "redirect": {"type": "string", "minLength": 1},
                        "credibility": {"type": "string", "minLength": 1},
                    },
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "runtime_record.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": [
                "id",
                "source_id",
                "source_dataset",
                "source_path",
                "role_code",
                "doc_type",
                "source_type",
                "topic",
                "difficulty",
                "title",
                "content",
                "embedding_text",
                "tags",
                "aliases",
                "keyword",
                "parsed_meta",
                "sections",
                "metadata",
            ],
            "properties": {
                "id": {"type": "string", "minLength": 1},
                "source_id": {"type": "string", "minLength": 1},
                "source_dataset": {"type": "string", "minLength": 1},
                "source_path": {"type": "string", "minLength": 1},
                "role_code": {"type": "string", "minLength": 1},
                "doc_type": {"type": "string", "minLength": 1},
                "source_type": {"type": "string", "minLength": 1},
                "topic": {"type": "string", "minLength": 1},
                "difficulty": {"type": "string", "minLength": 1},
                "title": {"type": "string", "minLength": 1},
                "content": {"type": "string", "minLength": 1},
                "embedding_text": {"type": "string", "minLength": 1},
                "tags": string_array,
                "aliases": {"type": "array", "items": {"type": "string"}},
                "keyword": {"type": "string", "minLength": 1},
                "parsed_meta": {"type": "object"},
                "sections": {"type": "object", "minProperties": 1},
                "metadata": {
                    "type": "object",
                    "required": ["role_code", "doc_type", "source_type", "topic", "difficulty", "keyword", "source_path", "source_dataset"],
                },
            },
        },
    )
    write_json(
        DATA_DIR / "schemas" / "demo_record.schema.json",
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["user_id", "role_code"],
        },
    )


def generate_personalization_templates(role_code: str) -> None:
    patterns = [
        "基础薄弱型",
        "原理不稳型",
        "项目空泛型",
        "排障链路弱型",
        "指标缺失型",
        "表达分散型",
        "取舍意识弱型",
        "稳定性薄弱型",
        "性能归因弱型",
        "协作推动弱型",
        "简历可信度弱型",
        "成长节奏失衡型",
    ]
    role_name = ROLE_SPECS[role_code]["display_name"]
    for seq, pattern in enumerate(patterns, start=1):
        doc_id = f"persona_template_{role_code}_{seq:03d}"
        path = DATA_DIR / "metadata" / "personalization_templates" / role_code / f"{doc_id}.md"
        sections = [
            ("diagnosis", f"{pattern} 候选人通常不是不会做，而是知识、表达和证据没有形成闭环。"),
            ("improvement_advice", f"摘要生成时优先概括 {role_name} 候选人最近的高频短板、对应专项题和一条可执行建议。"),
            ("recommended_practice", "推荐顺序固定为：基础题 -> 场景题 -> 项目题 -> 复盘建议。"),
            ("expected_outcome", "让个性化摘要更像配置驱动的产品模板，而不是混入知识库正文。"),
        ]
        meta = {
            "id": doc_id,
            "template_type": "personalization_summary",
            "role": role_code,
            "pattern": pattern,
            "tags": [role_code, "persona_template"],
        }
        write_text(path, render_markdown(meta, f"个性化摘要模板：{pattern}", sections))


def refresh_tag_dictionary() -> None:
    tags: set[str] = set()
    for path in sorted((DATA_DIR / "content_source").rglob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        if not text.startswith("---"):
            continue
        lines = text.splitlines()
        end_index = None
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                end_index = index
                break
        if end_index is None:
            continue
        payload = yaml.safe_load("\n".join(lines[1:end_index])) or {}
        for item in payload.get("tags") or []:
            value = str(item or "").strip()
            if value:
                tags.add(value)
    base = json.loads((DATA_DIR / "metadata" / "tag_dictionary" / "tags.json").read_text(encoding="utf-8-sig"))
    base["category_tags"] = sorted(tags)
    write_json(DATA_DIR / "metadata" / "tag_dictionary" / "tags.json", base)


def seed_content_source(force: bool) -> None:
    if DATA_DIR.joinpath("content_source").exists() and not force:
        print("data/content_source already exists; skipping seed (use --force to recreate)")
        return

    reset_seeded_dirs()
    write_metadata_and_schemas()
    generate_demo_data()

    topic_map = {
        "cpp_backend": normalize_topics(CPP_TOPICS),
        "web_frontend": normalize_topics(WEB_TOPICS),
    }
    seed_payloads: dict[str, dict] = {}
    for role_code, topics in topic_map.items():
        _, seed_payload = generate_questions(role_code, topics)
        seed_payloads[role_code] = seed_payload
        generate_faq(role_code, topics)
        generate_competency_docs(role_code)
        generate_resume_docs(role_code)
        generate_growth_docs(role_code)
        generate_personalization_templates(role_code)
    generate_common_docs()
    write_question_seeds(seed_payloads)
    refresh_tag_dictionary()
    print("seeded data/content_source, data/metadata, data/schemas, and data/demo")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo content_source/metadata/schemas/demo directories.")
    parser.add_argument("--force", action="store_true", help="Recreate seeded directories even when content_source already exists.")
    args = parser.parse_args()

    seed_content_source(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

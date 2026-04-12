from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from app.core.config import ROOT_DIR


METADATA_DIR = ROOT_DIR / "data" / "metadata"


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


@lru_cache(maxsize=1)
def get_roles_catalog() -> dict:
    return _read_json(METADATA_DIR / "taxonomies" / "roles.json")


@lru_cache(maxsize=1)
def get_role_map() -> dict[str, dict]:
    roles = get_roles_catalog().get("roles", [])
    return {
        str(item.get("code") or "").strip(): item
        for item in roles
        if str(item.get("code") or "").strip()
    }


@lru_cache(maxsize=1)
def get_competency_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    for role in get_role_map().values():
        competencies = role.get("competencies") or {}
        if isinstance(competencies, dict):
            for code, label in competencies.items():
                key = str(code or "").strip()
                value = str(label or "").strip()
                if key and value:
                    labels[key] = value
    return labels


def get_competency_label(code: str) -> str:
    normalized = str(code or "").strip()
    return get_competency_labels().get(normalized, normalized)


@lru_cache(maxsize=1)
def get_difficulty_rules() -> dict:
    return _read_json(METADATA_DIR / "difficulty_rules" / "rules.json")


def get_allowed_question_difficulties() -> set[str]:
    question_rules = get_difficulty_rules().get("question") or {}
    return {str(item).strip() for item in question_rules.keys() if str(item).strip()}


def get_allowed_knowledge_levels() -> set[str]:
    knowledge_rules = get_difficulty_rules().get("knowledge") or {}
    return {str(item).strip() for item in knowledge_rules.keys() if str(item).strip()}


@lru_cache(maxsize=1)
def get_tag_dictionary() -> dict:
    return _read_json(METADATA_DIR / "tag_dictionary" / "tags.json")


def get_allowed_tags() -> set[str]:
    payload = get_tag_dictionary()
    tags: set[str] = set()
    for key in ("core_tags", "role_tags", "doc_type_tags", "category_tags", "feature_tags"):
        values = payload.get(key) or []
        if isinstance(values, list):
            tags.update(str(item).strip() for item in values if str(item).strip())
    return tags


@lru_cache(maxsize=1)
def get_retrieval_profiles() -> dict:
    return _read_json(METADATA_DIR / "retrieval_profiles" / "default.json")


def get_retrieval_profile(name: str = "default") -> dict:
    payload = get_retrieval_profiles()
    profile = payload.get(name) or {}
    return profile if isinstance(profile, dict) else {}


def clear_metadata_caches() -> None:
    get_roles_catalog.cache_clear()
    get_role_map.cache_clear()
    get_competency_labels.cache_clear()
    get_difficulty_rules.cache_clear()
    get_tag_dictionary.cache_clear()
    get_retrieval_profiles.cache_clear()

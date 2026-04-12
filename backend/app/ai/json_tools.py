import json
from typing import Any


def repair_json_text(payload: str) -> str:
    text = payload.strip()
    if text.startswith("```"):
        lines = [line for line in text.splitlines() if not line.startswith("```")]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    return text


def parse_json(payload: str) -> dict[str, Any]:
    fixed = repair_json_text(payload)
    return json.loads(fixed)

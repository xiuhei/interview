from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RUNTIME_RECORDS_PATH = DATA_DIR / "runtime_corpus" / "records.jsonl"
DUPLICATE_REPORT_PATH = DATA_DIR / "build_artifacts" / "duplicate_report.json"
TOKEN_RE = re.compile(r"[A-Za-z0-9_\u4e00-\u9fff]+")


def load_runtime_records(path: Path = RUNTIME_RECORDS_PATH) -> list[dict]:
    if not path.is_file():
        return []
    records: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            payload = raw_line.strip()
            if not payload:
                continue
            try:
                records.append(json.loads(payload))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON in {path.as_posix()} at line {line_no}: {exc.msg}") from exc
    return records


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(text or "") if token.strip()}


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    intersection = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return intersection / union


def build_duplicate_report(records: list[dict], threshold: float) -> list[dict]:
    prepared = [
        {
            "id": str(record.get("id") or "").strip(),
            "doc_type": str(record.get("doc_type") or "").strip(),
            "tokens": tokenize(str(record.get("embedding_text") or record.get("content") or "")),
        }
        for record in records
    ]
    pairs: list[dict] = []
    for index, left in enumerate(prepared):
        if not left["id"]:
            continue
        for right in prepared[index + 1:]:
            if not right["id"]:
                continue
            similarity = jaccard_similarity(left["tokens"], right["tokens"])
            if similarity < threshold:
                continue
            pairs.append(
                {
                    "id_a": left["id"],
                    "id_b": right["id"],
                    "similarity": round(similarity, 4),
                    "doc_type": left["doc_type"] if left["doc_type"] == right["doc_type"] else "mixed",
                }
            )
    return sorted(pairs, key=lambda item: (-item["similarity"], item["id_a"], item["id_b"]))


def write_duplicate_report(report: list[dict], path: Path = DUPLICATE_REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"generated_from": RUNTIME_RECORDS_PATH.as_posix(), "pairs": report}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect highly similar runtime corpus records.")
    parser.add_argument("--threshold", type=float, default=0.85)
    parser.add_argument("--fail-on-violation", action="store_true")
    parser.add_argument("--records", type=Path, default=RUNTIME_RECORDS_PATH)
    parser.add_argument("--output", type=Path, default=DUPLICATE_REPORT_PATH)
    args = parser.parse_args()

    records = load_runtime_records(args.records)
    report = build_duplicate_report(records, threshold=args.threshold)
    write_duplicate_report(report, path=args.output)
    print(f"duplicate pairs >= {args.threshold:.2f}: {len(report)}")
    if args.fail_on_violation and report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

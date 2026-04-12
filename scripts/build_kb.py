from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db.session import SessionLocal  # noqa: E402
from app.rag.indexer import build_result_to_status_payload, rebuild_knowledge_base  # noqa: E402
from app.repositories.system_repository import SystemRepository  # noqa: E402


def main() -> None:
    result = rebuild_knowledge_base()
    print(f"indexed {result.collection_entities} chunks into Milvus from {result.indexed_docs} source files")
    print(
        "embedding "
        f"calls={result.embedding_calls} "
        f"chunks={result.embedded_chunks} "
        f"duration_s={result.embedding_duration_seconds:.3f}"
    )
    print(f"milvus_write duration_s={result.milvus_write_duration_seconds:.3f}")
    print(f"build_total duration_s={result.total_duration_seconds:.3f}")

    db = SessionLocal()
    try:
        SystemRepository(db).upsert_config("kb_status", build_result_to_status_payload(result))
        db.commit()
        print("knowledge base status updated")
    except Exception as exc:
        db.rollback()
        print(f"knowledge base indexed but status update failed: {exc}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.question_seed_service import QuestionSeedService


def test_question_seed_loading():
    service = QuestionSeedService()
    question, competency = service.get_opening_question("cpp_backend", [], [])
    assert question
    assert competency == "project_depth"

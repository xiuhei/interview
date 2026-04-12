from app.services.answer_boundary_detector import (
    AnswerBoundaryDetector,
    BoundaryAction,
)
from app.speech.silence_grader import SilenceEvent, SilenceGrade


def make_event(grade: SilenceGrade, duration_ms: int, speech_before_ms: int = 3000) -> SilenceEvent:
    return SilenceEvent(
        grade=grade,
        duration_ms=duration_ms,
        speech_before_ms=speech_before_ms,
        timestamp_ms=duration_ms,
    )


async def _evaluate(detector: AnswerBoundaryDetector, event: SilenceEvent, text: str) -> BoundaryAction:
    decision = await detector.evaluate(
        silence_event=event,
        current_transcript=text,
        question="请介绍一下你如何设计高并发订单系统",
    )
    return decision.action


def test_short_pause_keeps_waiting():
    detector = AnswerBoundaryDetector(llm_caller=None, prompt_provider=None)
    action = __import__("asyncio").run(
        _evaluate(detector, make_event(SilenceGrade.SHORT_PAUSE, 1200), "我会先从流量削峰开始说")
    )
    assert action == BoundaryAction.WAIT


def test_long_pause_with_explicit_end_finalizes():
    detector = AnswerBoundaryDetector(llm_caller=None, prompt_provider=None)
    action = __import__("asyncio").run(
        _evaluate(
            detector,
            make_event(SilenceGrade.LONG_PAUSE, 6200),
            "我会先做削峰和幂等控制，再看库存一致性，差不多就是这些",
        )
    )
    assert action == BoundaryAction.FINALIZE


def test_long_pause_with_sparse_content_prompts():
    detector = AnswerBoundaryDetector(llm_caller=None, prompt_provider=None)
    action = __import__("asyncio").run(
        _evaluate(detector, make_event(SilenceGrade.LONG_PAUSE, 6500, 1200), "会用缓存")
    )
    assert action == BoundaryAction.PROMPT_CONTINUE

from app.services.answer_segmentation_service import AnswerSegmentationService


def test_transcript_growth_becomes_multiple_segments():
    service = AnswerSegmentationService()

    first = service.append_from_transcript(
        transcript="我先讲一下整体方案，先做限流和削峰。",
        start_ms=0,
        end_ms=3200,
        gap_before_ms=0,
    )
    second = service.append_from_transcript(
        transcript="我先讲一下整体方案，先做限流和削峰。然后库存扣减要保证幂等。",
        start_ms=5200,
        end_ms=7600,
        gap_before_ms=2000,
    )

    assert first is not None
    assert second is not None
    assert service.segment_count == 2
    assert "幂等" in second.text
    assert service.get_merged_transcript().startswith("我先讲一下整体方案")


def test_long_gap_marks_segment_as_supplement():
    service = AnswerSegmentationService()
    service.append_from_transcript(
        transcript="主要就是先拆链路，再看监控和告警。",
        start_ms=0,
        end_ms=3000,
        gap_before_ms=0,
    )
    segment = service.append_from_transcript(
        transcript="主要就是先拆链路，再看监控和告警。我再补充一点，压测时还做了热点隔离。",
        start_ms=9200,
        end_ms=11200,
        gap_before_ms=6200,
    )

    assert segment is not None
    assert segment.is_supplement is True

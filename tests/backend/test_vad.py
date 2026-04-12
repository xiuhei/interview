"""
VAD 单元测试
"""

import struct
import pytest

from app.speech.vad import VoiceActivityDetector, VADEvent, VADResult


def _make_silence(duration_ms: int, sample_rate: int = 16000) -> bytes:
    """生成静音 PCM 数据"""
    n_samples = int(sample_rate * duration_ms / 1000)
    return struct.pack(f"<{n_samples}h", *([0] * n_samples))


def _make_speech(duration_ms: int, amplitude: int = 5000, sample_rate: int = 16000) -> bytes:
    """生成有声 PCM 数据（简单方波）"""
    n_samples = int(sample_rate * duration_ms / 1000)
    return struct.pack(f"<{n_samples}h", *([amplitude, -amplitude] * (n_samples // 2)))


@pytest.fixture
def vad():
    """旧模式 VAD（兼容测试）"""
    return VoiceActivityDetector(
        speech_threshold=0.03,
        silence_ms_to_end=600,  # 缩短以加速测试
        min_speech_ms=400,
        chunk_ms=200,
        continuous_mode=False,
    )


@pytest.fixture
def vad_continuous():
    """持续模式 VAD"""
    return VoiceActivityDetector(
        speech_threshold=0.03,
        min_speech_ms=400,
        chunk_ms=200,
        continuous_mode=True,
    )


def test_silence_returns_silence(vad):
    chunk = _make_silence(200)
    result = vad.feed(chunk)
    assert result.event == VADEvent.SILENCE


def test_speech_start(vad):
    chunk = _make_speech(200)
    result = vad.feed(chunk)
    assert result.event == VADEvent.SPEECH_START


def test_speech_continue(vad):
    vad.feed(_make_speech(200))
    result = vad.feed(_make_speech(200))
    assert result.event == VADEvent.SPEECH_CONTINUE


def test_endpoint_detection(vad):
    """说话 → 静音超过阈值 → ENDPOINT"""
    vad.feed(_make_speech(200))
    vad.feed(_make_speech(200))
    vad.feed(_make_speech(200))

    vad.feed(_make_silence(200))
    vad.feed(_make_silence(200))
    result = vad.feed(_make_silence(200))
    assert result.event == VADEvent.ENDPOINT


def test_short_speech_ignored(vad):
    """语音太短不触发 ENDPOINT"""
    vad.feed(_make_speech(200))
    vad.feed(_make_silence(200))
    vad.feed(_make_silence(200))
    result = vad.feed(_make_silence(200))
    assert result.event == VADEvent.SILENCE


def test_reset(vad):
    vad.feed(_make_speech(200))
    assert vad.is_speaking
    vad.reset()
    assert not vad.is_speaking
    assert vad.speech_duration_ms == 0


# ---- 持续模式测试 ----

def test_continuous_short_pause(vad_continuous):
    """持续模式：短暂停顿"""
    # 说话
    vad_continuous.feed(_make_speech(200))
    vad_continuous.feed(_make_speech(200))
    vad_continuous.feed(_make_speech(200))

    # 沉默 800ms = 4 chunks → SHORT_PAUSE
    events = []
    for _ in range(5):
        r = vad_continuous.feed(_make_silence(200))
        if r.event not in (VADEvent.SILENCE, VADEvent.SPEECH_CONTINUE):
            events.append(r.event)

    assert VADEvent.SHORT_PAUSE in events


def test_continuous_graded_silence(vad_continuous):
    """持续模式：沉默分级依次触发"""
    # 说话
    for _ in range(5):
        vad_continuous.feed(_make_speech(200))

    # 长时间沉默
    events = []
    for _ in range(45):
        r = vad_continuous.feed(_make_silence(200))
        if r.event not in (VADEvent.SILENCE, VADEvent.SPEECH_CONTINUE):
            events.append(r.event)

    assert VADEvent.SHORT_PAUSE in events
    assert VADEvent.MEDIUM_PAUSE in events
    assert VADEvent.LONG_PAUSE in events
    assert VADEvent.EXTENDED_SILENCE in events


def test_continuous_speech_resumed(vad_continuous):
    """持续模式：停顿后恢复说话"""
    vad_continuous.feed(_make_speech(200))
    vad_continuous.feed(_make_speech(200))
    vad_continuous.feed(_make_speech(200))

    # 短暂停顿
    for _ in range(5):
        vad_continuous.feed(_make_silence(200))

    # 恢复说话
    r = vad_continuous.feed(_make_speech(200))
    assert r.event == VADEvent.SPEECH_RESUMED


def test_continuous_silence_event_data(vad_continuous):
    """持续模式：沉默事件包含正确数据"""
    for _ in range(5):
        vad_continuous.feed(_make_speech(200))

    # 等到 SHORT_PAUSE
    for _ in range(5):
        r = vad_continuous.feed(_make_silence(200))
        if r.event == VADEvent.SHORT_PAUSE:
            assert r.silence_event is not None
            assert r.silence_event.duration_ms >= 800
            assert r.silence_event.speech_before_ms >= 800
            break
    else:
        pytest.fail("SHORT_PAUSE not emitted")

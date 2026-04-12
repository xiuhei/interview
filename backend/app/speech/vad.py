"""
VAD (Voice Activity Detection) / 端点检测。
增强版：支持沉默分级，为持续语音面试模式提供细粒度停顿事件。
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass
from enum import Enum

from app.speech.silence_grader import SilenceEvent, SilenceGrade, SilenceGrader, SilenceThresholds

logger = logging.getLogger(__name__)


class VADEvent(str, Enum):
    SILENCE = "silence"                         # 静默（未检测到语音）
    SPEECH_START = "speech_start"               # 检测到用户开始说话
    SPEECH_CONTINUE = "speech_continue"         # 用户持续说话
    ENDPOINT = "endpoint"                       # 确认说完（兼容旧逻辑）
    # ---- 持续模式新增 ----
    SHORT_PAUSE = "short_pause"                 # 短暂停顿 (0.8s~2s)
    MEDIUM_PAUSE = "medium_pause"               # 中等停顿 (2s~5s)
    LONG_PAUSE = "long_pause"                   # 长停顿 (5s~8s)
    EXTENDED_SILENCE = "extended_silence"        # 超长沉默 (>8s)
    SPEECH_RESUMED = "speech_resumed"           # 停顿后恢复说话


@dataclass
class VADResult:
    """VAD 处理结果"""
    event: VADEvent
    silence_event: SilenceEvent | None = None   # 仅在沉默相关事件时存在


class VoiceActivityDetector:
    """
    增强版 VAD：
    - 基于 RMS 音量检测语音活动
    - 支持沉默分级（SHORT_PAUSE → MEDIUM_PAUSE → LONG_PAUSE → EXTENDED_SILENCE）
    - 每个等级的沉默事件在一次沉默期间只触发一次
    - 支持 SPEECH_RESUMED 事件（停顿后恢复说话）
    - continuous_mode=False 时行为与旧版一致
    """

    def __init__(
        self,
        speech_threshold: float = 0.03,
        silence_ms_to_end: int = 1500,
        min_speech_ms: int = 500,
        chunk_ms: int = 200,
        continuous_mode: bool = True,
        silence_thresholds: SilenceThresholds | None = None,
    ):
        self.speech_threshold = speech_threshold
        self.silence_ms_to_end = silence_ms_to_end
        self.min_speech_ms = min_speech_ms
        self.chunk_ms = chunk_ms
        self.continuous_mode = continuous_mode

        self._is_speaking = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._was_speaking = False   # 是否曾经说过话（用于判断 SPEECH_RESUMED）

        # 沉默分级
        self._grader = SilenceGrader(silence_thresholds)
        self._last_emitted_grade = SilenceGrade.NONE
        self._total_elapsed_ms = 0   # 累计时间（用于时间戳）

    def reset(self) -> None:
        self._is_speaking = False
        self._speech_ms = 0
        self._silence_ms = 0
        self._was_speaking = False
        self._last_emitted_grade = SilenceGrade.NONE

    def feed(self, audio_chunk: bytes) -> VADResult:
        """
        输入一个音频块（16-bit PCM, mono），返回 VAD 结果。
        continuous_mode=True 时返回分级沉默事件。
        continuous_mode=False 时兼容旧行为。
        """
        self._total_elapsed_ms += self.chunk_ms
        rms = self._compute_rms(audio_chunk)
        has_speech = rms > self.speech_threshold

        if has_speech:
            return self._handle_speech(rms)
        else:
            return self._handle_silence()

    def _handle_speech(self, rms: float) -> VADResult:
        """处理有语音的情况"""
        was_in_pause = self._silence_ms > 0 and self._was_speaking

        self._silence_ms = 0
        self._last_emitted_grade = SilenceGrade.NONE

        if not self._is_speaking:
            self._is_speaking = True
            self._speech_ms = self.chunk_ms

            if was_in_pause:
                # 停顿后恢复说话
                logger.debug("VAD: speech_resumed rms=%.4f", rms)
                self._was_speaking = True
                return VADResult(event=VADEvent.SPEECH_RESUMED)
            else:
                # 首次开始说话
                logger.debug("VAD: speech_start rms=%.4f", rms)
                self._was_speaking = True
                return VADResult(event=VADEvent.SPEECH_START)
        else:
            self._speech_ms += self.chunk_ms
            return VADResult(event=VADEvent.SPEECH_CONTINUE)

    def _handle_silence(self) -> VADResult:
        """处理无语音的情况"""
        if not self._is_speaking and not self._was_speaking:
            return VADResult(event=VADEvent.SILENCE)

        if self._is_speaking:
            # 从说话转入沉默
            self._silence_ms += self.chunk_ms

            if not self.continuous_mode:
                # 旧模式：固定阈值判定端点
                return self._legacy_endpoint_check()

            # 持续模式：分级沉默检测
            return self._graded_silence_check()

        # _was_speaking=True 但 _is_speaking=False：已经触发过端点/分级沉默
        # 持续累积沉默时间
        self._silence_ms += self.chunk_ms

        if self.continuous_mode:
            return self._graded_silence_check()
        return VADResult(event=VADEvent.SILENCE)

    def _legacy_endpoint_check(self) -> VADResult:
        """旧模式端点检测"""
        if self._silence_ms >= self.silence_ms_to_end:
            if self._speech_ms >= self.min_speech_ms:
                logger.debug(
                    "VAD: endpoint speech=%dms silence=%dms",
                    self._speech_ms, self._silence_ms,
                )
                self._is_speaking = False
                self._speech_ms = 0
                self._silence_ms = 0
                return VADResult(event=VADEvent.ENDPOINT)
            else:
                self._is_speaking = False
                self._speech_ms = 0
                self._silence_ms = 0
                return VADResult(event=VADEvent.SILENCE)
        return VADResult(event=VADEvent.SPEECH_CONTINUE)

    def _graded_silence_check(self) -> VADResult:
        """持续模式：分级沉默检测，每个等级只触发一次"""
        current_grade = self._grader.classify(self._silence_ms)

        if current_grade == SilenceGrade.NONE:
            # 沉默时间不足以触发任何等级
            return VADResult(event=VADEvent.SPEECH_CONTINUE)

        # 只有升级时才触发新事件
        if self._grade_rank(current_grade) > self._grade_rank(self._last_emitted_grade):
            self._last_emitted_grade = current_grade
            # 标记不再说话（已进入停顿阶段）
            speech_before = self._speech_ms
            self._is_speaking = False

            silence_event = self._grader.create_event(
                silence_ms=self._silence_ms,
                speech_before_ms=speech_before,
                timestamp_ms=self._total_elapsed_ms,
            )

            event_map = {
                SilenceGrade.SHORT_PAUSE: VADEvent.SHORT_PAUSE,
                SilenceGrade.MEDIUM_PAUSE: VADEvent.MEDIUM_PAUSE,
                SilenceGrade.LONG_PAUSE: VADEvent.LONG_PAUSE,
                SilenceGrade.EXTENDED_SILENCE: VADEvent.EXTENDED_SILENCE,
            }
            vad_event = event_map[current_grade]

            logger.debug(
                "VAD: %s silence=%dms speech_before=%dms",
                vad_event.value, self._silence_ms, speech_before,
            )
            return VADResult(event=vad_event, silence_event=silence_event)

        # 等级未升级，返回静默持续
        return VADResult(event=VADEvent.SILENCE)

    @staticmethod
    def _grade_rank(grade: SilenceGrade) -> int:
        ranks = {
            SilenceGrade.NONE: 0,
            SilenceGrade.SHORT_PAUSE: 1,
            SilenceGrade.MEDIUM_PAUSE: 2,
            SilenceGrade.LONG_PAUSE: 3,
            SilenceGrade.EXTENDED_SILENCE: 4,
        }
        return ranks.get(grade, 0)

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def speech_duration_ms(self) -> int:
        return self._speech_ms

    @property
    def silence_duration_ms(self) -> int:
        return self._silence_ms

    @staticmethod
    def _compute_rms(audio_chunk: bytes) -> float:
        """计算 16-bit PCM 音频的 RMS 音量（归一化到 0~1）"""
        if len(audio_chunk) < 2:
            return 0.0
        n_samples = len(audio_chunk) // 2
        try:
            samples = struct.unpack(f"<{n_samples}h", audio_chunk[:n_samples * 2])
        except struct.error:
            return 0.0
        if not samples:
            return 0.0
        sum_sq = sum(s * s for s in samples)
        rms = (sum_sq / n_samples) ** 0.5
        return rms / 32768.0  # 归一化

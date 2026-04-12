"""
沉默分级器 — 将连续沉默时长分类为不同等级。
用于持续语音面试模式下的停顿判断。
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class SilenceGrade(str, Enum):
    """沉默等级"""
    NONE = "none"                       # 无沉默（正在说话）
    SHORT_PAUSE = "short_pause"         # 短暂停顿 (0.8s ~ 2s) — 正常思考
    MEDIUM_PAUSE = "medium_pause"       # 中等停顿 (2s ~ 5s) — 可能在想/快结束
    LONG_PAUSE = "long_pause"           # 长停顿 (5s ~ 8s) — 可能已回答结束
    EXTENDED_SILENCE = "extended_silence"  # 超长沉默 (>8s) — 基本可判定结束


@dataclass
class SilenceEvent:
    """沉默事件"""
    grade: SilenceGrade
    duration_ms: int            # 当前连续沉默时长
    speech_before_ms: int       # 沉默前的语音时长
    timestamp_ms: int = 0       # 事件时间戳（相对面试开始）


@dataclass
class SilenceThresholds:
    """沉默分级阈值（可配置）"""
    short_pause_ms: int = 800
    medium_pause_ms: int = 2000
    long_pause_ms: int = 5000
    extended_silence_ms: int = 8000

    def validate(self) -> None:
        assert self.short_pause_ms < self.medium_pause_ms < self.long_pause_ms < self.extended_silence_ms, \
            "沉默阈值必须递增: short < medium < long < extended"


class SilenceGrader:
    """
    沉默分级器。
    根据连续沉默时长和配置阈值，返回当前沉默等级。
    """

    def __init__(self, thresholds: SilenceThresholds | None = None):
        self.thresholds = thresholds or SilenceThresholds()
        self.thresholds.validate()

    def classify(self, silence_ms: int) -> SilenceGrade:
        """根据沉默时长返回等级"""
        t = self.thresholds
        if silence_ms >= t.extended_silence_ms:
            return SilenceGrade.EXTENDED_SILENCE
        elif silence_ms >= t.long_pause_ms:
            return SilenceGrade.LONG_PAUSE
        elif silence_ms >= t.medium_pause_ms:
            return SilenceGrade.MEDIUM_PAUSE
        elif silence_ms >= t.short_pause_ms:
            return SilenceGrade.SHORT_PAUSE
        else:
            return SilenceGrade.NONE

    def create_event(
        self,
        silence_ms: int,
        speech_before_ms: int,
        timestamp_ms: int = 0,
    ) -> SilenceEvent:
        """创建沉默事件"""
        return SilenceEvent(
            grade=self.classify(silence_ms),
            duration_ms=silence_ms,
            speech_before_ms=speech_before_ms,
            timestamp_ms=timestamp_ms,
        )

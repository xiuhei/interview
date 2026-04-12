"""
语音特征分析 — 提取语速、停顿比、音量稳定性等指标。
先用规则 + mock 实现，模块结构真实，后续可替换为更精准的模型。
"""

from __future__ import annotations

import logging
import struct
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class AudioFeatureResult:
    """语音特征分析结果"""
    speech_rate_wpm: float = 0.0       # 语速（每分钟字数）
    pause_ratio: float = 0.0           # 停顿比（静音时长 / 总时长）
    volume_stability: float = 0.0      # 音量稳定性 (0~1, 1=最稳定)
    pitch_variance: float = 0.0        # 音调变化幅度
    voiced_ratio: float = 0.0          # 有声段占比
    confidence_score: float = 0.0      # 语音自信度 (0~1)
    clarity_score: float = 0.0         # 清晰度 (0~1)
    fluency_score: float = 0.0         # 流畅度 (0~1)
    emotion_state: str = "neutral"     # 情绪状态


class AudioFeatureExtractor:
    """语音特征提取器"""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def analyze(self, audio_data: bytes, transcript: str = "") -> AudioFeatureResult:
        """
        分析音频数据，返回语音特征。
        当前为基于规则的简化实现。
        """
        if not audio_data or len(audio_data) < 100:
            return AudioFeatureResult()

        duration_s = len(audio_data) / (self.sample_rate * 2)  # 16-bit mono
        if duration_s < 0.1:
            return AudioFeatureResult()

        # 计算基础指标
        rms_values = self._compute_chunk_rms(audio_data, chunk_size=3200)  # 100ms chunks
        voiced_chunks = sum(1 for r in rms_values if r > 0.02)
        total_chunks = max(len(rms_values), 1)
        voiced_ratio = voiced_chunks / total_chunks

        # 音量稳定性
        if rms_values:
            mean_rms = sum(rms_values) / len(rms_values)
            if mean_rms > 0:
                variance = sum((r - mean_rms) ** 2 for r in rms_values) / len(rms_values)
                cv = (variance ** 0.5) / mean_rms  # 变异系数
                volume_stability = max(0.0, min(1.0, 1.0 - cv))
            else:
                volume_stability = 0.0
        else:
            volume_stability = 0.0

        # 语速估算（基于转写文本字数和有声时长）
        if transcript and voiced_ratio > 0:
            char_count = len(transcript.replace(" ", ""))
            speech_seconds = duration_s * voiced_ratio
            speech_rate_wpm = (char_count / max(speech_seconds, 1)) * 60
        else:
            speech_rate_wpm = 0.0

        # 停顿比
        pause_ratio = 1.0 - voiced_ratio

        # 流畅度 & 自信度（简化推算）
        fluency_score = min(1.0, voiced_ratio * 1.2)
        confidence_score = min(1.0, volume_stability * 0.5 + fluency_score * 0.5)
        clarity_score = min(1.0, volume_stability * 0.6 + (1.0 - pause_ratio) * 0.4)

        return AudioFeatureResult(
            speech_rate_wpm=round(speech_rate_wpm, 1),
            pause_ratio=round(pause_ratio, 3),
            volume_stability=round(volume_stability, 3),
            pitch_variance=0.0,  # 需要更复杂的分析
            voiced_ratio=round(voiced_ratio, 3),
            confidence_score=round(confidence_score, 3),
            clarity_score=round(clarity_score, 3),
            fluency_score=round(fluency_score, 3),
            emotion_state="neutral",
        )

    def _compute_chunk_rms(self, audio_data: bytes, chunk_size: int = 3200) -> list[float]:
        """分块计算 RMS"""
        results = []
        for i in range(0, len(audio_data) - chunk_size + 1, chunk_size):
            chunk = audio_data[i:i + chunk_size]
            n_samples = len(chunk) // 2
            try:
                samples = struct.unpack(f"<{n_samples}h", chunk[:n_samples * 2])
            except struct.error:
                results.append(0.0)
                continue
            sum_sq = sum(s * s for s in samples)
            rms = (sum_sq / max(n_samples, 1)) ** 0.5 / 32768.0
            results.append(rms)
        return results

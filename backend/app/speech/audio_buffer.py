"""
音频缓冲管理 — 收集 WebSocket 传入的音频块，合并为完整音频。
"""

from __future__ import annotations

import base64
import logging

logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    收集音频块并合并。
    支持 base64 编码的 PCM 数据。
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        self.sample_rate = sample_rate
        self.channels = channels
        self._chunks: list[bytes] = []
        self._total_bytes = 0

    def append(self, chunk_b64: str) -> bytes:
        """
        追加 base64 编码的音频块。
        返回解码后的原始 PCM 数据。
        """
        try:
            raw = base64.b64decode(chunk_b64)
        except Exception:
            logger.warning("音频块 base64 解码失败")
            return b""
        self._chunks.append(raw)
        self._total_bytes += len(raw)
        return raw

    def append_raw(self, raw: bytes) -> None:
        self._chunks.append(raw)
        self._total_bytes += len(raw)

    def get_all(self) -> bytes:
        return b"".join(self._chunks)

    def get_duration_ms(self) -> int:
        bytes_per_sample = 2 * self.channels  # 16-bit
        total_samples = self._total_bytes // bytes_per_sample
        return int(total_samples / self.sample_rate * 1000)

    def clear(self) -> None:
        self._chunks.clear()
        self._total_bytes = 0

    @property
    def size_bytes(self) -> int:
        return self._total_bytes

    @property
    def is_empty(self) -> bool:
        return self._total_bytes == 0

    def to_wav_bytes(self) -> bytes:
        """将 PCM 数据封装为 WAV 格式"""
        import struct
        pcm = self.get_all()
        bits_per_sample = 16
        byte_rate = self.sample_rate * self.channels * bits_per_sample // 8
        block_align = self.channels * bits_per_sample // 8
        data_size = len(pcm)
        file_size = 36 + data_size

        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", file_size, b"WAVE",
            b"fmt ", 16, 1,  # PCM format
            self.channels, self.sample_rate,
            byte_rate, block_align, bits_per_sample,
            b"data", data_size,
        )
        return header + pcm

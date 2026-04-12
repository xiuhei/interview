"""
Mock ASR 实现 — 用于开发和测试。
返回预设文本或随机技术回答。
"""

from __future__ import annotations

import random

from app.speech.base import SpeechRecognitionService, TranscriptionResult

_MOCK_ANSWERS = [
    "我在上一个项目中主要负责后端微服务架构的设计和实现，用的是Go语言和gRPC框架。",
    "这个性能优化是我独立完成的，主要是通过引入缓存层和数据库索引优化，QPS从500提升到了3000。",
    "我用的是Vue3加TypeScript，组件化开发，状态管理用的Pinia。",
    "并发控制这块我比较熟悉，用过互斥锁、读写锁，也做过无锁队列的实现。",
    "我对TCP三次握手和四次挥手比较了解，也实际排查过线上的连接泄露问题。",
    "容器化部署这块，我用Docker和Kubernetes，CI/CD用的是GitLab Pipeline。",
    "单元测试覆盖率大概在80%左右，核心模块都有集成测试。",
    "这个项目大概持续了半年，团队五个人，我负责核心交易模块。",
]


class MockSpeechRecognitionService(SpeechRecognitionService):
    """返回预设文本，用于开发测试"""

    async def transcribe(self, audio_data: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        text = random.choice(_MOCK_ANSWERS)
        duration_ms = max(len(audio_data) // (sample_rate * 2) * 1000, 3000)
        return TranscriptionResult(
            text=text,
            language="zh",
            confidence=round(random.uniform(0.85, 0.99), 2),
            duration_ms=duration_ms,
        )

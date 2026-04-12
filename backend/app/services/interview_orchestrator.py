"""
面试主协调器 — 串联状态机、记忆、LLM、ASR、决策。
增强版：支持持续语音对话模式（自动判断回答结束、沉默分级、回答切分）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from app.ai.json_tools import parse_json, repair_json_text
from app.ai.prompt_loader import FilePromptTemplateProvider, PromptTemplateProvider
from app.audio.tts import get_tts_service
from app.core.config import get_settings
from app.schemas.websocket import ServerMessage
from app.services.answer_boundary_detector import (
    AnswerBoundaryDetector,
    BoundaryAction,
)
from app.services.answer_segmentation_service import AnswerSegmentationService
from app.services.interview_difficulty import get_difficulty_profile, normalize_difficulty
from app.services.interview_memory_service import InterviewMemoryService
from app.services.interview_state_machine import (
    InterviewEvent,
    InterviewState,
    InterviewStateMachine,
)
from app.services.silence_prompt_decider import SilencePromptDecider
from app.services.websocket_manager import WebSocketManager, ws_manager
from app.speech.audio_buffer import AudioBuffer
from app.speech.audio_feature_extractor import AudioFeatureExtractor, AudioFeatureResult
from app.speech.base import SpeechRecognitionService
from app.speech.mock_asr import MockSpeechRecognitionService
from app.speech.silence_grader import SilenceThresholds
from app.speech.vad import VADEvent, VADResult, VoiceActivityDetector

logger = logging.getLogger(__name__)


class InterviewOrchestratorService:
    """
    面试主协调器。
    每个面试会话对应一个实例，管理该会话的完整生命周期。
    支持两种模式：
    - 持续模式（continuous_mode=True）：自动判断回答结束、沉默分级
    - 旧模式（continuous_mode=False）：兼容手动开关麦
    """

    def __init__(
        self,
        session_id: str,
        ws_mgr: WebSocketManager | None = None,
        prompt_provider: PromptTemplateProvider | None = None,
    ):
        self.session_id = session_id
        self.ws_mgr = ws_mgr or ws_manager
        self.settings = get_settings()
        self.prompt_provider = prompt_provider or FilePromptTemplateProvider()

        # 核心组件（在 prepare 阶段初始化）
        self.state_machine: InterviewStateMachine | None = None
        self.memory: InterviewMemoryService | None = None
        self.vad: VoiceActivityDetector | None = None
        self.audio_buffer: AudioBuffer | None = None
        self.feature_extractor = AudioFeatureExtractor()
        self.asr: SpeechRecognitionService = MockSpeechRecognitionService()
        self.tts = get_tts_service() if self.settings.tts_ready else None

        # 持续模式组件
        self.boundary_detector: AnswerBoundaryDetector | None = None
        self.segmentation: AnswerSegmentationService | None = None
        self.silence_prompt_decider: SilencePromptDecider | None = None
        self.continuous_mode: bool = self.settings.continuous_mode_enabled

        # 面试配置
        self.job_name: str = ""
        self.style: str = "medium"
        self.max_rounds: int = self.settings.dynamic_interview_max_questions
        self.resume_summary: str | None = None
        self.competencies: list[str] = []
        self.job_config: dict = {}
        self.style_config: dict = {}

        # 运行时
        self._silence_timer: asyncio.Task | None = None
        self._rounds: list[dict] = []
        self._analysis_results: list[dict] = []
        self._audio_features: list[AudioFeatureResult] = []
        self._consecutive_empty = 0
        self._degraded = False

        # 持续模式运行时
        self._silence_reminder_count: int = 0
        self._last_nudge_time: float = 0
        self._current_speech_start_ms: int = 0
        self._current_segment_start_ms: int = 0
        self._last_segment_end_ms: int = 0
        self._pending_finalize_task: asyncio.Task | None = None
        self._current_transcript: str = ""
        self._last_interim_transcript: str = ""
        self._question_start_time: float = 0

    # ============================================================
    # 公共 API
    # ============================================================

    async def create_session(
        self,
        job_name: str,
        style: str = "medium",
        max_rounds: int | None = None,
        resume_summary: str | None = None,
        competencies: list[str] | None = None,
    ) -> None:
        """初始化面试会话"""
        self.job_name = job_name
        self.style = normalize_difficulty(style)
        if max_rounds is None:
            max_rounds = self.settings.dynamic_interview_max_questions
        self.max_rounds = max_rounds
        self.resume_summary = resume_summary
        self.competencies = competencies or []

        self.state_machine = InterviewStateMachine(self.session_id)
        self.memory = InterviewMemoryService(
            job_name=job_name,
            style=self.style,
            max_rounds=max_rounds,
            resume_summary=resume_summary,
            competencies=list(self.competencies),
        )

        # 构建沉默阈值
        silence_thresholds = SilenceThresholds(
            short_pause_ms=self.settings.silence_short_pause_ms,
            medium_pause_ms=self.settings.silence_medium_pause_ms,
            long_pause_ms=self.settings.silence_long_pause_ms,
            extended_silence_ms=self.settings.silence_extended_ms,
        )

        self.vad = VoiceActivityDetector(
            speech_threshold=0.03,
            silence_ms_to_end=1500,
            min_speech_ms=500,
            chunk_ms=200,
            continuous_mode=self.continuous_mode,
            silence_thresholds=silence_thresholds,
        )
        self.audio_buffer = AudioBuffer()

        # 持续模式组件
        if self.continuous_mode:
            self.boundary_detector = AnswerBoundaryDetector(
                llm_caller=self._call_llm,
                prompt_provider=self.prompt_provider,
                min_speech_ms=self.settings.answer_min_speech_ms,
            )
            self.segmentation = AnswerSegmentationService(
                llm_caller=self._call_llm,
                prompt_provider=self.prompt_provider,
            )
            self.silence_prompt_decider = SilencePromptDecider(
                llm_caller=self._call_llm,
                prompt_provider=self.prompt_provider,
            )

        # 加载岗位和风格配置
        self.job_config = self._load_job_config(job_name)
        self.style_config = self._load_style_config(self.style)

        logger.info(
            "面试会话创建 session=%s job=%s style=%s continuous=%s",
            self.session_id, job_name, self.style, self.continuous_mode,
        )

    async def start_interview(self) -> str:
        """启动面试，返回开场白+首题"""
        sm = self.state_machine
        await sm.fire(InterviewEvent.PREPARE)
        await sm.fire(InterviewEvent.PREPARED)

        # OPENING → 生成开场白+首题
        opening_text = await self._generate_opening()
        first_question = await self._generate_first_question()
        full_text = f"{opening_text} {first_question}"

        self.memory.advance_round()
        self.memory.set_current_question(first_question)

        await sm.fire(InterviewEvent.OPENING_DONE)

        # 发送给前端
        await self._send(self._build_speak_message(full_text, is_question=True))
        await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))

        # 通知前端持续模式状态
        if self.continuous_mode:
            await self._send(ServerMessage.continuous_mode(True))

        return full_text

    async def handle_audio_chunk(self, chunk_b64: str) -> None:
        """处理前端发来的音频块"""
        sm = self.state_machine
        raw = self.audio_buffer.append(chunk_b64)
        if not raw:
            return

        vad_result = self.vad.feed(raw)

        if self.continuous_mode:
            await self._handle_audio_continuous(vad_result)
        else:
            await self._handle_audio_legacy(vad_result)

    async def handle_speak_done(self) -> None:
        """前端 TTS 播报完毕"""
        sm = self.state_machine
        if sm.can_fire(InterviewEvent.SPEAK_DONE):
            await sm.fire(InterviewEvent.SPEAK_DONE)
            await self._send(ServerMessage.listening())
            await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))
            self._start_silence_timer()
            self._question_start_time = time.monotonic()

    async def handle_user_end(self) -> dict:
        """用户主动结束面试"""
        return await self._finish_interview()

    async def handle_force_answer_end(self) -> None:
        """用户手动标记回答结束（持续模式的可选快捷方式）"""
        sm = self.state_machine
        if sm.is_candidate_active() or sm.state == InterviewState.USER_SPEAKING:
            logger.info("用户手动结束回答 session=%s", self.session_id)
            self._cancel_pending_finalize()
            await self._finalize_answer()

    # ============================================================
    # 持续模式：音频处理
    # ============================================================

    async def _handle_audio_continuous(self, vad_result: VADResult) -> None:
        """持续模式下的音频事件处理"""
        sm = self.state_machine
        event = vad_result.event

        if event == VADEvent.SPEECH_START:
            await self._on_speech_start()

        elif event == VADEvent.SPEECH_RESUMED:
            await self._on_speech_resumed()

        elif event == VADEvent.SPEECH_CONTINUE:
            pass  # 正常说话，无需动作

        elif event == VADEvent.SHORT_PAUSE:
            await self._on_short_pause(vad_result)

        elif event == VADEvent.MEDIUM_PAUSE:
            await self._on_medium_pause(vad_result)

        elif event == VADEvent.LONG_PAUSE:
            await self._on_long_pause(vad_result)

        elif event == VADEvent.EXTENDED_SILENCE:
            await self._on_extended_silence(vad_result)

    async def _on_speech_start(self) -> None:
        """检测到语音开始"""
        sm = self.state_machine
        if sm.can_fire(InterviewEvent.USER_STARTED):
            self._cancel_silence_timer()
            self._cancel_pending_finalize()
            self._current_speech_start_ms = int(
                (time.monotonic() - self._question_start_time) * 1000
            ) if self._question_start_time else 0
            self._current_segment_start_ms = self._current_speech_start_ms

            await sm.fire(InterviewEvent.USER_STARTED)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))

    async def _on_speech_resumed(self) -> None:
        """停顿后恢复说话"""
        sm = self.state_machine
        if sm.can_fire(InterviewEvent.SPEECH_RESUMED):
            self._cancel_pending_finalize()
            # 计算与上一段的间隔
            now_ms = int((time.monotonic() - self._question_start_time) * 1000) \
                if self._question_start_time else 0
            gap_ms = now_ms - self._last_segment_end_ms if self._last_segment_end_ms else 0
            await self._flush_current_segment(end_ms=now_ms, gap_before_ms=max(0, gap_ms))

            # 如果之前有一段内容，先保存为一个 segment
            if self._current_transcript.strip() and self.segmentation:
                is_supplement = self.segmentation.should_mark_as_supplement(
                    gap_ms, ""  # 新文本尚未获取
                )
                # segment 会在 _do_interim_asr 中更新

            await sm.fire(InterviewEvent.SPEECH_RESUMED)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))
            # 重置新段起始
            self._current_segment_start_ms = now_ms

    async def _on_short_pause(self, vad_result: VADResult) -> None:
        """短暂停顿"""
        sm = self.state_machine
        if sm.can_fire(InterviewEvent.SHORT_PAUSE):
            await sm.fire(InterviewEvent.SHORT_PAUSE)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))
            # 短暂停顿不做任何判断，只更新状态

    async def _on_medium_pause(self, vad_result: VADResult) -> None:
        """中等停顿 — 开始评估是否结束"""
        sm = self.state_machine

        # 状态可能从 USER_SPEAKING 或 CANDIDATE_SHORT_PAUSE 进入
        if sm.state == InterviewState.USER_SPEAKING and sm.can_fire(InterviewEvent.SHORT_PAUSE):
            await sm.fire(InterviewEvent.SHORT_PAUSE)

        if sm.can_fire(InterviewEvent.LONG_PAUSE):
            # 跳到 LONG_PAUSE 状态
            pass  # 不直接转 long pause，等真正到 long pause 阈值再转

        # 做一次批量 ASR 获取当前文本
        await self._do_interim_asr()

        # 边界检测
        if self.boundary_detector and vad_result.silence_event:
            decision = await self.boundary_detector.evaluate(
                silence_event=vad_result.silence_event,
                current_transcript=self._current_transcript,
                question=self.memory.current_ctx.current_question or "",
            )
            if decision.action == BoundaryAction.FINALIZE:
                await self._finalize_answer()

    async def _on_long_pause(self, vad_result: VADResult) -> None:
        """长停顿 — 更积极的边界检测"""
        sm = self.state_machine

        # 尝试转到 CANDIDATE_LONG_PAUSE
        if sm.can_fire(InterviewEvent.LONG_PAUSE):
            await sm.fire(InterviewEvent.LONG_PAUSE)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))

        # 做 ASR
        await self._do_interim_asr()

        # 边界检测
        if self.boundary_detector and vad_result.silence_event:
            decision = await self.boundary_detector.evaluate(
                silence_event=vad_result.silence_event,
                current_transcript=self._current_transcript,
                question=self.memory.current_ctx.current_question or "",
            )

            if decision.action == BoundaryAction.FINALIZE:
                await self._finalize_answer()
            elif decision.action == BoundaryAction.PROMPT_CONTINUE:
                await self._send_nudge(decision.answer_complete_estimate)

    async def _on_extended_silence(self, vad_result: VADResult) -> None:
        """超长沉默 — 强制结束当前轮"""
        sm = self.state_machine

        # 确保状态正确
        if sm.state == InterviewState.USER_SPEAKING and sm.can_fire(InterviewEvent.EXTENDED_SILENCE):
            await self._do_interim_asr()
            await sm.fire(InterviewEvent.EXTENDED_SILENCE)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))
            await self._process_answer()
        elif sm.is_in_pause():
            if sm.can_fire(InterviewEvent.EXTENDED_SILENCE):
                await self._do_interim_asr()
                await sm.fire(InterviewEvent.EXTENDED_SILENCE)
                await self._send(ServerMessage.state_changed(
                    sm.state.value, self.memory.global_ctx.round_no
                ))
                await self._process_answer()
            elif sm.can_fire(InterviewEvent.BOUNDARY_CONFIRMED):
                await self._finalize_answer()

    async def _finalize_answer(self) -> None:
        """确认回答结束，触发处理流程"""
        sm = self.state_machine
        if sm.can_fire(InterviewEvent.BOUNDARY_CONFIRMED):
            await self._do_interim_asr()  # 确保最新文本
            await self._flush_current_segment()
            await sm.fire(InterviewEvent.BOUNDARY_CONFIRMED)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))
            await self._send(ServerMessage.answer_boundary(
                self.memory.global_ctx.round_no
            ))
            await self._process_answer()

    async def _do_interim_asr(self) -> None:
        """对当前缓冲区做一次批量 ASR"""
        try:
            audio_data = self.audio_buffer.get_all()
            if not audio_data or len(audio_data) < 100:
                return
            result = await self.asr.transcribe(audio_data)
            if result and result.text:
                self._current_transcript = result.text.strip()
                self._last_interim_transcript = self._current_transcript
                if self.boundary_detector:
                    self.boundary_detector.update_transcript(result.text)
        except Exception:
            logger.debug("临时 ASR 转写失败 session=%s", self.session_id)

    async def _flush_current_segment(
        self,
        end_ms: int | None = None,
        gap_before_ms: int | None = None,
    ) -> None:
        if not self.segmentation:
            return
        await self._do_interim_asr()
        if not self._current_transcript.strip():
            return
        if end_ms is None:
            end_ms = int((time.monotonic() - self._question_start_time) * 1000) \
                if self._question_start_time else 0
        if gap_before_ms is None:
            gap_before_ms = (
                self._current_segment_start_ms - self._last_segment_end_ms
                if self._last_segment_end_ms and self._current_segment_start_ms
                else 0
            )

        segment = self.segmentation.append_from_transcript(
            transcript=self._current_transcript,
            start_ms=self._current_segment_start_ms,
            end_ms=end_ms,
            gap_before_ms=max(0, gap_before_ms),
        )
        if segment:
            self._last_segment_end_ms = segment.end_ms

    async def _send_nudge(self, completeness_estimate: str = "low") -> None:
        """发送沉默提醒"""
        sm = self.state_machine
        settings = self.settings

        # 检查限制
        if self._silence_reminder_count >= settings.max_silence_reminders:
            logger.info("已达最大提醒次数，结束当前回答 session=%s", self.session_id)
            await self._finalize_answer()
            return

        now = time.monotonic()
        if now - self._last_nudge_time < settings.silence_prompt_interval_ms / 1000:
            return  # 提醒间隔不足

        # 生成提醒话术
        prompt_decision = await self.silence_prompt_decider.decide(
            question=self.memory.current_ctx.current_question or "",
            transcript=self._current_transcript,
            silence_duration_ms=self.vad.silence_duration_ms,
            reminder_count=self._silence_reminder_count,
            completeness_estimate=completeness_estimate,
            question_type="technical",
        ) if self.silence_prompt_decider else None

        if prompt_decision and not prompt_decision.should_prompt:
            if prompt_decision.next_action_if_no_response == "end_current_answer":
                await self._finalize_answer()
            return

        nudge_text = (
            prompt_decision.prompt_text
            if prompt_decision and prompt_decision.prompt_text
            else await self._generate_nudge()
        )

        self._silence_reminder_count += 1
        self._last_nudge_time = now

        if self.boundary_detector:
            self.boundary_detector.mark_prompted()

        # 发送提醒（通过 NUDGE_SENT 转到 INTERVIEWER_SPEAKING，然后 speak_done 后回到等待）
        if sm.can_fire(InterviewEvent.NUDGE_SENT):
            await sm.fire(InterviewEvent.NUDGE_SENT)
            await self._send(self._build_speak_message(nudge_text, is_question=False))
            await self._send(ServerMessage.silence_nudge(nudge_text, self._silence_reminder_count))
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))
        else:
            # 无法通过状态机发送，直接发文本提醒
            await self._send(ServerMessage.silence_nudge(nudge_text, self._silence_reminder_count))

    def _cancel_pending_finalize(self) -> None:
        """取消待执行的答案处理"""
        if self._pending_finalize_task and not self._pending_finalize_task.done():
            self._pending_finalize_task.cancel()
            self._pending_finalize_task = None

    # ============================================================
    # 旧模式：兼容手动开关麦
    # ============================================================

    async def _handle_audio_legacy(self, vad_result: VADResult) -> None:
        """旧模式下的音频事件处理（兼容）"""
        sm = self.state_machine
        event = vad_result.event

        if event == VADEvent.SPEECH_START:
            if sm.can_fire(InterviewEvent.USER_STARTED):
                self._cancel_silence_timer()
                await sm.fire(InterviewEvent.USER_STARTED)
                await self._send(ServerMessage.state_changed(
                    sm.state.value, self.memory.global_ctx.round_no
                ))

        elif event == VADEvent.ENDPOINT:
            if sm.can_fire(InterviewEvent.USER_STOPPED):
                await sm.fire(InterviewEvent.USER_STOPPED)
                await sm.fire(InterviewEvent.ENDPOINT_CONFIRMED)
                await self._send(ServerMessage.state_changed(
                    "answer_analyzing", self.memory.global_ctx.round_no
                ))
                asyncio.create_task(self._process_answer_legacy())

    async def _process_answer_legacy(self) -> None:
        """旧模式处理回答"""
        try:
            sm = self.state_machine

            audio_data = self.audio_buffer.get_all()
            result = await self.asr.transcribe(audio_data)
            transcript = result.text
            logger.info("ASR 转写 session=%s: %s", self.session_id, transcript[:80])

            self.memory.set_current_answer(transcript)

            features = self.feature_extractor.analyze(audio_data, transcript)
            self._audio_features.append(features)

            analysis = await self._analyze_answer(transcript)
            self._analysis_results.append(analysis)

            self.memory.set_answer_analysis(
                summary=analysis.get("answer_summary", transcript[:80]),
                followup_points=analysis.get("followup_points", []),
                weakness_tags=analysis.get("problems", []),
            )

            if not transcript.strip() or len(transcript.strip()) < 5:
                self._consecutive_empty += 1
            else:
                self._consecutive_empty = 0

            await sm.fire(InterviewEvent.ANALYSIS_DONE)

            decision = await self._make_decision(analysis)
            decision_type = decision.get("decision", "follow_up")

            self.memory.commit_round(
                decision=decision_type,
                score_hint=analysis.get("technical_correctness", "medium"),
            )
            self._rounds.append({
                "round_no": self.memory.global_ctx.round_no,
                "question": self.memory.current_ctx.current_question,
                "answer_transcript": transcript,
                "analysis": analysis,
                "decision": decision,
                "audio_features": {
                    "speech_rate_wpm": features.speech_rate_wpm,
                    "pause_ratio": features.pause_ratio,
                    "confidence_score": features.confidence_score,
                    "fluency_score": features.fluency_score,
                },
            })

            if decision_type == "wrap_up" or self._consecutive_empty >= 3:
                await sm.fire(InterviewEvent.WRAP_UP)
                closing_text = await self._generate_closing()
                await self._send(self._build_speak_message(closing_text, is_question=False))
                await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))
            elif decision_type == "switch_topic":
                await sm.fire(InterviewEvent.SWITCH_TOPIC)
                self.memory.advance_round()
                next_text = await self._generate_switch_topic(decision)
                self.memory.set_current_question(next_text, decision.get("target_competency", ""))
                await self._send(self._build_speak_message(next_text, is_question=True))
                await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))
            else:
                await sm.fire(InterviewEvent.FOLLOW_UP)
                followup_text = await self._generate_followup(decision, analysis)
                self.memory.set_current_question(followup_text)
                await self._send(self._build_speak_message(followup_text, is_question=True))
                await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))

            self.audio_buffer.clear()
            self.vad.reset()

        except Exception:
            logger.exception("处理回答异常 session=%s", self.session_id)
            await self._send(ServerMessage.error("process_error", "回答处理异常，请重试"))

    # ============================================================
    # 持续模式：回答处理
    # ============================================================

    async def _process_answer(self) -> None:
        """持续模式处理回答：ASR → 切分 → 分析 → 决策 → 下一步"""
        try:
            sm = self.state_machine

            # 1. 最终 ASR 转写
            audio_data = self.audio_buffer.get_all()
            result = await self.asr.transcribe(audio_data)
            transcript = result.text if result else self._current_transcript
            logger.info("ASR 最终转写 session=%s: %s", self.session_id, transcript[:80])

            # 2. 保存最后一个 segment
            self._current_transcript = transcript.strip()

            # 使用切分后的文本
            final_transcript = self.segmentation.get_analysis_ready_text() \
                if self.segmentation else transcript

            self.memory.set_current_answer(final_transcript)

            # 3. 音频特征分析
            features = self.feature_extractor.analyze(audio_data, final_transcript)
            self._audio_features.append(features)

            # 4. 回答分析
            analysis = await self._analyze_answer(final_transcript)
            self._analysis_results.append(analysis)

            self.memory.set_answer_analysis(
                summary=analysis.get("answer_summary", final_transcript[:80]),
                followup_points=analysis.get("followup_points", []),
                weakness_tags=analysis.get("problems", []),
            )

            # 检查空回答
            if not final_transcript.strip() or len(final_transcript.strip()) < 5:
                self._consecutive_empty += 1
            else:
                self._consecutive_empty = 0

            # 5. ANALYSIS_DONE → FOLLOWUP_DECIDING
            await sm.fire(InterviewEvent.ANALYSIS_DONE)
            await self._send(ServerMessage.state_changed(
                sm.state.value, self.memory.global_ctx.round_no
            ))

            # 6. 决策
            decision = await self._make_decision(analysis)
            decision_type = decision.get("decision", "follow_up")

            # 提交轮次
            self.memory.commit_round(
                decision=decision_type,
                score_hint=analysis.get("technical_correctness", "medium"),
            )

            round_data = {
                "round_no": self.memory.global_ctx.round_no,
                "question": self.memory.current_ctx.current_question,
                "answer_transcript": final_transcript,
                "analysis": analysis,
                "decision": decision,
                "audio_features": {
                    "speech_rate_wpm": features.speech_rate_wpm,
                    "pause_ratio": features.pause_ratio,
                    "confidence_score": features.confidence_score,
                    "fluency_score": features.fluency_score,
                },
            }
            if self.segmentation:
                round_data["segmentation"] = self.segmentation.get_segment_metadata()
            self._rounds.append(round_data)

            # 7. 根据决策生成下一步
            if decision_type == "wrap_up" or self._consecutive_empty >= 3:
                await sm.fire(InterviewEvent.WRAP_UP)
                closing_text = await self._generate_closing()
                await self._send(self._build_speak_message(closing_text, is_question=False))
                await self._send(ServerMessage.state_changed(
                    sm.state.value, self.memory.global_ctx.round_no
                ))
            elif decision_type == "switch_topic":
                await sm.fire(InterviewEvent.SWITCH_TOPIC)
                self.memory.advance_round()
                next_text = await self._generate_switch_topic(decision)
                self.memory.set_current_question(next_text, decision.get("target_competency", ""))
                await self._send(self._build_speak_message(next_text, is_question=True))
                await self._send(ServerMessage.state_changed(
                    sm.state.value, self.memory.global_ctx.round_no
                ))
            else:
                await sm.fire(InterviewEvent.FOLLOW_UP)
                followup_text = await self._generate_followup(decision, analysis)
                self.memory.set_current_question(followup_text)
                await self._send(self._build_speak_message(followup_text, is_question=True))
                await self._send(ServerMessage.state_changed(
                    sm.state.value, self.memory.global_ctx.round_no
                ))

            # 8. 重置本轮状态
            self._reset_round_state()

        except Exception:
            logger.exception("处理回答异常 session=%s", self.session_id)
            await self._send(ServerMessage.error("process_error", "回答处理异常，请重试"))

    def _reset_round_state(self) -> None:
        """重置本轮运行时状态"""
        self.audio_buffer.clear()
        self.vad.reset()
        self._silence_reminder_count = 0
        self._last_nudge_time = 0
        self._current_transcript = ""
        self._last_interim_transcript = ""
        self._current_segment_start_ms = 0
        self._last_segment_end_ms = 0
        if self.boundary_detector:
            self.boundary_detector.reset()
        if self.segmentation:
            self.segmentation.reset()

    # ============================================================
    # 面试结束
    # ============================================================

    async def _finish_interview(self) -> dict:
        """结束面试并生成报告"""
        sm = self.state_machine

        # 尝试迁移到 CLOSING/FINISHED
        if sm.state == InterviewState.CLOSING:
            await sm.fire(InterviewEvent.CLOSING_DONE)
        elif sm.state == InterviewState.INTERVIEW_ENDING:
            await sm.fire(InterviewEvent.CLOSING_DONE)  # → CLOSING
            await sm.fire(InterviewEvent.CLOSING_DONE)  # → FINISHED
        elif sm.can_fire(InterviewEvent.WRAP_UP):
            await sm.fire(InterviewEvent.WRAP_UP)
            if sm.state == InterviewState.INTERVIEW_ENDING:
                await sm.fire(InterviewEvent.CLOSING_DONE)
                await sm.fire(InterviewEvent.CLOSING_DONE)
            elif sm.state == InterviewState.CLOSING:
                await sm.fire(InterviewEvent.CLOSING_DONE)
        else:
            sm._state = InterviewState.FINISHED

        report = await self._generate_report()
        await self._send(ServerMessage.report_ready(report))
        await self._send(ServerMessage.state_changed("finished", self.memory.global_ctx.round_no))

        logger.info("面试结束 session=%s rounds=%d", self.session_id, len(self._rounds))
        return report

    # ============================================================
    # LLM 调用
    # ============================================================

    async def _call_llm(self, system_prompt: str, user_content: str, expect_json: bool = False) -> str:
        """调用 LLM"""
        settings = self.settings
        if not settings.llm_ready:
            logger.warning("LLM 未配置，返回 mock 响应 | session=%s", self.session_id)
            self._degraded = True
            return self._mock_llm_response(expect_json)

        import httpx
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        body: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
        }
        if expect_json:
            body["response_format"] = {"type": "json_object"}

        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}

        def _sync_call() -> str:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    headers=headers,
                    json=body,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync_call)

    def _mock_llm_response(self, expect_json: bool) -> str:
        if expect_json:
            return json.dumps({
                "answer_summary": "候选人给出了基本回答",
                "is_off_topic": False,
                "is_generic": False,
                "answered_core_question": True,
                "technical_correctness": "medium",
                "completeness": "medium",
                "logic_clarity": "medium",
                "authenticity_risk": "low",
                "star_level": "medium",
                "covered_competencies": [],
                "evidence_points": [],
                "problems": [],
                "followup_points": ["可以追问更多细节"],
                "should_followup": True,
                "suggested_followup_type": "deepen_detail",
            }, ensure_ascii=False)
        return "好的，我了解了。那我再追问一下，这部分具体是怎么实现的？"

    # ============================================================
    # LLM 生成方法
    # ============================================================

    async def _generate_opening(self) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_opening")
            user_content = prompt.replace("{{ job_name }}", self.job_name)
            if self.resume_summary:
                user_content = user_content.replace("{{ resume_summary }}", self.resume_summary)
            else:
                user_content = user_content.replace("{{ resume_summary }}", "未提供简历")
            return await self._call_llm(system_prompt, user_content)
        except Exception:
            logger.warning("生成开场白失败 | session=%s", self.session_id)
            self._degraded = True
            return f"你好，欢迎来到今天的面试。我是面试官，今天主要围绕{self.job_name}岗位的相关技术来交流。准备好了的话我们就开始吧。"

    async def _generate_first_question(self) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_first_question")
            context = self.memory.build_llm_context()
            user_content = prompt.replace("{{ context }}", context)
            return await self._call_llm(system_prompt, user_content)
        except Exception:
            logger.warning("生成首题失败 | session=%s", self.session_id)
            self._degraded = True
            if self.resume_summary:
                return "我看了你的简历，先从你最近的一个项目开始聊吧，简单介绍一下你在这个项目中具体负责什么。"
            return f"先从基础开始，你觉得{self.job_name}最核心的技术能力是什么？结合你的经验说一下。"

    async def _analyze_answer(self, transcript: str) -> dict:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_answer_analysis")
            user_content = prompt.replace("{{ context }}", self.memory.build_llm_context())
            user_content = user_content.replace("{{ answer_transcript }}", transcript)
            raw = await self._call_llm(system_prompt, user_content, expect_json=True)
            return parse_json(raw)
        except Exception:
            logger.warning("回答分析失败 | session=%s", self.session_id)
            self._degraded = True
            return {
                "answer_summary": transcript[:80],
                "is_off_topic": False,
                "is_generic": len(transcript) < 30,
                "answered_core_question": True,
                "technical_correctness": "medium",
                "completeness": "medium",
                "logic_clarity": "medium",
                "authenticity_risk": "low",
                "followup_points": [],
                "should_followup": True,
                "suggested_followup_type": "deepen_detail",
            }

    async def _make_decision(self, analysis: dict) -> dict:
        if self.memory.should_wrap_up():
            return {"decision": "wrap_up", "reason": "已达到轮次上限或覆盖度足够"}
        if self._consecutive_empty >= 3:
            return {"decision": "wrap_up", "reason": "连续3轮无有效回答"}

        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_decision")
            ctx = self.memory.build_decision_context()
            ctx["current_analysis"] = analysis
            user_content = prompt.replace("{{ context }}", json.dumps(ctx, ensure_ascii=False, indent=2))
            raw = await self._call_llm(system_prompt, user_content, expect_json=True)
            return parse_json(raw)
        except Exception:
            logger.warning("决策失败 | session=%s", self.session_id)
            self._degraded = True
            if analysis.get("should_followup"):
                return {
                    "decision": "follow_up",
                    "followup_type": analysis.get("suggested_followup_type", "deepen_detail"),
                    "reason": "默认追问",
                }
            return {
                "decision": "switch_topic",
                "target_competency": (self.memory.global_ctx.uncovered_competencies or [""])[0],
                "reason": "当前维度信息充分，切换话题",
            }

    async def _generate_followup(self, decision: dict, analysis: dict) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_followup")
            user_content = prompt.replace("{{ context }}", self.memory.build_llm_context())
            user_content = user_content.replace(
                "{{ followup_type }}", decision.get("followup_type", "deepen_detail"))
            return await self._call_llm(system_prompt, user_content)
        except Exception:
            logger.warning("生成追问失败 | session=%s", self.session_id)
            self._degraded = True
            ftype = decision.get("followup_type", "deepen_detail")
            templates = {
                "deepen_detail": "这块能再展开说一下吗？具体是怎么做的。",
                "verify_authenticity": "这个是你独立完成的还是团队协作？你具体负责哪部分？",
                "redirect_back": "我理解你说的，不过我们还是回到刚才的问题，你能再针对性地说一下吗？",
                "ask_for_example": "能举一个具体的例子吗？",
                "quantify_result": "有没有具体的数据或指标可以说明效果？",
            }
            return templates.get(ftype, "这块能再具体说一下吗？")

    async def _generate_switch_topic(self, decision: dict) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_switch_topic")
            user_content = prompt.replace("{{ context }}", self.memory.build_llm_context())
            user_content = user_content.replace(
                "{{ target_competency }}", decision.get("target_competency", ""))
            return await self._call_llm(system_prompt, user_content)
        except Exception:
            logger.warning("生成换题话术失败 | session=%s", self.session_id)
            self._degraded = True
            comp = decision.get("target_competency", "其他方面")
            return f"好的，这个方向我了解了。我们换个话题，聊一下{comp}相关的内容。"

    async def _generate_closing(self) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_closing")
            user_content = prompt.replace("{{ context }}", self.memory.build_llm_context())
            return await self._call_llm(system_prompt, user_content)
        except Exception:
            logger.warning("生成结束语失败 | session=%s", self.session_id)
            self._degraded = True
            return "好，今天的面试就到这里。整体聊下来我对你有了基本的了解，感谢你的时间。稍后可以在页面上查看详细的面试报告。"

    async def _generate_nudge(self) -> str:
        """生成沉默提醒话术（持续模式专用）"""
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_silence_nudge")

            user_content = prompt
            user_content = user_content.replace(
                "{{ question }}", self.memory.current_ctx.current_question or "")
            user_content = user_content.replace(
                "{{ transcript }}", self._current_transcript or "(尚未说话)")
            user_content = user_content.replace(
                "{{ silence_duration_ms }}", str(self.vad.silence_duration_ms))
            user_content = user_content.replace(
                "{{ reminder_count }}", str(self._silence_reminder_count))
            user_content = user_content.replace(
                "{{ completeness_estimate }}",
                "low" if len(self._current_transcript) < 30 else "medium")
            user_content = user_content.replace("{{ question_type }}", "technical")

            raw = await self._call_llm(system_prompt, user_content, expect_json=True)
            result = parse_json(raw)
            return result.get("prompt_text", "你可以继续想一想，想到什么说什么就好。")
        except Exception:
            logger.warning("生成沉默提醒失败 | session=%s", self.session_id)
            nudge_templates = [
                "你可以直接说，没关系，想到什么说什么就好。",
                "如果你回答完了，我会继续下一个问题。",
                "你也可以结合你的项目经验来说。",
            ]
            idx = min(self._silence_reminder_count, len(nudge_templates) - 1)
            return nudge_templates[idx]

    async def _generate_report(self) -> dict:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_final_report")
            report_data = {
                "job_name": self.job_name,
                "style": self.style,
                "total_rounds": len(self._rounds),
                "rounds": self._rounds,
                "covered_competencies": self.memory.global_ctx.covered_competencies,
                "weakness_tags": self.memory.global_ctx.weakness_tags,
            }
            user_content = prompt.replace(
                "{{ report_data }}", json.dumps(report_data, ensure_ascii=False, indent=2))
            raw = await self._call_llm(system_prompt, user_content, expect_json=True)
            report = parse_json(raw)
            report["degraded"] = self._degraded
            return report
        except Exception:
            logger.warning("报告生成失败 | session=%s", self.session_id)
            return self._build_default_report()

    # ============================================================
    # 辅助方法
    # ============================================================

    def _build_system_prompt(self) -> str:
        parts = []
        try:
            parts.append(self.prompt_provider.load("voice_system"))
        except Exception:
            parts.append(self._default_system_prompt())
        try:
            parts.append(self.prompt_provider.load("voice_style_constraints"))
        except Exception:
            pass
        try:
            parts.append(self.prompt_provider.load("voice_length_constraints"))
        except Exception:
            pass
        return "\n\n".join(parts)

    def _default_system_prompt(self) -> str:
        profile = get_difficulty_profile(self.style)
        style_name = self.style_config.get("style_name") or profile.voice_style_name
        tone = self.style_config.get("tone") or profile.prompt_hint
        return f"""你是一位经验丰富的技术面试官，正在对候选人进行{self.job_name}岗位的面试。
面试难度：{style_name}。
适合人群：{profile.audience_hint}。
当前要求：{tone}

核心规则：
1. 用真人面试官的口吻说话，简洁、直接、自然
2. 每次只问一个问题，不超过3句话、45个汉字
3. 所有输出用于语音播报，不要使用 markdown、列表、括号等书面格式
4. 禁止说"根据你的回答""系统检测到""你的评分是"等机器人表达
5. 像真人一样自然过渡："好的""我明白了""那我追问一下"
"""

    def _load_job_config(self, job_name: str) -> dict:
        import yaml
        config_dir = get_settings().data_dir.parent / "backend" / "app" / "config" / "jobs"
        for name in ["cpp_backend", "web_frontend"]:
            path = config_dir / f"{name}.yaml"
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    if cfg and cfg.get("job_name") == job_name:
                        return cfg
        return {}

    def _load_style_config(self, style: str) -> dict:
        import yaml
        config_dir = get_settings().data_dir.parent / "backend" / "app" / "config" / "styles"
        path = config_dir / f"{style}.yaml"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def _start_silence_timer(self) -> None:
        self._cancel_silence_timer()

        timeout = 30 if self.continuous_mode else 10

        async def _timer():
            await asyncio.sleep(timeout)
            sm = self.state_machine
            if sm and sm.can_fire(InterviewEvent.SILENCE_TIMEOUT):
                logger.info("用户超时未说话 session=%s", self.session_id)
                await sm.fire(InterviewEvent.SILENCE_TIMEOUT)
                reminder = await self._generate_silence_reminder()
                await self._send(self._build_speak_message(reminder, is_question=False))
                await self._send(ServerMessage.state_changed(sm.state.value, self.memory.global_ctx.round_no))

        self._silence_timer = asyncio.create_task(_timer())

    def _cancel_silence_timer(self) -> None:
        if self._silence_timer and not self._silence_timer.done():
            self._silence_timer.cancel()
            self._silence_timer = None

    async def _generate_silence_reminder(self) -> str:
        try:
            system_prompt = self._build_system_prompt()
            prompt = self.prompt_provider.load("voice_silence_recovery")
            return await self._call_llm(system_prompt, prompt)
        except Exception:
            return "你可以直接回答，没关系，想到什么说什么就好。"

    async def _send(self, msg: ServerMessage) -> None:
        await self.ws_mgr.send_to(self.session_id, msg)

    def _build_speak_message(self, text: str, is_question: bool) -> ServerMessage:
        if not self.tts:
            return ServerMessage.interviewer_speak(text, is_question=is_question)
        try:
            audio = self.tts.synthesize(text)
            return ServerMessage.interviewer_speak(
                text,
                is_question=is_question,
                audio_base64=audio.audio_base64,
                mime_type=audio.mime_type,
            )
        except Exception:
            logger.exception("TTS synthesis failed | session_id=%s", self.session_id)
            return ServerMessage.interviewer_speak(text, is_question=is_question)

    def _build_default_report(self) -> dict:
        return {
            "overall_comment": "面试报告生成失败，以下为默认结果，不代表真实评估。",
            "overall_score": 0,
            "dimension_scores": {
                "accuracy": 0,
                "completeness": 0,
                "logic": 0,
                "job_fit": 0,
                "credibility": 0,
                "speech_confidence": 0,
                "speech_clarity": 0,
                "speech_fluency": 0,
                "emotion_stability": 0,
            },
            "strengths": [],
            "major_issues": ["报告由系统默认生成，AI 评估未成功完成"],
            "weakness_tags": self.memory.global_ctx.weakness_tags if self.memory else [],
            "authenticity_risks": [],
            "improvement_suggestions": [],
            "next_training_plan": [],
            "degraded": True,
        }


# ---- 会话管理 ----
_active_orchestrators: dict[str, InterviewOrchestratorService] = {}


def get_orchestrator(session_id: str) -> InterviewOrchestratorService | None:
    return _active_orchestrators.get(session_id)


def register_orchestrator(session_id: str, orch: InterviewOrchestratorService) -> None:
    _active_orchestrators[session_id] = orch


def remove_orchestrator(session_id: str) -> None:
    _active_orchestrators.pop(session_id, None)

"""
面试状态机 — 驱动整个语音面试流程的核心骨架。
增强版：支持持续语音对话模式的细粒度状态和转换。
"""

from __future__ import annotations

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class InterviewState(str, Enum):
    """面试状态枚举"""
    INTERVIEW_INIT = "idle"
    IDLE = "idle"
    PREPARING = "preparing"
    OPENING = "opening"
    INTERVIEWER_SPEAKING = "interviewer_speaking"
    WAITING_FOR_CANDIDATE_SPEECH = "user_waiting"
    USER_WAITING = "user_waiting"
    CANDIDATE_SPEAKING = "user_speaking"
    USER_SPEAKING = "user_speaking"
    # ---- 持续模式新增状态 ----
    CANDIDATE_SHORT_PAUSE = "candidate_short_pause"     # 候选人短暂停顿
    CANDIDATE_LONG_PAUSE = "candidate_long_pause"       # 候选人长停顿
    ANSWER_FINALIZING = "answer_finalizing"              # 确认回答结束，准备评分
    FOLLOWUP_DECIDING = "followup_deciding"              # 判断是否追问
    ASKING_FOLLOWUP = "asking_followup"                  # 正在追问
    ASKING_NEXT_QUESTION = "asking_next_question"        # 正在提下一题
    INTERVIEW_ENDING = "interview_ending"                # 面试即将结束
    INTERVIEW_ABORTED = "interview_aborted"              # 面试异常中止
    # ---- 旧模式兼容 ----
    ENDPOINT_DETECTING = "endpoint_detecting"
    ANSWER_ANALYZING = "answer_analyzing"
    DECISION_MAKING = "decision_making"
    CLOSING = "closing"
    FINISHED = "finished"


class InterviewEvent(str, Enum):
    """触发状态迁移的事件"""
    PREPARE = "prepare"
    PREPARED = "prepared"
    OPENING_DONE = "opening_done"
    SPEAK_DONE = "speak_done"
    USER_STARTED = "user_started"
    SILENCE_TIMEOUT = "silence_timeout"
    USER_STOPPED = "user_stopped"
    ENDPOINT_CONFIRMED = "endpoint_confirmed"
    SPEECH_RESUMED = "speech_resumed"
    ANALYSIS_DONE = "analysis_done"
    FOLLOW_UP = "follow_up"
    SWITCH_TOPIC = "switch_topic"
    WRAP_UP = "wrap_up"
    CLOSING_DONE = "closing_done"
    # ---- 持续模式新增事件 ----
    SHORT_PAUSE = "short_pause"                 # 检测到短暂停顿
    LONG_PAUSE = "long_pause"                   # 检测到长停顿
    EXTENDED_SILENCE = "extended_silence"        # 检测到超长沉默
    BOUNDARY_CONFIRMED = "boundary_confirmed"   # 确认回答结束
    NUDGE_SENT = "nudge_sent"                   # 已发送沉默提醒
    NUDGE_DONE = "nudge_done"                   # 提醒播报完毕
    FOLLOWUP_DECIDED = "followup_decided"       # 追问决策完成
    NEXT_QUESTION_DECIDED = "next_question_decided"  # 下一题决策完成
    ABORT = "abort"                             # 异常中止


@dataclass
class Transition:
    """状态迁移定义"""
    source: InterviewState
    event: InterviewEvent
    target: InterviewState


# ---- 迁移表 ----
TRANSITIONS: list[Transition] = [
    # === 初始化 & 开场 ===
    Transition(InterviewState.IDLE, InterviewEvent.PREPARE, InterviewState.PREPARING),
    Transition(InterviewState.PREPARING, InterviewEvent.PREPARED, InterviewState.OPENING),
    Transition(InterviewState.OPENING, InterviewEvent.OPENING_DONE, InterviewState.INTERVIEWER_SPEAKING),

    # === 面试官说话 → 等待用户 ===
    Transition(InterviewState.INTERVIEWER_SPEAKING, InterviewEvent.SPEAK_DONE, InterviewState.USER_WAITING),
    Transition(InterviewState.ASKING_FOLLOWUP, InterviewEvent.SPEAK_DONE, InterviewState.USER_WAITING),
    Transition(InterviewState.ASKING_NEXT_QUESTION, InterviewEvent.SPEAK_DONE, InterviewState.USER_WAITING),

    # === 用户开始说话 ===
    Transition(InterviewState.USER_WAITING, InterviewEvent.USER_STARTED, InterviewState.USER_SPEAKING),
    Transition(InterviewState.USER_WAITING, InterviewEvent.SILENCE_TIMEOUT, InterviewState.INTERVIEWER_SPEAKING),

    # === 持续模式：说话 → 停顿 → 恢复 ===
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.SHORT_PAUSE, InterviewState.CANDIDATE_SHORT_PAUSE),
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.LONG_PAUSE, InterviewState.CANDIDATE_LONG_PAUSE),
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.EXTENDED_SILENCE, InterviewState.ANSWER_FINALIZING),
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.BOUNDARY_CONFIRMED, InterviewState.ANSWER_FINALIZING),

    # 短暂停顿
    Transition(InterviewState.CANDIDATE_SHORT_PAUSE, InterviewEvent.SPEECH_RESUMED, InterviewState.USER_SPEAKING),
    Transition(InterviewState.CANDIDATE_SHORT_PAUSE, InterviewEvent.LONG_PAUSE, InterviewState.CANDIDATE_LONG_PAUSE),
    Transition(InterviewState.CANDIDATE_SHORT_PAUSE, InterviewEvent.EXTENDED_SILENCE, InterviewState.ANSWER_FINALIZING),
    Transition(InterviewState.CANDIDATE_SHORT_PAUSE, InterviewEvent.BOUNDARY_CONFIRMED, InterviewState.ANSWER_FINALIZING),

    # 长停顿
    Transition(InterviewState.CANDIDATE_LONG_PAUSE, InterviewEvent.SPEECH_RESUMED, InterviewState.USER_SPEAKING),
    Transition(InterviewState.CANDIDATE_LONG_PAUSE, InterviewEvent.BOUNDARY_CONFIRMED, InterviewState.ANSWER_FINALIZING),
    Transition(InterviewState.CANDIDATE_LONG_PAUSE, InterviewEvent.EXTENDED_SILENCE, InterviewState.ANSWER_FINALIZING),
    Transition(InterviewState.CANDIDATE_LONG_PAUSE, InterviewEvent.NUDGE_SENT, InterviewState.INTERVIEWER_SPEAKING),

    # === 回答结束 → 分析 → 决策 ===
    Transition(InterviewState.ANSWER_FINALIZING, InterviewEvent.ANALYSIS_DONE, InterviewState.FOLLOWUP_DECIDING),
    Transition(InterviewState.ANSWER_FINALIZING, InterviewEvent.SPEECH_RESUMED, InterviewState.USER_SPEAKING),

    # 追问决策
    Transition(InterviewState.FOLLOWUP_DECIDING, InterviewEvent.FOLLOW_UP, InterviewState.ASKING_FOLLOWUP),
    Transition(InterviewState.FOLLOWUP_DECIDING, InterviewEvent.SWITCH_TOPIC, InterviewState.ASKING_NEXT_QUESTION),
    Transition(InterviewState.FOLLOWUP_DECIDING, InterviewEvent.WRAP_UP, InterviewState.INTERVIEW_ENDING),

    # === 面试结束 ===
    Transition(InterviewState.INTERVIEW_ENDING, InterviewEvent.CLOSING_DONE, InterviewState.CLOSING),
    Transition(InterviewState.CLOSING, InterviewEvent.CLOSING_DONE, InterviewState.FINISHED),

    # === 异常中止（从任意关键状态） ===
    Transition(InterviewState.USER_WAITING, InterviewEvent.ABORT, InterviewState.INTERVIEW_ABORTED),
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.ABORT, InterviewState.INTERVIEW_ABORTED),
    Transition(InterviewState.CANDIDATE_SHORT_PAUSE, InterviewEvent.ABORT, InterviewState.INTERVIEW_ABORTED),
    Transition(InterviewState.CANDIDATE_LONG_PAUSE, InterviewEvent.ABORT, InterviewState.INTERVIEW_ABORTED),
    Transition(InterviewState.INTERVIEWER_SPEAKING, InterviewEvent.ABORT, InterviewState.INTERVIEW_ABORTED),

    # === 旧模式兼容（非持续模式仍可用） ===
    Transition(InterviewState.USER_SPEAKING, InterviewEvent.USER_STOPPED, InterviewState.ENDPOINT_DETECTING),
    Transition(InterviewState.ENDPOINT_DETECTING, InterviewEvent.ENDPOINT_CONFIRMED, InterviewState.ANSWER_ANALYZING),
    Transition(InterviewState.ENDPOINT_DETECTING, InterviewEvent.SPEECH_RESUMED, InterviewState.USER_SPEAKING),
    Transition(InterviewState.ANSWER_ANALYZING, InterviewEvent.ANALYSIS_DONE, InterviewState.DECISION_MAKING),
    Transition(InterviewState.DECISION_MAKING, InterviewEvent.FOLLOW_UP, InterviewState.INTERVIEWER_SPEAKING),
    Transition(InterviewState.DECISION_MAKING, InterviewEvent.SWITCH_TOPIC, InterviewState.INTERVIEWER_SPEAKING),
    Transition(InterviewState.DECISION_MAKING, InterviewEvent.WRAP_UP, InterviewState.CLOSING),
]

# 构建查找表: (source, event) -> target
_TRANSITION_MAP: dict[tuple[InterviewState, InterviewEvent], InterviewState] = {
    (t.source, t.event): t.target for t in TRANSITIONS
}


class IllegalTransitionError(Exception):
    """非法状态迁移"""

    def __init__(self, state: InterviewState, event: InterviewEvent):
        self.state = state
        self.event = event
        super().__init__(f"非法迁移: 状态 {state.value} 不接受事件 {event.value}")


# 回调类型
StateCallback = Callable[[InterviewState], Awaitable[None]] | Callable[[InterviewState], None]


class InterviewStateMachine:
    """
    面试状态机。
    - 通过 fire(event) 触发迁移
    - 每次迁移触发 on_exit / on_enter 回调
    - 非法迁移抛 IllegalTransitionError
    """

    def __init__(self, session_id: str, initial_state: InterviewState = InterviewState.IDLE):
        self._session_id = session_id
        self._state = initial_state
        self._on_enter: dict[InterviewState, list[StateCallback]] = {}
        self._on_exit: dict[InterviewState, list[StateCallback]] = {}
        self._global_on_transition: list[Callable] = []

    @property
    def state(self) -> InterviewState:
        return self._state

    @property
    def session_id(self) -> str:
        return self._session_id

    def on_enter(self, state: InterviewState, callback: StateCallback) -> None:
        self._on_enter.setdefault(state, []).append(callback)

    def on_exit(self, state: InterviewState, callback: StateCallback) -> None:
        self._on_exit.setdefault(state, []).append(callback)

    def on_transition(self, callback: Callable) -> None:
        self._global_on_transition.append(callback)

    async def fire(self, event: InterviewEvent) -> InterviewState:
        """
        触发事件，执行状态迁移。
        返回迁移后的新状态。
        """
        key = (self._state, event)
        target = _TRANSITION_MAP.get(key)
        if target is None:
            logger.error(
                "非法状态迁移 session=%s state=%s event=%s",
                self._session_id, self._state.value, event.value,
            )
            raise IllegalTransitionError(self._state, event)

        old_state = self._state
        logger.info(
            "状态迁移 session=%s: %s -[%s]-> %s",
            self._session_id, old_state.value, event.value, target.value,
        )

        # on_exit 回调
        for cb in self._on_exit.get(old_state, []):
            result = cb(old_state)
            if hasattr(result, "__await__"):
                await result

        self._state = target

        # on_enter 回调
        for cb in self._on_enter.get(target, []):
            result = cb(target)
            if hasattr(result, "__await__"):
                await result

        # 全局迁移回调
        for cb in self._global_on_transition:
            result = cb(old_state, event, target)
            if hasattr(result, "__await__"):
                await result

        return target

    def can_fire(self, event: InterviewEvent) -> bool:
        return (self._state, event) in _TRANSITION_MAP

    def allowed_events(self) -> list[InterviewEvent]:
        return [e for s, e in _TRANSITION_MAP if s == self._state]

    def is_finished(self) -> bool:
        return self._state in (InterviewState.FINISHED, InterviewState.INTERVIEW_ABORTED)

    def is_in_pause(self) -> bool:
        """是否处于候选人停顿状态"""
        return self._state in (
            InterviewState.CANDIDATE_SHORT_PAUSE,
            InterviewState.CANDIDATE_LONG_PAUSE,
        )

    def is_candidate_active(self) -> bool:
        """候选人是否在活跃回答中（说话或停顿）"""
        return self._state in (
            InterviewState.USER_SPEAKING,
            InterviewState.CANDIDATE_SHORT_PAUSE,
            InterviewState.CANDIDATE_LONG_PAUSE,
        )

    def __repr__(self) -> str:
        return f"<InterviewStateMachine session={self._session_id} state={self._state.value}>"

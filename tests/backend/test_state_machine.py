"""
面试状态机单元测试
"""

import pytest
import asyncio

from app.services.interview_state_machine import (
    InterviewState,
    InterviewEvent,
    InterviewStateMachine,
    IllegalTransitionError,
)


@pytest.fixture
def sm():
    return InterviewStateMachine("test-session-001")


@pytest.mark.asyncio
async def test_initial_state(sm):
    assert sm.state == InterviewState.IDLE


@pytest.mark.asyncio
async def test_full_flow_follow_up(sm):
    """测试完整流程：开始 → 面试 → 追问 → 结束"""
    # IDLE → PREPARING
    await sm.fire(InterviewEvent.PREPARE)
    assert sm.state == InterviewState.PREPARING

    # PREPARING → OPENING
    await sm.fire(InterviewEvent.PREPARED)
    assert sm.state == InterviewState.OPENING

    # OPENING → INTERVIEWER_SPEAKING
    await sm.fire(InterviewEvent.OPENING_DONE)
    assert sm.state == InterviewState.INTERVIEWER_SPEAKING

    # INTERVIEWER_SPEAKING → USER_WAITING
    await sm.fire(InterviewEvent.SPEAK_DONE)
    assert sm.state == InterviewState.USER_WAITING

    # USER_WAITING → USER_SPEAKING
    await sm.fire(InterviewEvent.USER_STARTED)
    assert sm.state == InterviewState.USER_SPEAKING

    # USER_SPEAKING → ENDPOINT_DETECTING
    await sm.fire(InterviewEvent.USER_STOPPED)
    assert sm.state == InterviewState.ENDPOINT_DETECTING

    # ENDPOINT_DETECTING → ANSWER_ANALYZING
    await sm.fire(InterviewEvent.ENDPOINT_CONFIRMED)
    assert sm.state == InterviewState.ANSWER_ANALYZING

    # ANSWER_ANALYZING → DECISION_MAKING
    await sm.fire(InterviewEvent.ANALYSIS_DONE)
    assert sm.state == InterviewState.DECISION_MAKING

    # DECISION_MAKING → INTERVIEWER_SPEAKING (follow_up)
    await sm.fire(InterviewEvent.FOLLOW_UP)
    assert sm.state == InterviewState.INTERVIEWER_SPEAKING


@pytest.mark.asyncio
async def test_full_flow_wrap_up(sm):
    """测试完整流程到结束"""
    for event in [
        InterviewEvent.PREPARE,
        InterviewEvent.PREPARED,
        InterviewEvent.OPENING_DONE,
        InterviewEvent.SPEAK_DONE,
        InterviewEvent.USER_STARTED,
        InterviewEvent.USER_STOPPED,
        InterviewEvent.ENDPOINT_CONFIRMED,
        InterviewEvent.ANALYSIS_DONE,
        InterviewEvent.WRAP_UP,
        InterviewEvent.CLOSING_DONE,
    ]:
        await sm.fire(event)

    assert sm.state == InterviewState.FINISHED
    assert sm.is_finished()


@pytest.mark.asyncio
async def test_switch_topic(sm):
    """测试换题"""
    for event in [
        InterviewEvent.PREPARE,
        InterviewEvent.PREPARED,
        InterviewEvent.OPENING_DONE,
        InterviewEvent.SPEAK_DONE,
        InterviewEvent.USER_STARTED,
        InterviewEvent.USER_STOPPED,
        InterviewEvent.ENDPOINT_CONFIRMED,
        InterviewEvent.ANALYSIS_DONE,
        InterviewEvent.SWITCH_TOPIC,
    ]:
        await sm.fire(event)

    assert sm.state == InterviewState.INTERVIEWER_SPEAKING


@pytest.mark.asyncio
async def test_silence_timeout(sm):
    """测试超时未说话"""
    for event in [
        InterviewEvent.PREPARE,
        InterviewEvent.PREPARED,
        InterviewEvent.OPENING_DONE,
        InterviewEvent.SPEAK_DONE,
        InterviewEvent.SILENCE_TIMEOUT,
    ]:
        await sm.fire(event)

    assert sm.state == InterviewState.INTERVIEWER_SPEAKING


@pytest.mark.asyncio
async def test_speech_resumed(sm):
    """测试停顿后继续说话"""
    for event in [
        InterviewEvent.PREPARE,
        InterviewEvent.PREPARED,
        InterviewEvent.OPENING_DONE,
        InterviewEvent.SPEAK_DONE,
        InterviewEvent.USER_STARTED,
        InterviewEvent.USER_STOPPED,
        InterviewEvent.SPEECH_RESUMED,
    ]:
        await sm.fire(event)

    assert sm.state == InterviewState.USER_SPEAKING


@pytest.mark.asyncio
async def test_illegal_transition(sm):
    """测试非法迁移抛异常"""
    with pytest.raises(IllegalTransitionError):
        await sm.fire(InterviewEvent.SPEAK_DONE)  # IDLE 不接受 SPEAK_DONE


@pytest.mark.asyncio
async def test_can_fire(sm):
    assert sm.can_fire(InterviewEvent.PREPARE)
    assert not sm.can_fire(InterviewEvent.SPEAK_DONE)


@pytest.mark.asyncio
async def test_allowed_events(sm):
    events = sm.allowed_events()
    assert InterviewEvent.PREPARE in events
    assert len(events) == 1  # IDLE 只有 PREPARE


@pytest.mark.asyncio
async def test_on_enter_callback(sm):
    entered = []

    async def on_enter(state):
        entered.append(state)

    sm.on_enter(InterviewState.PREPARING, on_enter)
    await sm.fire(InterviewEvent.PREPARE)
    assert InterviewState.PREPARING in entered


@pytest.mark.asyncio
async def test_on_exit_callback(sm):
    exited = []

    async def on_exit(state):
        exited.append(state)

    sm.on_exit(InterviewState.IDLE, on_exit)
    await sm.fire(InterviewEvent.PREPARE)
    assert InterviewState.IDLE in exited

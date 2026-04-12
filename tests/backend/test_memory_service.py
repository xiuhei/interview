"""
面试记忆服务单元测试
"""

import pytest

from app.services.interview_memory_service import InterviewMemoryService


@pytest.fixture
def memory():
    return InterviewMemoryService(
        job_name="C++后端开发",
        style="normal",
        max_rounds=10,
        resume_summary="3年C++经验，熟悉网络编程",
        competencies=["C++语言特性", "系统编程", "网络编程", "中间件", "工程能力"],
    )


def test_initial_state(memory):
    assert memory.global_ctx.job_name == "C++后端开发"
    assert memory.global_ctx.round_no == 0
    assert len(memory.global_ctx.uncovered_competencies) == 5
    assert len(memory.global_ctx.covered_competencies) == 0


def test_advance_round(memory):
    round_no = memory.advance_round()
    assert round_no == 1
    assert memory.global_ctx.round_no == 1


def test_set_current_question_covers_competency(memory):
    memory.set_current_question("智能指针怎么用？", "C++语言特性")
    assert "C++语言特性" in memory.global_ctx.covered_competencies
    assert "C++语言特性" not in memory.global_ctx.uncovered_competencies


def test_coverage_ratio(memory):
    assert memory.coverage_ratio() == 0.0
    memory.set_current_question("q1", "C++语言特性")
    assert memory.coverage_ratio() == 0.2
    memory.set_current_question("q2", "系统编程")
    assert memory.coverage_ratio() == 0.4


def test_should_wrap_up_by_rounds(memory):
    memory.global_ctx.round_no = 10
    assert memory.should_wrap_up()


def test_should_wrap_up_by_coverage(memory):
    for comp in ["C++语言特性", "系统编程", "网络编程", "中间件"]:
        memory.set_current_question("q", comp)
    assert memory.coverage_ratio() == 0.8
    assert memory.should_wrap_up()


def test_commit_round(memory):
    memory.advance_round()
    memory.set_current_question("智能指针怎么用？")
    memory.set_current_answer("shared_ptr 和 unique_ptr 的区别...")
    memory.set_answer_analysis(
        summary="回答了智能指针的基本概念",
        followup_points=["没有提到weak_ptr"],
        weakness_tags=["RAII理解不够深入"],
    )
    memory.commit_round("follow_up", score_hint="medium")

    assert len(memory.round_summaries) == 1
    assert memory.round_summaries[0].decision == "follow_up"
    assert "RAII理解不够深入" in memory.global_ctx.weakness_tags


def test_build_llm_context(memory):
    memory.advance_round()
    memory.set_current_question("智能指针怎么用？", "C++语言特性")
    memory.set_current_answer("shared_ptr 是引用计数的智能指针")

    ctx = memory.build_llm_context()
    assert "C++后端开发" in ctx
    assert "智能指针" in ctx
    assert "shared_ptr" in ctx


def test_build_decision_context(memory):
    memory.advance_round()
    memory.set_current_question("q1", "C++语言特性")
    memory.set_current_answer("answer")
    memory.set_answer_analysis("summary", ["point1"])
    memory.commit_round("follow_up")

    ctx = memory.build_decision_context()
    assert ctx["job_name"] == "C++后端开发"
    assert ctx["round_no"] == 1
    assert len(ctx["recent_rounds"]) == 1


def test_sliding_window_limit(memory):
    """测试滑动窗口只保留最近 N 轮"""
    for i in range(5):
        memory.advance_round()
        memory.set_current_question(f"q{i}")
        memory.set_current_answer(f"a{i}")
        memory.set_answer_analysis(f"summary{i}")
        memory.commit_round("follow_up")

    ctx = memory.build_decision_context()
    assert len(ctx["recent_rounds"]) == 3  # SLIDING_WINDOW_SIZE = 3

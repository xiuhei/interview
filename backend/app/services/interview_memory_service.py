"""
面试上下文记忆管理 — 三层上下文：全局、滑动窗口、当前题。
不将全部逐字稿拼给 LLM，做压缩记忆。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SLIDING_WINDOW_SIZE = 3  # 保留最近 N 轮摘要


@dataclass
class GlobalContext:
    """整场不变或缓慢更新的全局上下文"""
    job_name: str = ""
    interview_style: str = "medium"
    resume_summary: str | None = None
    round_no: int = 0
    max_rounds: int = 10
    covered_competencies: list[str] = field(default_factory=list)
    uncovered_competencies: list[str] = field(default_factory=list)
    weakness_tags: list[str] = field(default_factory=list)


@dataclass
class RoundSummary:
    """单轮摘要"""
    round_no: int = 0
    question_summary: str = ""
    answer_summary: str = ""
    score_hint: str = ""
    decision: str = ""
    competency: str = ""


@dataclass
class CurrentContext:
    """当前题上下文，每轮重置"""
    current_question: str = ""
    current_answer_transcript: str = ""
    current_answer_summary: str = ""
    current_followup_points: list[str] = field(default_factory=list)


class InterviewMemoryService:
    """
    管理面试上下文记忆。
    提供 build_llm_context() 将三层上下文组装成结构化文本注入 Prompt。
    """

    def __init__(self, job_name: str, style: str, max_rounds: int = 10,
                 resume_summary: str | None = None,
                 competencies: list[str] | None = None):
        self.global_ctx = GlobalContext(
            job_name=job_name,
            interview_style=style,
            resume_summary=resume_summary,
            max_rounds=max_rounds,
            uncovered_competencies=list(competencies) if competencies else [],
        )
        self.round_summaries: list[RoundSummary] = []
        self.current_ctx = CurrentContext()

    # ---- 更新接口 ----

    def advance_round(self) -> int:
        self.global_ctx.round_no += 1
        self.current_ctx = CurrentContext()
        return self.global_ctx.round_no

    def set_current_question(self, question: str, competency: str = "") -> None:
        self.current_ctx.current_question = question
        if competency and competency not in self.global_ctx.covered_competencies:
            self.global_ctx.covered_competencies.append(competency)
            if competency in self.global_ctx.uncovered_competencies:
                self.global_ctx.uncovered_competencies.remove(competency)

    def set_current_answer(self, transcript: str) -> None:
        self.current_ctx.current_answer_transcript = transcript

    def set_answer_analysis(self, summary: str, followup_points: list[str] | None = None,
                            weakness_tags: list[str] | None = None) -> None:
        self.current_ctx.current_answer_summary = summary
        self.current_ctx.current_followup_points = followup_points or []
        if weakness_tags:
            for tag in weakness_tags:
                if tag not in self.global_ctx.weakness_tags:
                    self.global_ctx.weakness_tags.append(tag)

    def commit_round(self, decision: str, score_hint: str = "") -> None:
        """将当前轮提交到滑动窗口"""
        rs = RoundSummary(
            round_no=self.global_ctx.round_no,
            question_summary=self.current_ctx.current_question[:80],
            answer_summary=self.current_ctx.current_answer_summary or
                           self.current_ctx.current_answer_transcript[:80],
            score_hint=score_hint,
            decision=decision,
        )
        self.round_summaries.append(rs)
        logger.info("提交轮次摘要 round=%d decision=%s", rs.round_no, decision)

    # ---- 覆盖度 ----

    def coverage_ratio(self) -> float:
        total = len(self.global_ctx.covered_competencies) + len(self.global_ctx.uncovered_competencies)
        if total == 0:
            return 1.0
        return len(self.global_ctx.covered_competencies) / total

    def should_wrap_up(self) -> bool:
        if self.global_ctx.round_no >= self.global_ctx.max_rounds:
            return True
        if self.coverage_ratio() >= 0.8:
            return True
        return False

    # ---- 构建 LLM 上下文 ----

    def build_llm_context(self) -> str:
        parts: list[str] = []

        # 全局
        g = self.global_ctx
        parts.append(f"【全局信息】岗位: {g.job_name} | 风格: {g.interview_style} | "
                      f"轮次: {g.round_no}/{g.max_rounds}")
        if g.resume_summary:
            parts.append(f"简历摘要: {g.resume_summary[:200]}")
        if g.covered_competencies:
            parts.append(f"已覆盖维度: {', '.join(g.covered_competencies)}")
        if g.uncovered_competencies:
            parts.append(f"未覆盖维度: {', '.join(g.uncovered_competencies)}")
        if g.weakness_tags:
            parts.append(f"已发现短板: {', '.join(g.weakness_tags)}")

        # 滑动窗口（最近 N 轮）
        recent = self.round_summaries[-SLIDING_WINDOW_SIZE:]
        if recent:
            parts.append("【最近问答摘要】")
            for rs in recent:
                parts.append(f"  第{rs.round_no}轮 — Q: {rs.question_summary} | "
                              f"A: {rs.answer_summary} | 评价: {rs.score_hint} | 决策: {rs.decision}")

        # 当前题
        c = self.current_ctx
        if c.current_question:
            parts.append(f"【当前问题】{c.current_question}")
        if c.current_answer_transcript:
            parts.append(f"【当前回答原文】{c.current_answer_transcript[:300]}")
        if c.current_answer_summary:
            parts.append(f"【当前回答摘要】{c.current_answer_summary}")
        if c.current_followup_points:
            parts.append(f"【可追问方向】{'; '.join(c.current_followup_points)}")

        return "\n".join(parts)

    def build_decision_context(self) -> dict:
        """为决策 prompt 构建结构化字典"""
        return {
            "job_name": self.global_ctx.job_name,
            "style": self.global_ctx.interview_style,
            "round_no": self.global_ctx.round_no,
            "max_rounds": self.global_ctx.max_rounds,
            "covered_competencies": self.global_ctx.covered_competencies,
            "uncovered_competencies": self.global_ctx.uncovered_competencies,
            "weakness_tags": self.global_ctx.weakness_tags,
            "coverage_ratio": round(self.coverage_ratio(), 2),
            "current_question": self.current_ctx.current_question,
            "current_answer_summary": self.current_ctx.current_answer_summary,
            "followup_points": self.current_ctx.current_followup_points,
            "recent_rounds": [
                {
                    "round_no": rs.round_no,
                    "question": rs.question_summary,
                    "answer": rs.answer_summary,
                    "score": rs.score_hint,
                    "decision": rs.decision,
                }
                for rs in self.round_summaries[-SLIDING_WINDOW_SIZE:]
            ],
        }

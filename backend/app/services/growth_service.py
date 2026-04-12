from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean

from sqlalchemy.orm import Session

from app.repositories.interview_repository import InterviewRepository
from app.schemas.growth import CompetencyProgress, GrowthInsight, GrowthPlanItem, GrowthPoint, GrowthSummary, WeaknessInsight
from app.services.metadata_service import get_competency_label


SESSION_TTL_HOURS = 48
class GrowthService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.interview_repo = InterviewRepository(db)

    def get_growth_insight(self, user_id: int) -> GrowthInsight:
        self._cleanup_expired_unfinished_sessions(user_id=user_id)
        sessions = list(reversed(self.interview_repo.list_completed_sessions(user_id)))
        trends: list[GrowthPoint] = []
        weakness_counter: Counter[str] = Counter()
        weakness_scores: defaultdict[str, list[float]] = defaultdict(list)
        competency_scores: defaultdict[str, list[float]] = defaultdict(list)
        competency_latest: dict[str, float] = {}
        total_scores: list[float] = []

        for session in sessions:
            if not session.report:
                continue
            total_scores.append(session.report.total_score)
            trends.append(
                GrowthPoint(
                    date=session.created_at.strftime("%Y-%m-%d"),
                    total_score=session.report.total_score,
                )
            )
            for competency, score in session.report.competency_scores.items():
                numeric_score = float(score)
                competency_scores[competency].append(numeric_score)
                competency_latest[competency] = numeric_score
            for weakness in session.report.report_payload.get("weaknesses", []):
                tag = weakness.get("tag", "表达结构")
                weakness_counter[tag] += 1
                weakness_scores[tag].append(float(weakness.get("score", session.report.total_score)))

        weakness_items = [
            WeaknessInsight(
                tag=self._competency_label(tag),
                count=count,
                avg_score=round(sum(weakness_scores[tag]) / len(weakness_scores[tag]), 2),
            )
            for tag, count in weakness_counter.most_common(5)
        ]
        sorted_competency_scores = sorted(
            competency_scores.items(),
            key=lambda item: mean(item[1]),
            reverse=True,
        )
        competency_progress = [
            CompetencyProgress(
                competency=self._competency_label(competency),
                average_score=round(mean(scores), 2),
                latest_score=round(competency_latest.get(competency, scores[-1]), 2),
                session_count=len(scores),
            )
            for competency, scores in sorted_competency_scores
        ]

        strongest_competency = sorted_competency_scores[0][0] if sorted_competency_scores else "暂无"
        focus_competency = sorted_competency_scores[-1][0] if sorted_competency_scores else "综合能力"
        average_score = round(mean(total_scores), 2) if total_scores else None
        latest_score = round(total_scores[-1], 2) if total_scores else None
        previous_score = total_scores[-2] if len(total_scores) >= 2 else None
        score_delta = round(latest_score - previous_score, 2) if latest_score is not None and previous_score is not None else None
        readiness_label = self._readiness_label(average_score)
        plan = [
            GrowthPlanItem(
                title=f"专项训练：{item.tag}",
                focus=item.tag,
                action="围绕高频短板完成 3 道专项题，并复盘回答结构。",
                expected_result="提升回答的完整度、可信度和岗位贴合度。",
            )
            for item in weakness_items[:3]
        ] or [
            GrowthPlanItem(
                title="基础训练计划",
                focus="综合能力",
                action="完成一轮常规面试，并重点补充项目量化结果。",
                expected_result="建立稳定的答题结构和表达节奏。",
            )
        ]

        summary = GrowthSummary(
            completed_sessions=len(total_scores),
            average_score=average_score,
            latest_score=latest_score,
            score_delta=score_delta,
            strongest_competency=strongest_competency,
            focus_competency=focus_competency,
            readiness_label=readiness_label,
            narrative=self._narrative(
                len(total_scores),
                average_score,
                strongest_competency,
                focus_competency,
            ),
            recommendations=[item.action for item in plan[:3]],
        )
        return GrowthInsight(
            summary=summary,
            trends=trends,
            competency_progress=competency_progress,
            weaknesses=weakness_items,
            plan=plan,
        )

    def _cleanup_expired_unfinished_sessions(self, user_id: int | None = None) -> int:
        expires_before = datetime.now(timezone.utc) - timedelta(hours=SESSION_TTL_HOURS)
        deleted = self.interview_repo.cleanup_expired_unfinished_sessions(
            expires_before=expires_before,
            user_id=user_id,
        )
        if deleted:
            self.db.commit()
        return deleted

    def _competency_label(self, value: str) -> str:
        return get_competency_label(value)

    def _readiness_label(self, average_score: float | None) -> str:
        if average_score is None:
            return "待开始"
        if average_score >= 85:
            return "优势明显"
        if average_score >= 75:
            return "稳步进步"
        if average_score >= 60:
            return "继续补强"
        return "需要集中训练"

    def _narrative(
        self,
        completed_sessions: int,
        average_score: float | None,
        strongest_competency: str,
        focus_competency: str,
    ) -> str:
        if completed_sessions == 0 or average_score is None:
            return "当前还没有已完成的面试记录。完成一轮面试后，这里会显示能力趋势、优势能力和下一步训练建议。"
        return (
            f"你已经完成了 {completed_sessions} 场面试，当前平均分为 {average_score}。"
            f"表现最稳定的能力点是 {self._competency_label(strongest_competency)}，"
            f"接下来最值得继续补强的是 {self._competency_label(focus_competency)}。"
        )



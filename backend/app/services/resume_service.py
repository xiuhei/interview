import re
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.enums import ResumeStatus
from app.repositories.position_repository import PositionRepository
from app.repositories.resume_repository import ResumeRepository
from app.schemas.resume import ResumeJobMatch, ResumeLibraryItem, ResumeScoreBreakdown, ResumeSummary
from app.services.prompt_service import PromptService
from app.utils.text import clean_text, extract_keywords, keyword_hits, read_resume_text, star_score


SUPPORTED_RESUME_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".rtf"}
DEFAULT_BACKGROUND = "简历信息较少，请补充代表性项目、职责和结果。"
RESULT_MARKERS = ["结果", "收益", "提升", "优化", "增长", "降低", "缩短", "稳定", "上线", "落地"]
OWNERSHIP_MARKERS = ["负责", "主导", "设计", "实现", "推动", "排查", "优化", "落地", "搭建", "维护"]
PROJECT_HINT_MARKERS = ["项目", "系统", "平台", "服务", "后台", "前端", "架构", "业务"]
GENERIC_PROJECT_TOKENS = {
    "项目",
    "经历",
    "经验",
    "负责",
    "参与",
    "一些",
    "一点",
    "做过",
    "相关",
    "工作",
    "开发",
    "岗位",
    "学习",
    "能力",
    "简历",
    "求职",
}
SKILL_ALIASES = {
    "C++": ["c++"],
    "STL": ["stl"],
    "Linux": ["linux"],
    "Redis": ["redis"],
    "MySQL": ["mysql"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MongoDB": ["mongodb", "mongo"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq", "rabbit mq"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "gRPC": ["grpc"],
    "HTTP": ["http", "https"],
    "TCP": ["tcp"],
    "Nginx": ["nginx"],
    "Vue": ["vue", "vue3", "vue 3"],
    "React": ["react"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "HTML/CSS": ["html", "css", "sass", "less"],
    "Vite": ["vite"],
    "Webpack": ["webpack"],
    "Pinia": ["pinia"],
    "Vuex": ["vuex"],
    "Node.js": ["node", "node.js", "nodejs"],
    "Webpack/Vite": ["webpack", "vite"],
    "浏览器原理": ["浏览器", "渲染", "event loop", "事件循环", "dom", "缓存"],
    "性能优化": ["性能", "首屏", "包体积", "压测", "吞吐", "rt", "qps", "监控"],
    "高并发": ["高并发", "并发", "吞吐", "qps", "限流"],
    "分布式": ["分布式", "微服务", "服务治理", "消息队列"],
}
ROLE_COMPETENCY_KEYWORDS = {
    "cpp_backend": {
        "cpp_language": ["C++", "STL", "智能指针", "RAII", "模板", "内存管理"],
        "os_network": ["Linux", "TCP", "Socket", "Epoll", "多线程", "网络编程"],
        "algorithm": ["算法", "复杂度", "哈希表", "链表", "树", "队列"],
        "system_design": ["Redis", "MySQL", "Kafka", "分布式", "微服务", "高并发"],
        "performance": ["性能优化", "压测", "监控", "排障", "QPS", "RT"],
        "project_depth": ["负责", "主导", "设计", "结果", "收益", "复盘"],
    },
    "web_frontend": {
        "frontend_foundation": ["JavaScript", "TypeScript", "HTML/CSS", "前端基础", "组件"],
        "vue_engineering": ["Vue", "Pinia", "Vuex", "Webpack/Vite", "工程化", "路由"],
        "browser_principle": ["浏览器原理", "DOM", "缓存", "渲染", "事件循环"],
        "network_performance": ["性能优化", "首屏", "缓存", "包体积", "监控", "CDN"],
        "architecture": ["架构", "设计系统", "组件库", "模块化", "平台化", "状态管理"],
        "project_depth": ["负责", "主导", "结果", "收益", "复盘", "协作"],
    },
}
INTERVIEW_FOCUS_TEMPLATES = {
    "cpp_language": "重点确认 C++ 语言特性、内存管理和工程实践是否真的做过。",
    "os_network": "重点追问 IO 模型、网络协议和线上排障的真实场景。",
    "algorithm": "重点追问复杂度分析和为什么这样选数据结构。",
    "system_design": "重点追问缓存、数据库、限流、消息队列之间的设计取舍。",
    "performance": "重点追问瓶颈定位、压测验证和量化优化结果。",
    "project_depth": "重点追问个人职责、关键难点、方案取舍和最终指标。",
    "frontend_foundation": "重点追问 JavaScript/TypeScript 基础和组件实现细节。",
    "vue_engineering": "重点追问 Vue 工程化、状态管理和构建链路。",
    "browser_principle": "重点追问浏览器渲染、事件循环和缓存机制。",
    "network_performance": "重点追问首屏优化、缓存策略和监控指标。",
    "architecture": "重点追问前端架构拆分、模块边界和公共能力设计。",
}


class ResumeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ResumeRepository(db)
        self.position_repo = PositionRepository(db)
        self.settings = get_settings()
        self.prompt_service = PromptService()

    def save_upload(self, user_id: int, file: UploadFile):
        extension = (Path(file.filename or "resume.txt").suffix or ".txt").lower()
        if extension not in SUPPORTED_RESUME_EXTENSIONS:
            raise AppException("当前仅支持 PDF、DOCX、TXT、MD、RTF 简历。", 400)
        stored_name = f"{uuid4().hex}{extension}"
        target = self.settings.upload_dir / "resumes" / stored_name
        with target.open("wb") as output:
            output.write(file.file.read())
        resume = self.repo.create(
            user_id=user_id,
            filename=file.filename or stored_name,
            stored_path=str(target.relative_to(self.settings.upload_dir.parent)),
            mime_type=file.content_type or "application/octet-stream",
            raw_text="",
            status=ResumeStatus.uploaded,
        )
        self.db.commit()
        self.db.refresh(resume)
        return resume

    def list_resumes(self, user_id: int) -> list[ResumeLibraryItem]:
        items = self.repo.list_for_user(user_id) if hasattr(self.repo, "list_for_user") else []
        return [self._to_library_item(item) for item in items]

    def parse_resume(self, resume_id: int, user_id: int | None = None):
        resume = self._get_resume(resume_id, user_id=user_id)
        full_path = self.settings.upload_dir.parent / resume.stored_path
        raw_text = clean_text(read_resume_text(full_path))
        if not raw_text:
            raise AppException("简历内容为空或当前格式暂不支持解析，请尝试导出为 PDF、DOCX 或 TXT。", 400)
        draft_summary = self._build_summary(raw_text)
        prompt_result, fallback_used = self.prompt_service.run_json_prompt(
            "resume_parse",
            {
                "task_context": {
                    "document_type": "resume",
                    "language": "zh-CN",
                    "stage": "resume_parse",
                },
                "resume_text": raw_text[:5000],
                "draft": draft_summary.model_dump(),
            },
            fallback_result=draft_summary.model_dump(),
        )
        merged_summary = self._merge_prompt_summary(draft_summary, prompt_result)
        final_summary = self._enrich_summary(raw_text, merged_summary)

        resume.raw_text = raw_text
        resume.status = ResumeStatus.parsed
        raw_result = {
            "prompt_result": prompt_result,
            "fallback_used": fallback_used,
            "draft_summary": draft_summary.model_dump(),
        }
        if resume.parse:
            resume.parse.summary = final_summary.model_dump()
            resume.parse.raw_result = raw_result
        else:
            self.repo.create_parse(
                resume_id=resume.id,
                summary=final_summary.model_dump(),
                raw_result=raw_result,
            )
        self.db.commit()
        self.db.refresh(resume)
        return resume

    def get_summary(self, resume_id: int, user_id: int | None = None) -> ResumeSummary:
        resume = self._get_resume(resume_id, user_id=user_id)
        if not resume.parse:
            raise AppException("简历摘要不存在", 404)
        return ResumeSummary.model_validate(resume.parse.summary)

    def _get_resume(self, resume_id: int, user_id: int | None = None):
        if user_id is not None and hasattr(self.repo, "get_for_user"):
            resume = self.repo.get_for_user(user_id, resume_id)
        else:
            resume = self.repo.get(resume_id)
            if user_id is not None and resume and getattr(resume, "user_id", user_id) != user_id:
                resume = None
        if not resume:
            raise AppException("简历不存在", 404)
        return resume

    def _to_library_item(self, resume) -> ResumeLibraryItem:
        summary = None
        if getattr(resume, "parse", None) and getattr(resume.parse, "summary", None):
            summary = ResumeSummary.model_validate(resume.parse.summary)
        return ResumeLibraryItem(
            id=resume.id,
            filename=resume.filename,
            stored_path=resume.stored_path,
            mime_type=resume.mime_type,
            status=resume.status,
            created_at=resume.created_at,
            updated_at=resume.updated_at,
            summary=summary,
        )

    def _build_summary(self, text: str) -> ResumeSummary:
        normalized = clean_text(text)
        fragments = self._split_fragments(normalized)
        highlights = self._extract_highlights(normalized, fragments)
        project_experiences = self._extract_project_experiences(fragments)
        tech_stack = self._extract_tech_stack(normalized)
        risk_points = self._extract_risk_points(normalized, project_experiences, tech_stack)
        background = normalized[:220] or DEFAULT_BACKGROUND
        return ResumeSummary(
            candidate_name=self._extract_candidate_name(normalized),
            background=background,
            project_experiences=project_experiences,
            tech_stack=tech_stack,
            highlights=highlights,
            risk_points=risk_points,
            years_of_experience=self._extract_years(normalized),
        )

    def _enrich_summary(self, raw_text: str, summary: ResumeSummary) -> ResumeSummary:
        job_matches = self._build_job_matches(raw_text, summary)
        best_job_match = job_matches[0] if job_matches else None
        score_breakdown = self._build_score_breakdown(raw_text, summary, best_job_match)
        overall_score = round(
            score_breakdown.clarity * 0.18
            + score_breakdown.project_depth * 0.25
            + score_breakdown.impact * 0.2
            + score_breakdown.role_relevance * 0.25
            + score_breakdown.credibility * 0.12,
            2,
        )
        interview_focuses = self._build_interview_focuses(summary, best_job_match)
        resume_suggestions = self._build_resume_suggestions(summary, score_breakdown, best_job_match)
        return summary.model_copy(
            update={
                "overall_score": overall_score,
                "score_breakdown": score_breakdown,
                "job_matches": job_matches,
                "best_job_match": best_job_match,
                "resume_suggestions": resume_suggestions,
                "interview_focuses": interview_focuses,
            }
        )

    def _build_job_matches(self, raw_text: str, summary: ResumeSummary) -> list[ResumeJobMatch]:
        positions = self._list_positions()
        if not positions:
            return []

        matches: list[ResumeJobMatch] = []
        normalized_text = raw_text.lower()
        verified_projects = self._verified_project_experiences(raw_text, summary.project_experiences)
        for position in positions:
            competency_entries = list(getattr(position, "competencies", []) or [])
            if not competency_entries:
                continue
            weighted_total = 0.0
            total_weight = 0.0
            matched_skills: list[str] = []
            missing_skills: list[str] = []
            matched_projects: list[str] = []
            low_scores: list[tuple[str, float]] = []

            for competency in competency_entries:
                keyword_specs = self._keyword_specs_for_competency(position.code, competency.code)
                if not keyword_specs:
                    continue
                matched = [label for label, aliases in keyword_specs if any(alias in normalized_text for alias in aliases)]
                match_ratio = len(matched) / len(keyword_specs)
                project_bonus = 8 if self._projects_touch_keywords(verified_projects, keyword_specs) else 0
                years_bonus = 4 if summary.years_of_experience and summary.years_of_experience >= 2 and matched else 0
                match_count_bonus = min(len(matched), 3) * 8
                missing_penalty = 10 if not matched else 0
                competency_score = self._clamp_score(
                    8 + match_ratio * 60 + match_count_bonus + project_bonus + years_bonus - missing_penalty
                )
                weighted_total += competency_score * float(getattr(competency, "weight", 0.0) or 0.0)
                total_weight += float(getattr(competency, "weight", 0.0) or 0.0)
                matched_skills.extend(matched[:3])
                if matched:
                    matched_projects.extend(self._matched_projects(verified_projects, matched))
                else:
                    missing_skills.extend(label for label, _ in keyword_specs[:2])
                if competency_score < 70:
                    low_scores.append((competency.code, competency_score))

            if total_weight <= 0:
                continue

            score_penalty = 0
            if self._has_quant_risk(summary):
                score_penalty += 4
            if not verified_projects:
                score_penalty += 10
            score = round(self._clamp_score(weighted_total / total_weight - score_penalty), 2)
            low_scores.sort(key=lambda item: item[1])
            interview_focuses = [
                INTERVIEW_FOCUS_TEMPLATES.get(code, f"重点追问 {code} 相关项目细节。")
                for code, _ in low_scores[:2]
            ]
            if self._has_quant_risk(summary):
                interview_focuses.append("重点追问结果指标、验证方式和上线后的真实收益。")
            if self._has_ownership_risk(summary):
                interview_focuses.append("重点追问你本人负责了什么，而不是团队整体做了什么。")
            interview_focuses = self._dedupe(interview_focuses)[:4]
            matched_skills = self._dedupe(matched_skills)[:6]
            missing_skills = [item for item in self._dedupe(missing_skills) if item not in matched_skills][:5]
            matched_projects = self._dedupe(matched_projects)[:3] or verified_projects[:2]
            matches.append(
                ResumeJobMatch(
                    position_code=position.code,
                    position_name=position.name,
                    score=score,
                    level=self._match_level(score),
                    matched_skills=matched_skills,
                    missing_skills=missing_skills,
                    matched_projects=matched_projects,
                    interview_focuses=interview_focuses,
                    summary=self._build_job_match_summary(position.name, score, matched_skills, missing_skills),
                )
            )

        return sorted(matches, key=lambda item: item.score, reverse=True)

    def _build_score_breakdown(
        self,
        raw_text: str,
        summary: ResumeSummary,
        best_job_match: ResumeJobMatch | None,
    ) -> ResumeScoreBreakdown:
        normalized = raw_text.lower()
        raw_length = len(clean_text(raw_text))
        fragment_count = len(self._split_fragments(raw_text))
        verified_projects = self._verified_project_experiences(raw_text, summary.project_experiences)
        verified_project_count = len(verified_projects)
        verified_tech_stack = self._extract_tech_stack(raw_text)
        verified_tech_count = len(verified_tech_stack)
        metrics_count = len(
            re.findall(r"\d+(?:\.\d+)?\s*(?:%|ms|s|秒|分钟|倍|万|千|qps|tps|rt|人|次|个)", normalized)
        )
        result_hits = sum(1 for marker in RESULT_MARKERS if marker in raw_text)
        ownership_hits = sum(1 for marker in OWNERSHIP_MARKERS if marker in raw_text)
        structure_hits = sum(
            [
                1 if summary.candidate_name else 0,
                1 if summary.years_of_experience is not None else 0,
                1 if raw_length >= 80 else 0,
                1 if fragment_count >= 3 else 0,
                1 if verified_project_count >= 1 else 0,
                1 if verified_tech_count >= 2 else 0,
            ]
        )
        clarity = self._clamp_score(
            12
            + structure_hits * 11
            + min(verified_project_count, 3) * 7
            + (8 if raw_length >= 160 else 0)
            - (8 if self._has_timeline_risk(summary) else 0)
            - (10 if raw_length < 60 else 0)
            - (8 if fragment_count < 3 else 0)
            - (6 if len(summary.risk_points) >= 3 else 0)
        )
        project_depth = self._clamp_score(
            8
            + min(star_score(raw_text), 100) * 0.22
            + min(verified_project_count, 3) * 14
            + min(ownership_hits, 4) * 7
            + min(verified_tech_count, 6) * 3
            - (14 if verified_project_count == 0 else 0)
            - (10 if ownership_hits == 0 else 0)
        )
        impact = self._clamp_score(
            8
            + min(metrics_count, 4) * 16
            + min(result_hits, 4) * 10
            + (8 if any(any(char.isdigit() for char in item) for item in verified_projects) else 0)
            - (12 if metrics_count == 0 else 0)
            - (8 if result_hits == 0 else 0)
        )
        if best_job_match:
            role_relevance = self._clamp_score(
                best_job_match.score
                - (8 if verified_tech_count < 2 else 0)
                - (8 if verified_project_count == 0 else 0)
            )
        else:
            role_relevance = self._clamp_score(
                10
                + verified_tech_count * 6
                + verified_project_count * 6
                - (10 if verified_tech_count == 0 else 0)
            )
        credibility = self._clamp_score(
            10
            + min(ownership_hits, 4) * 8
            + min(metrics_count, 3) * 7
            + min(verified_tech_count, 5) * 5
            + (6 if verified_project_count >= 2 else 0)
            - (12 if self._has_ownership_risk(summary) else 0)
            - (10 if verified_project_count == 0 else 0)
            - (8 if raw_length < 80 else 0)
        )
        return ResumeScoreBreakdown(
            clarity=round(clarity, 2),
            project_depth=round(project_depth, 2),
            impact=round(impact, 2),
            role_relevance=round(role_relevance, 2),
            credibility=round(credibility, 2),
        )

    def _build_resume_suggestions(
        self,
        summary: ResumeSummary,
        score_breakdown: ResumeScoreBreakdown,
        best_job_match: ResumeJobMatch | None,
    ) -> list[str]:
        suggestions: list[str] = []
        if score_breakdown.impact < 70:
            suggestions.append("把每个核心项目补成“问题-动作-结果”，至少给出 1 到 2 个量化指标。")
        if score_breakdown.project_depth < 72:
            suggestions.append("补充代表性项目里的个人职责、关键难点、方案取舍和复盘，减少只写技术名词。")
        if score_breakdown.credibility < 72:
            suggestions.append("把“我负责什么、怎么验证有效、上线后效果如何”写得更明确，增强可信度。")
        if best_job_match and best_job_match.missing_skills:
            suggestions.append(
                f"如果目标是 {best_job_match.position_name}，建议补充 {best_job_match.missing_skills[0]} 等岗位直接相关经验。"
            )
        if self._has_timeline_risk(summary):
            suggestions.append("补充工作年限和时间线，让经历连续性和成长路径更清晰。")
        if self._has_ownership_risk(summary):
            suggestions.append("项目描述里多写个人主导动作，避免只写团队结果。")
        return self._dedupe(suggestions)[:5] or ["可以继续补充项目结果和个人贡献，提升岗位匹配度。"]

    def _build_interview_focuses(self, summary: ResumeSummary, best_job_match: ResumeJobMatch | None) -> list[str]:
        focuses = list(best_job_match.interview_focuses if best_job_match else [])
        if self._has_quant_risk(summary):
            focuses.append("优先追问量化结果，例如性能指标、业务收益或故障恢复效果。")
        if self._has_ownership_risk(summary):
            focuses.append("优先追问个人职责边界，确认不是泛化描述。")
        if summary.project_experiences:
            focuses.append(f"优先从“{summary.project_experiences[0]}”切入，要求讲清楚背景、难点和结果。")
        return self._dedupe(focuses)[:5]

    def _extract_highlights(self, text: str, fragments: list[str]) -> list[str]:
        highlights: list[str] = []
        for fragment in fragments:
            if any(marker in fragment for marker in RESULT_MARKERS) and any(char.isdigit() for char in fragment):
                highlights.append(fragment[:48])
        for token in ["高并发", "性能优化", "分布式", "微服务", "Vue", "React", "TypeScript", "Redis", "MySQL"]:
            if token.lower() in text.lower():
                highlights.append(token)
        return self._dedupe(highlights)[:4] or ["候选人具备一定项目和技术栈描述。"]

    def _extract_project_experiences(self, fragments: list[str]) -> list[str]:
        projects = [
            fragment[:60]
            for fragment in fragments
            if len(fragment) >= 12 and any(marker in fragment for marker in PROJECT_HINT_MARKERS)
        ]
        return self._dedupe(projects)[:4] or ["需要在面试中进一步澄清代表性项目经历。"]

    def _extract_tech_stack(self, text: str) -> list[str]:
        lowered = text.lower()
        return [
            skill
            for skill, aliases in SKILL_ALIASES.items()
            if any(alias in lowered for alias in aliases)
        ][:10]

    def _extract_risk_points(
        self,
        text: str,
        project_experiences: list[str],
        tech_stack: list[str],
    ) -> list[str]:
        risks: list[str] = []
        if not any(marker in text for marker in OWNERSHIP_MARKERS):
            risks.append("项目职责和个人贡献写得还不够清楚")
        if not re.search(r"\d+(?:\.\d+)?\s*(?:%|ms|s|秒|分钟|倍|万|千|qps|tps|rt|人|次|个)", text.lower()):
            risks.append("缺少量化结果，项目价值不够直观")
        if len(project_experiences) <= 1:
            risks.append("代表性项目数量偏少，建议补足 2 到 3 个可深挖案例")
        if self._extract_years(text) is None:
            risks.append("工作年限和时间线不够明确")
        if len(tech_stack) < 4:
            risks.append("岗位相关技术关键词偏少，匹配度表达还可以更强")
        return self._dedupe(risks)[:4]

    def _extract_candidate_name(self, text: str) -> str | None:
        head = text[:24].strip()
        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", head):
            return head
        english_match = re.match(r"([A-Z][a-z]+(?: [A-Z][a-z]+)?)", text)
        if english_match:
            candidate = english_match.group(1).strip()
            if all(marker not in candidate.lower() for marker in ["resume", "project", "email", "phone"]):
                return candidate
        return None

    def _extract_years(self, text: str) -> int | None:
        year_match = re.search(r"(\d{1,2})\s*年", text)
        if year_match:
            return int(year_match.group(1))
        english_match = re.search(r"(\d{1,2})(?:\+)?\s*years?", text.lower())
        if english_match:
            return int(english_match.group(1))
        return None

    def _split_fragments(self, text: str) -> list[str]:
        items = [
            item.strip(" ，,。；;：:-")
            for item in re.split(r"[。；;]|(?<=[0-9])\.(?=\s)|\|", text)
            if item.strip(" ，,。；;：:-")
        ]
        return [item for item in items if len(item) >= 8]

    def _verified_project_experiences(self, raw_text: str, project_experiences: list[str]) -> list[str]:
        verified: list[str] = []
        for project in project_experiences:
            project_keywords = extract_keywords(project)
            hits = keyword_hits(raw_text, project_keywords)
            cjk_hits = len(
                {
                    chunk
                    for chunk in re.findall(r"[\u4e00-\u9fff]{2}", project)
                    if chunk not in GENERIC_PROJECT_TOKENS and chunk in raw_text
                }
            )
            if hits >= 2 or (hits >= 1 and len(project.strip()) >= 10) or cjk_hits >= 2:
                verified.append(project)
        return self._dedupe(verified)

    def _projects_touch_keywords(self, projects: list[str], keyword_specs: list[tuple[str, list[str]]]) -> bool:
        project_text = " ".join(projects).lower()
        return any(alias in project_text for _, aliases in keyword_specs for alias in aliases)

    def _matched_projects(self, projects: list[str], matched_skills: list[str]) -> list[str]:
        lowered_skills = [item.lower() for item in matched_skills]
        return [
            project
            for project in projects
            if any(skill in project.lower() for skill in lowered_skills)
        ]

    def _build_job_match_summary(
        self,
        position_name: str,
        score: float,
        matched_skills: list[str],
        missing_skills: list[str],
    ) -> str:
        if matched_skills and missing_skills:
            return (
                f"当前简历和 {position_name} 的匹配度为 {score:.1f} 分，已有 {matched_skills[0]} 等相关经历，"
                f"但 {missing_skills[0]} 等能力还建议补强。"
            )
        if matched_skills:
            return f"当前简历和 {position_name} 的匹配度为 {score:.1f} 分，已有较清晰的岗位相关经历。"
        return f"当前简历和 {position_name} 的匹配度为 {score:.1f} 分，岗位相关经历还可以表达得更直接。"

    def _keyword_specs_for_competency(self, role_code: str, competency_code: str) -> list[tuple[str, list[str]]]:
        labels = ROLE_COMPETENCY_KEYWORDS.get(role_code, {}).get(competency_code, [])
        specs: list[tuple[str, list[str]]] = []
        for label in labels:
            aliases = SKILL_ALIASES.get(label)
            if aliases:
                specs.append((label, aliases))
            else:
                specs.append((label, [label.lower()]))
        return specs

    def _match_level(self, score: float) -> str:
        if score >= 85:
            return "高匹配"
        if score >= 75:
            return "匹配较强"
        if score >= 60:
            return "有一定匹配"
        return "需要补强"

    def _has_quant_risk(self, summary: ResumeSummary) -> bool:
        return any("量化" in item or "结果" in item for item in summary.risk_points)

    def _has_ownership_risk(self, summary: ResumeSummary) -> bool:
        return any("职责" in item or "贡献" in item for item in summary.risk_points)

    def _has_timeline_risk(self, summary: ResumeSummary) -> bool:
        return any("时间线" in item or "年限" in item for item in summary.risk_points)

    def _list_positions(self) -> list:
        position_repo = getattr(self, "position_repo", None)
        if position_repo is None or not hasattr(position_repo, "list_positions"):
            return []
        return position_repo.list_positions()

    def _merge_prompt_summary(self, draft_summary: ResumeSummary, prompt_result: dict) -> ResumeSummary:
        draft = draft_summary.model_dump()
        merged = {
            "candidate_name": self._normalize_text(prompt_result.get("candidate_name")) or draft.get("candidate_name"),
            "background": self._normalize_text(prompt_result.get("background")) or draft["background"],
            "project_experiences": self._normalize_text_list(
                prompt_result.get("project_experiences"),
                draft["project_experiences"],
            ),
            "tech_stack": self._normalize_text_list(prompt_result.get("tech_stack"), draft["tech_stack"]),
            "highlights": self._normalize_text_list(prompt_result.get("highlights"), draft["highlights"]),
            "risk_points": self._normalize_text_list(prompt_result.get("risk_points"), draft["risk_points"]),
            "years_of_experience": self._normalize_years(
                prompt_result.get("years_of_experience"),
                draft["years_of_experience"],
            ),
        }
        return ResumeSummary.model_validate(merged)

    def _normalize_text(self, value) -> str:
        if value is None:
            return ""
        return str(value).strip()

    def _normalize_text_list(self, value, fallback: list[str]) -> list[str]:
        if not isinstance(value, list):
            return fallback
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback

    def _normalize_years(self, value, fallback: int | None) -> int | None:
        if value is None or value == "":
            return fallback
        try:
            years = int(value)
        except (TypeError, ValueError):
            return fallback
        return years if years >= 0 else fallback

    def _dedupe(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            normalized = item.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            result.append(normalized)
        return result

    def _clamp_score(self, value: float) -> float:
        return max(0.0, min(100.0, value))

import hashlib
import json

from app.core.config import get_settings
DEFAULT_OPENING_BY_ROLE = {
    "web_frontend": "请介绍一个你做过的前端项目，说说你负责什么，难点在哪。",
    "cpp_backend": "请介绍一个你做过的 C++ 后端项目，说说你负责什么，难点在哪。",
}

DEFAULT_FOLLOW_UP = {
    "deepen": "继续说说 {competency}。",
    "redirect": "先回到 {competency} 这个点。",
    "credibility": "这件事里你具体负责什么？怎么验证结果？",
}

INVALID_QUESTION_PHRASES = (
    "项目真实性",
    "真实性为什么能工作",
    "和 项目真实性 相关的问题",
)
PROJECT_DEPTH_HINTS = ("项目", "经历", "负责", "落地", "场景", "结果", "难点", "方案")
PROJECT_DEPTH_INVALID_PATTERNS = (
    "核心概念",
    "为什么能工作",
    "底层原理",
    "请对比",
    "对比 ",
    "怎么比较",
    "应该怎么比较",
    "如何判断是否采用它",
)


class QuestionSeedService:
    def __init__(self) -> None:
        settings = get_settings()
        self.seed_dir = settings.content_source_dir / "question_seeds"
        self.question_bank_path = settings.runtime_corpus_dir / "records.jsonl"
        self._seed_cache: dict[str, dict] = {}
        self._question_cache: dict[str, dict[str, list[str]]] = {}

    def _load_seed_payload(self, role_code: str) -> dict:
        if role_code not in self._seed_cache:
            path = self.seed_dir / f"{role_code}.json"
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
            raw["opening"] = [
                {
                    **item,
                    "question": self._normalize_text(str(item.get("question", ""))),
                    "competency_code": str(item.get("competency_code", "project_depth")),
                }
                for item in raw.get("opening", [])
                if self._is_valid_question_text(str(item.get("question", "")))
            ]
            raw["competencies"] = {
                code: [
                    {
                        **item,
                        "question": self._normalize_text(str(item.get("question", ""))),
                    }
                    for item in items
                    if self._is_valid_question_text(str(item.get("question", "")))
                ]
                for code, items in raw.get("competencies", {}).items()
            }
            raw["follow_up"] = {
                key: self._normalize_text(str(value))
                for key, value in raw.get("follow_up", {}).items()
            }
            self._seed_cache[role_code] = raw
        return self._seed_cache[role_code]

    def _load_question_bank(self, role_code: str) -> dict[str, list[str]]:
        if role_code in self._question_cache:
            return self._question_cache[role_code]

        payload = self._load_seed_payload(role_code)
        known_competencies = set(payload.get("competencies", {}).keys())
        buckets: dict[str, list[str]] = {code: [] for code in known_competencies}
        buckets["__general__"] = []

        if self.question_bank_path.exists():
            with self.question_bank_path.open("r", encoding="utf-8-sig") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if item.get("role_code") != role_code or item.get("doc_type") != "question":
                        continue
                    question_text = self._extract_question_text(item)
                    if not question_text:
                        continue
                    source_type = self._normalize_text(str(item.get("source_type", ""))).strip().lower()
                    bucket = source_type if source_type in known_competencies else "__general__"
                    buckets.setdefault(bucket, []).append(question_text)

        self._question_cache[role_code] = {
            key: [item for item in dict.fromkeys(value) if self._is_valid_question_text(item)]
            for key, value in buckets.items()
            if value
        }
        return self._question_cache[role_code]

    def get_opening_question(
        self,
        role_code: str,
        highlights: list[str],
        risk_points: list[str],
        used_questions: list[str] | None = None,
        selector_seed: str | int | None = None,
        projects: list[str] | None = None,
        interview_focuses: list[str] | None = None,
        style: str = "medium",
    ) -> tuple[str, str]:
        payload = self._load_seed_payload(role_code)
        used_questions = used_questions or []
        projects = projects or []
        interview_focuses = interview_focuses or []
        competency = "project_depth"

        if projects:
            project = self._normalize_resume_fragment(projects[0])
            if project:
                return (
                    self._apply_opening_difficulty(
                        f"先从你简历里的“{project}”讲起。请你说明这个项目里你具体负责什么、最难的问题是什么、最后结果怎样。",
                        style,
                    ),
                    competency,
                )
        if interview_focuses:
            focus = self._normalize_resume_fragment(interview_focuses[0])
            if focus:
                return (
                    self._apply_opening_difficulty(
                        f"我们先围绕“{focus}”来聊。请结合一个你亲自做过的项目，讲清楚你的职责、做法和结果。",
                        style,
                    ),
                    competency,
                )
        if highlights:
            return (
                self._apply_opening_difficulty(
                    f"你简历里提到过“{highlights[0]}”，请结合一个最有代表性的项目，讲清楚你的职责、关键难点和最终结果。",
                    style,
                ),
                competency,
            )
        if risk_points:
            return (
                self._apply_opening_difficulty(
                    f"我注意到你的经历里可能存在“{risk_points[0]}”这个风险点。请你结合一个真实项目，说明这段经历里你具体负责了什么、怎么做、结果如何。",
                    style,
                ),
                    competency,
                )
        opening_pool = [
            item["question"]
            for item in payload.get("opening", [])
            if item.get("question") and self._is_project_depth_question_text(item["question"])
        ]
        base_question = self._pick_question(opening_pool, used_questions, selector_seed) or DEFAULT_OPENING_BY_ROLE.get(
            role_code,
            "请先介绍一个你做过的代表性项目，重点说明你的职责、难点和结果。",
        )
        return self._apply_opening_difficulty(base_question, style), competency

    def get_question_for_competency(
        self,
        role_code: str,
        competency_code: str,
        used_questions: list[str] | None = None,
        selector_seed: str | int | None = None,
        style: str = "medium",
    ) -> str:
        payload = self._load_seed_payload(role_code)
        question_bank = self._load_question_bank(role_code)
        used_questions = used_questions or []

        if competency_code == "project_depth":
            project_pool: list[str] = []
            project_pool.extend(
                self._normalize_text(str(item.get("question", "")))
                for item in payload.get("competencies", {}).get(competency_code, [])
                if self._is_project_depth_question_text(str(item.get("question", "")))
            )
            project_pool.extend(
                item for item in question_bank.get(competency_code, [])
                if self._is_project_depth_question_text(item)
            )
            question = self._pick_question(project_pool, used_questions, selector_seed)
            if question:
                return self._apply_main_difficulty(question, style, competency_code)
            return self._apply_main_difficulty(
                "请结合一个你做过的代表性项目展开回答，说说你负责的部分和关键难点。",
                style,
                competency_code,
            )

        pool: list[str] = []
        pool.extend(
            self._normalize_text(str(item.get("question", "")))
            for item in payload.get("competencies", {}).get(competency_code, [])
        )
        pool.extend(question_bank.get(competency_code, []))
        if not pool:
            pool.extend(question_bank.get("__general__", []))
            pool.extend(self._normalize_text(str(item.get("question", ""))) for item in payload.get("opening", []))

        question = self._pick_question(pool, used_questions, selector_seed)
        if question:
            return self._apply_main_difficulty(question, style, competency_code)
        return self._apply_main_difficulty(
            f"请围绕 {competency_code} 结合一个真实经历展开回答。",
            style,
            competency_code,
        )

    def get_follow_up_question(
        self,
        role_code: str,
        follow_up_type: str,
        competency_code: str,
        answer_text: str,
        style: str = "medium",
    ) -> str:
        payload = self._load_seed_payload(role_code)
        template = payload.get("follow_up", {}).get(follow_up_type) or DEFAULT_FOLLOW_UP.get(follow_up_type) or DEFAULT_FOLLOW_UP["deepen"]
        cleaned_answer = self._normalize_text(answer_text)[:40]
        return self._apply_follow_up_difficulty(
            template.format(competency=competency_code, answer=cleaned_answer),
            style,
            follow_up_type,
        )

    def build_follow_up_candidates(
        self,
        role_code: str,
        competency_code: str,
        base_question: str,
        answer_text: str = "",
        style: str = "medium",
    ) -> list[dict]:
        payload = self._load_seed_payload(role_code)
        cleaned_answer = self._normalize_text(answer_text)[:36] or "你刚才的回答"
        candidate_map: dict[str, list[tuple[str, str]]] = {
            "deepen": [
                ("方案细节", f"继续围绕 {competency_code} 展开，说说你当时是怎么做的。"),
                ("取舍边界", f"这个 {competency_code} 场景里，你当时为什么这么选？"),
                ("结果验证", f"这个 {competency_code} 场景最后结果怎么样？"),
            ],
            "redirect": [
                ("回到核心", f"我们先回到这道题的核心。请直接回答：{base_question}"),
                ("聚焦一个点", f"先不要展开太多背景。请只围绕 {competency_code} 最关键的一点，重新用一个例子回答。"),
                ("一句结论", f"请先用一句话给出结论，再说明这个 {competency_code} 问题里你是怎么做的。"),
            ],
            "credibility": [
                ("个人职责", "请具体说明在这件事里你本人负责了什么，而不是团队整体做了什么。"),
                ("验证方式", f"你提到“{cleaned_answer}”。请补充你是如何验证这个做法真的有效的。"),
                ("量化结果", "请补充更可验证的结果，比如指标变化、上线效果或排查证据。"),
            ],
        }
        seed_follow_up = payload.get("follow_up", {})
        candidates: list[dict] = []
        for follow_up_type, items in candidate_map.items():
            seed_template = seed_follow_up.get(follow_up_type)
            if seed_template:
                candidates.append(
                    {
                        "question_text": self._apply_follow_up_difficulty(
                            seed_template.format(competency=competency_code, answer=cleaned_answer),
                            style,
                            follow_up_type,
                        ),
                        "follow_up_type": follow_up_type,
                        "competency_code": competency_code,
                        "angle": "题库模板",
                        "source": "seed",
                    }
                )
            for angle, question_text in items:
                candidates.append(
                    {
                        "question_text": self._apply_follow_up_difficulty(self._normalize_text(question_text), style, follow_up_type),
                        "follow_up_type": follow_up_type,
                        "competency_code": competency_code,
                        "angle": angle,
                        "source": "warmup",
                    }
                )

        unique: list[dict] = []
        seen: set[str] = set()
        for item in candidates:
            key = f"{item['follow_up_type']}::{item['question_text']}"
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def get_seed_examples(
        self,
        role_code: str,
        competency_code: str,
        count: int = 3,
    ) -> list[str]:
        """返回指定能力点的种子题目作为 few-shot 参考（不直接用于面试）"""
        payload = self._load_seed_payload(role_code)
        question_bank = self._load_question_bank(role_code)
        pool: list[str] = []
        pool.extend(
            self._normalize_text(str(item.get("question", "")))
            for item in payload.get("competencies", {}).get(competency_code, [])
        )
        pool.extend(question_bank.get(competency_code, []))
        if not pool:
            pool.extend(
                item["question"]
                for item in payload.get("opening", [])
                if item.get("question")
            )
        unique = list(dict.fromkeys(q for q in pool if q))
        return unique[:count]

    def _apply_opening_difficulty(self, question: str, style: str) -> str:
        normalized = self._normalize_text(question)
        if not normalized:
            return normalized
        return normalized

    def _apply_main_difficulty(self, question: str, style: str, competency_code: str) -> str:
        normalized = self._normalize_text(question)
        if not normalized:
            return normalized
        suffix = self._main_suffix_for_question(normalized, style, competency_code)
        if not suffix:
            return normalized
        return self._normalize_text(f"{normalized} {suffix}")

    def _apply_follow_up_difficulty(self, question: str, style: str, follow_up_type: str) -> str:
        normalized = self._normalize_text(question)
        if not normalized:
            return normalized
        return normalized

    def _pick_question(self, pool: list[str], used_questions: list[str], selector_seed: str | int | None) -> str:
        unique_pool = [
            item
            for item in dict.fromkeys(self._normalize_text(text) for text in pool if self._normalize_text(text))
            if self._is_valid_question_text(item)
        ]
        if not unique_pool:
            return ""
        ranked = sorted(
            unique_pool,
            key=lambda item: hashlib.sha1(f"{selector_seed}|{len(used_questions)}|{item}".encode("utf-8")).hexdigest(),
        )
        for item in ranked:
            if item not in used_questions:
                return item
        return ranked[0]

    def _is_valid_question_text(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        if not normalized:
            return False
        return not any(phrase in normalized for phrase in INVALID_QUESTION_PHRASES)

    def _is_project_depth_question_text(self, value: str) -> bool:
        normalized = self._normalize_text(value)
        if not self._is_valid_question_text(normalized):
            return False
        if any(pattern in normalized for pattern in PROJECT_DEPTH_INVALID_PATTERNS):
            return False
        return any(hint in normalized for hint in PROJECT_DEPTH_HINTS)

    def _extract_question_text(self, item: dict) -> str:
        parsed_meta = item.get("parsed_meta") or {}
        candidates = [
            parsed_meta.get("题目"),
            parsed_meta.get("棰樼洰"),
            item.get("title"),
        ]
        for candidate in candidates:
            normalized = self._normalize_text(str(candidate or ""))
            if normalized and len(normalized) >= 8:
                return normalized
        content = self._normalize_text(str(item.get("content", "")))
        for line in content.splitlines():
            clean = line.strip()
            if clean.startswith("题目:"):
                return clean.split(":", 1)[1].strip()
            if clean.startswith("棰樼洰:"):
                repaired = self._repair_mojibake(clean)
                if ":" in repaired:
                    return repaired.split(":", 1)[1].strip()
        return ""

    def _normalize_text(self, value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        text = self._repair_mojibake(text)
        text = text.replace("\u3000", " ").replace("\xa0", " ")
        return " ".join(text.split())

    def _normalize_resume_fragment(self, value: str) -> str:
        text = self._normalize_text(value)
        if len(text) <= 42:
            return text
        return f"{text[:39]}..."

    def _main_suffix_for_question(self, question: str, style_code: str, competency_code: str) -> str:
        return ""

    def _is_project_or_scenario_question(self, question: str, competency_code: str) -> bool:
        if competency_code == "project_depth":
            return True
        if self._is_comparison_question(question) or self._is_mechanism_question(question) or self._is_concept_question(question):
            return False
        scenario_markers = (
            "请介绍",
            "结合一个真实项目",
            "如果在项目里遇到",
            "如果让你设计",
            "职责",
            "方案",
            "模块",
            "项目",
            "结果",
            "复盘",
        )
        return any(marker in question for marker in scenario_markers)

    def _is_comparison_question(self, question: str) -> bool:
        comparison_markers = (
            "请对比",
            "怎么比较",
            "应该怎么比较",
            "优缺点",
            "适用场景",
            "如何选择",
        )
        return any(marker in question for marker in comparison_markers)

    def _is_mechanism_question(self, question: str) -> bool:
        mechanism_markers = (
            "从机制角度",
            "为什么能工作",
            "关键约束",
            "底层原理",
            "机制",
        )
        return any(marker in question for marker in mechanism_markers)

    def _is_concept_question(self, question: str) -> bool:
        concept_markers = (
            "请解释",
            "核心概念",
            "主要解决什么问题",
        )
        return any(marker in question for marker in concept_markers)

    def _repair_mojibake(self, value: str) -> str:
        text = value.strip()
        if not text:
            return ""
        suspicious_markers = ("璇", "鍥", "缁", "闈", "鏄", "棰", "锛", "銆")
        if not any(marker in text for marker in suspicious_markers):
            return text
        for encoding in ("gb18030", "gbk"):
            try:
                repaired = text.encode(encoding, errors="ignore").decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if repaired and repaired.count("?") <= text.count("?") and not any(marker in repaired for marker in ("璇", "鍥", "缁", "闈")):
                return repaired
        return text

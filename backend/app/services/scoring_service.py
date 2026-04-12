import logging
import re
from collections import Counter
from statistics import mean

from app.audio.analysis import analyze_audio, map_audio_scores
from app.schemas.interview import RetrievalEvidence
from app.schemas.resume import ResumeSummary
from app.services.interview_difficulty import normalize_difficulty
from app.services.prompt_service import PromptService
from app.utils.text import extract_keywords, keyword_hits, sentence_count


logger = logging.getLogger(__name__)

# 难度系数：影响 quality flag 惩罚上限和评分宽严
DIFFICULTY_SCALING = {
    "simple": {"penalty_scale": 0.7, "base_bonus": 2, "label": "简单"},
    "medium": {"penalty_scale": 1.0, "base_bonus": 0, "label": "中等"},
    "hard":   {"penalty_scale": 1.3, "base_bonus": -1, "label": "困难"},
}
LOGIC_MARKERS = [
    "首先",
    "然后",
    "最后",
    "因此",
    "所以",
    "接着",
    "总结",
]
CREDIBILITY_MARKERS = [
    "负责",
    "指标",
    "结果",
    "排查",
    "方案",
    "取舍",
    "上线",
    "压测",
    "监控",
    "优化",
]
CONFUSION_MARKERS = [
    "不知道",
    "不太清楚",
    "不清楚",
    "不理解",
    "没听懂",
    "没看懂",
    "什么意思",
    "啥意思",
    "不会",
    "答不上来",
    "不懂",
    "don't know",
    "not sure",
    "i don't know",
    "i do not know",
    "what do you mean",
]
LOW_SIGNAL_MARKERS = [
    "随便",
    "乱说",
    "胡说",
    "瞎说",
    "哈哈",
    "呵呵",
    "嗯",
    "额",
    "啊",
    "哦",
]
RESUME_DUMP_MARKERS = [
    "当前简历和",
    "亮点：",
    "风险点：",
]
GENERATED_TEMPLATE_MARKERS = [
    "回答模板",
    "适合面试",
    "适合面试/实验报告/课程设计",
    "实验报告",
    "课程设计",
    "下面给你一个",
    "我会用一个典型的",
    "详细对比表",
]
PROJECT_QUESTION_MARKERS = [
    "真实项目",
    "职责",
    "复盘",
    "如何验证",
    "压测",
    "瓶颈",
    "你在处理",
]
SEVERE_DIAGNOSTIC_MARKERS = [
    "严重偏题",
    "完全答非所问",
    "未实际回答题目",
    "完全未回应",
    "无任何逻辑关联",
    "典型偏题",
]
TEMPLATE_DIAGNOSTIC_MARKERS = [
    "回答模板",
    "未使用简历中真实项目",
    "虚构或迁移风险",
    "脱离岗位匹配主线",
    "未结合自身项目",
]


class ScoringService:
    def __init__(self) -> None:
        self.prompt_service = PromptService()

    def score_answer_fast(
        self,
        role_code: str,
        competency_code: str,
        question_text: str,
        answer_text: str,
        evidence: list[RetrievalEvidence],
        difficulty: str = "medium",
    ) -> dict:
        payload, _, _ = self._build_base_score_payload(
            role_code=role_code,
            competency_code=competency_code,
            question_text=question_text,
            answer_text=answer_text,
            evidence=evidence,
            audio_path=None,
            difficulty=difficulty,
        )
        return payload

    def score_answer(
        self,
        role_code: str,
        competency_code: str,
        question_text: str,
        answer_text: str,
        evidence: list[RetrievalEvidence],
        audio_path=None,
        retrieval_backend: str = "unknown",
        resume_summary: ResumeSummary | None = None,
        difficulty: str = "medium",
    ) -> tuple[dict, dict, dict]:
        base_payload, features, facts = self._build_base_score_payload(
            role_code=role_code,
            competency_code=competency_code,
            question_text=question_text,
            answer_text=answer_text,
            evidence=evidence,
            audio_path=audio_path,
            difficulty=difficulty,
        )
        fallback_strengths = facts["fallback_strengths"]
        fallback_risks = facts["fallback_risks"]
        fallback_prompt_result = {
            "summary": facts["fallback_explanation"],
            "strengths": fallback_strengths,
            "risks": fallback_risks,
            "suggestions": base_payload["suggestions"],
        }
        retrieval_context = self._build_retrieval_context(evidence)
        resume_context = self._build_resume_context(resume_summary, role_code)
        prompt_result, fallback_used = self.prompt_service.run_json_prompt(
            "score_answer",
            {
                "task_context": {
                    "role_code": role_code,
                    "competency_code": competency_code,
                    "stage": "score_answer",
                    "difficulty": difficulty,
                },
                "conversation_context": {
                    "question_text": question_text,
                    "answer_text": answer_text,
                },
                "resume_context": resume_context,
                "retrieval_context": retrieval_context,
                "draft": {
                    "overall_score": base_payload["overall_score"],
                    "text_scores": base_payload["text_scores"],
                    "audio_scores": base_payload["audio_scores"],
                    "summary": facts["fallback_explanation"],
                    "strengths": fallback_strengths,
                    "risks": fallback_risks,
                    "suggestions": base_payload["suggestions"],
                    "quality_flags": facts["quality_flags"],
                },
            },
            fallback_result=fallback_prompt_result,
        )

        # --- 混合评分：规则引擎 × 0.2 + LLM 调整 × 0.8 ---
        if not fallback_used:
            base_payload = self._merge_llm_scores(base_payload, prompt_result)
        base_payload = self._apply_post_merge_guardrails(
            base_payload,
            prompt_result,
            facts["quality_flags"],
        )

        summary = str(prompt_result.get("summary") or facts["fallback_explanation"]).strip() or facts["fallback_explanation"]
        strengths = self._normalize_text_list(prompt_result.get("strengths"), fallback_strengths)
        risks = self._normalize_text_list(prompt_result.get("risks"), fallback_risks)
        suggestions = self._normalize_text_list(prompt_result.get("suggestions"), base_payload["suggestions"])[:3]
        explanation = self._compose_explanation(summary, strengths, risks)
        debug_payload = {
            "prompt": "score_answer",
            "prompt_result": prompt_result,
            "fallback_used": fallback_used,
            "facts": {
                "question_keywords": facts["combined_keywords"],
                "answer_length": facts["answer_length"],
                "sentences": facts["sentences"],
                "keyword_match_count": facts["keyword_match_count"],
                "question_keyword_hits": facts["question_keyword_hits"],
                "evidence_keyword_hits": facts["evidence_keyword_hits"],
                "quality_flags": facts["quality_flags"],
            },
            "retrieval": {
                "backend": retrieval_backend,
                "evidence_count": len(retrieval_context),
            },
            "resume_context": resume_context,
        }
        logger.info(
            "prompt context prepared | prompt_name=%s role_code=%s competency_code=%s retrieval_backend=%s evidence_count=%s",
            "score_answer",
            role_code,
            competency_code,
            retrieval_backend,
            len(retrieval_context),
        )
        logger.info(
            "score generated | role_code=%s competency_code=%s overall_score=%s evidence_count=%s answer_length=%s fallback_used=%s quality_flags=%s",
            role_code,
            competency_code,
            base_payload["overall_score"],
            len(evidence),
            facts["answer_length"],
            fallback_used,
            facts["quality_flags"],
        )
        return (
            {
                **base_payload,
                "explanation": explanation,
                "suggestions": suggestions,
                "ai_generated": not fallback_used,
                "degraded": fallback_used,
            },
            features,
            debug_payload,
        )

    def _build_base_score_payload(
        self,
        role_code: str,
        competency_code: str,
        question_text: str,
        answer_text: str,
        evidence: list[RetrievalEvidence],
        audio_path=None,
        difficulty: str = "medium",
    ) -> tuple[dict, dict, dict]:
        difficulty = normalize_difficulty(difficulty)
        diff_cfg = DIFFICULTY_SCALING.get(difficulty, DIFFICULTY_SCALING["medium"])
        penalty_scale = diff_cfg["penalty_scale"]
        base_bonus = diff_cfg["base_bonus"]

        question_keywords = extract_keywords(question_text)
        evidence_keywords: list[str] = []
        for item in evidence:
            evidence_keywords.extend(extract_keywords(item.snippet))
        question_keywords = list(dict.fromkeys(question_keywords))[:12]
        evidence_keywords = list(dict.fromkeys(evidence_keywords))[:12]
        answer_keywords = extract_keywords(answer_text)
        unique_answer_keywords = list(dict.fromkeys(answer_keywords))

        answer_length = len(answer_text.strip())
        sentences = sentence_count(answer_text)
        question_keyword_hits = keyword_hits(answer_text, question_keywords)
        evidence_keyword_hits = keyword_hits(answer_text, evidence_keywords)
        # 总命中数 = 问题关键词 + evidence 关键词（去重后独立计算，不再双重计数）
        keyword_match_count = question_keyword_hits + evidence_keyword_hits
        logic_marker_count = keyword_hits(answer_text, LOGIC_MARKERS)
        credibility_marker_count = keyword_hits(answer_text, CREDIBILITY_MARKERS)
        quality_flags = self._detect_quality_flags(
            question_text=question_text,
            answer_text=answer_text,
            answer_length=answer_length,
            sentences=sentences,
            keyword_match_count=keyword_match_count,
            question_keyword_hits=question_keyword_hits,
            evidence_keyword_hits=evidence_keyword_hits,
            question_keywords=question_keywords,
            answer_keywords=answer_keywords,
        )

        has_digits = any(char.isdigit() for char in answer_text)
        # --- 评分公式（base 分大幅降低，拉开区分度；base_bonus 按难度微调）---
        accuracy = min(
            100,
            max(0, 3 + base_bonus)
            + question_keyword_hits * 3
            + evidence_keyword_hits * 2
            + credibility_marker_count * 4
            + (6 if has_digits else 0)
            + (6 if answer_length >= 80 and question_keyword_hits >= 2 else 0),
        )
        completeness = min(
            100,
            max(0, 3 + base_bonus)
            + min(sentences, 8) * 6
            + min(question_keyword_hits, 5) * 3
            + min(evidence_keyword_hits, 4) * 2
            + (6 if answer_length >= 100 else 0),
        )
        logic = min(
            100,
            max(0, 5 + base_bonus)
            + min(sentences, 8) * 5
            + logic_marker_count * 8
            + (6 if answer_length >= 60 else 0)
            + (6 if sentences >= 3 and logic_marker_count >= 2 else 0),
        )
        job_fit = min(
            100,
            max(0, 3 + base_bonus)
            + keyword_hits(answer_text, [role_code, competency_code, "项目", "性能", "设计", "优化", "架构", "前端"]) * 6
            + min(question_keyword_hits, 5) * 2
            + min(evidence_keyword_hits, 4) * 3,
        )
        credibility = min(
            100,
            max(0, 3 + base_bonus)
            + credibility_marker_count * 7
            + min(evidence_keyword_hits, 3) * 2
            + (10 if has_digits else 0)
            + (6 if answer_length >= 80 and credibility_marker_count >= 2 else 0),
        )

        if not any(quality_flags.values()):
            substantive_bonus = 0
            if answer_length >= 120 and sentences >= 3:
                substantive_bonus += 4
            if has_digits:
                substantive_bonus += 3
            if credibility_marker_count >= 2:
                substantive_bonus += 4
            if question_keyword_hits + evidence_keyword_hits >= 2:
                substantive_bonus += 3
            accuracy = min(100, accuracy + substantive_bonus)
            completeness = min(100, completeness + substantive_bonus + 2)
            logic = min(100, logic + max(2, substantive_bonus // 2))
            job_fit = min(100, job_fit + substantive_bonus)
            credibility = min(100, credibility + substantive_bonus + 3)

        def _cap(base_cap: int) -> int:
            """难度越高惩罚越严: hard(1.3)→上限更低, simple(0.7)→上限更高"""
            return max(0, int(base_cap / penalty_scale))

        if quality_flags["confused"]:
            accuracy = min(accuracy, _cap(8))
            completeness = min(completeness, _cap(6))
            logic = min(logic, _cap(8))
            job_fit = min(job_fit, _cap(6))
            credibility = min(credibility, _cap(5))

        if quality_flags["gibberish"]:
            accuracy = min(accuracy, _cap(5))
            completeness = min(completeness, _cap(4))
            logic = min(logic, _cap(5))
            job_fit = min(job_fit, _cap(4))
            credibility = min(credibility, _cap(3))

        if quality_flags["off_topic"]:
            accuracy = min(accuracy, _cap(8))
            completeness = min(completeness, _cap(10))
            logic = min(logic, _cap(12))
            job_fit = min(job_fit, _cap(6))
            credibility = min(credibility, _cap(8))

        if quality_flags["low_signal"]:
            accuracy = min(accuracy, _cap(15))
            completeness = min(completeness, _cap(12))
            logic = min(logic, _cap(15))
            job_fit = min(job_fit, _cap(14))
            credibility = min(credibility, _cap(10))

        if quality_flags["question_echo"]:
            accuracy = min(accuracy, _cap(10))
            completeness = min(completeness, _cap(10))
            logic = min(logic, _cap(12))
            job_fit = min(job_fit, _cap(10))
            credibility = min(credibility, _cap(8))

        if quality_flags["repetitive"]:
            completeness = min(completeness, _cap(16))
            logic = min(logic, _cap(14))
            credibility = min(credibility, _cap(12))

        if quality_flags["keyword_stuffing"]:
            accuracy = min(accuracy, _cap(16))
            completeness = min(completeness, _cap(18))
            logic = min(logic, _cap(16))
            job_fit = min(job_fit, _cap(18))
            credibility = min(credibility, _cap(12))

        if evidence and evidence_keyword_hits == 0 and question_keyword_hits <= 1:
            accuracy = min(accuracy, 20)
            job_fit = min(job_fit, 18)

        text_scores = {
            "accuracy": round(max(0, accuracy), 2),
            "completeness": round(max(0, completeness), 2),
            "logic": round(max(0, logic), 2),
            "job_fit": round(max(0, job_fit), 2),
            "credibility": round(max(0, credibility), 2),
        }

        features = analyze_audio(audio_path) if audio_path else {
            "status": "unavailable",
            "volume_stability": None,
            "pause_ratio": None,
            "speech_rate": None,
            "pitch_variation": None,
            "voiced_ratio": None,
        }
        audio_scores = map_audio_scores(features)
        audio_value = 0.0
        if audio_scores.get("status") == "available":
            audio_value = mean([
                audio_scores["confidence"],
                audio_scores["clarity"],
                audio_scores["fluency"],
                audio_scores["emotion"],
            ])

        text_value = mean(text_scores.values())
        overall = round(text_value * 0.9 + audio_value * 0.1, 2) if audio_value else round(text_value, 2)
        if quality_flags["confused"]:
            overall = min(overall, _cap(8))
        elif quality_flags["gibberish"]:
            overall = min(overall, _cap(5))
        elif quality_flags["off_topic"] or quality_flags["question_echo"]:
            overall = min(overall, _cap(10))
        elif quality_flags["low_signal"] or quality_flags["keyword_stuffing"] or quality_flags["repetitive"]:
            overall = min(overall, _cap(16))

        fallback_strengths = self._fallback_strengths(text_scores, quality_flags)
        fallback_risks = self._fallback_risks(text_scores, quality_flags)
        fallback_explanation, fallback_suggestions = self._build_fallback_feedback(
            competency_code=competency_code,
            text_scores=text_scores,
            quality_flags=quality_flags,
        )
        return (
            {
                "competency_code": competency_code,
                "overall_score": overall,
                "text_scores": text_scores,
                "audio_scores": audio_scores,
                "explanation": fallback_explanation,
                "suggestions": fallback_suggestions,
            },
            features,
            {
                "combined_keywords": list(dict.fromkeys(question_keywords + evidence_keywords)),
                "answer_length": answer_length,
                "sentences": sentences,
                "keyword_match_count": keyword_match_count,
                "question_keyword_hits": question_keyword_hits,
                "evidence_keyword_hits": evidence_keyword_hits,
                "unique_answer_keywords": len(unique_answer_keywords),
                "fallback_strengths": fallback_strengths,
                "fallback_risks": fallback_risks,
                "fallback_explanation": fallback_explanation,
                "quality_flags": quality_flags,
            },
        )

    def _detect_quality_flags(
        self,
        question_text: str,
        answer_text: str,
        answer_length: int,
        sentences: int,
        keyword_match_count: int,
        question_keyword_hits: int,
        evidence_keyword_hits: int,
        question_keywords: list[str],
        answer_keywords: list[str],
    ) -> dict[str, bool]:
        lowered = answer_text.lower()
        normalized = re.sub(r"\s+", "", lowered)
        normalized_question = re.sub(r"\s+", "", question_text.lower())
        confusion = any(marker in lowered or marker.replace(" ", "") in normalized for marker in CONFUSION_MARKERS)
        filler_only = normalized in {"嗯", "啊", "哦", "额", "不知道", "不懂", "不会"}
        filler_hit = any(marker in normalized for marker in LOW_SIGNAL_MARKERS)
        extracted = list(dict.fromkeys(answer_keywords))
        raw_tokens = re.findall(r"[a-zA-Z0-9_+#.-]+|[\u4e00-\u9fff]", lowered)
        keyword_free = keyword_match_count == 0 and question_keyword_hits == 0
        very_short = answer_length <= 8
        low_signal = filler_only or very_short or (answer_length < 20 and keyword_free) or (sentences <= 1 and keyword_free and answer_length < 40)
        gibberish = filler_only or (keyword_free and len(extracted) <= 1 and answer_length < 24) or (filler_hit and answer_length < 24)
        novel_keywords = [item for item in extracted if item not in question_keywords]
        repeated_ratio = 0.0
        if answer_keywords:
            repeated_ratio = Counter(answer_keywords).most_common(1)[0][1] / len(answer_keywords)
        unique_ratio = len(extracted) / max(len(answer_keywords), 1)
        raw_unique_ratio = len(set(raw_tokens)) / max(len(raw_tokens), 1)
        resume_summary_dump = all(marker in answer_text for marker in RESUME_DUMP_MARKERS)
        generated_template = any(marker in answer_text for marker in GENERATED_TEMPLATE_MARKERS)
        project_question = any(marker in question_text for marker in PROJECT_QUESTION_MARKERS)
        project_mismatch = project_question and (resume_summary_dump or generated_template)
        off_topic = (
            resume_summary_dump
            or (answer_length >= 10 and question_keyword_hits == 0 and evidence_keyword_hits == 0 and not confusion)
        )
        question_echo = (
            bool(normalized_question)
            and answer_length <= max(len(question_text) + 24, int(len(question_text) * 1.5))
            and question_keyword_hits >= max(2, len(question_keywords) // 2)
            and len(novel_keywords) <= 2
        )
        repetitive = answer_length >= 40 and (
            repeated_ratio >= 0.35
            or unique_ratio <= 0.45
            or raw_unique_ratio <= 0.35
        )
        keyword_stuffing = (
            (
                answer_length >= 80
                and question_keyword_hits >= max(3, len(question_keywords) // 2)
                and evidence_keyword_hits <= 1
                and len(novel_keywords) <= 2
            )
            or (
                answer_length >= 120
                and sentences <= 2
                and question_keyword_hits >= 3
                and evidence_keyword_hits <= 1
            )
        )
        return {
            "confused": confusion,
            "low_signal": low_signal or confusion,
            "gibberish": gibberish or (confusion and answer_length <= 12),
            "off_topic": off_topic,
            "question_echo": question_echo,
            "repetitive": repetitive,
            "keyword_stuffing": keyword_stuffing,
            "resume_summary_dump": resume_summary_dump,
            "generated_template": generated_template,
            "project_mismatch": project_mismatch,
        }

    def _apply_post_merge_guardrails(self, base_payload: dict, prompt_result: dict, quality_flags: dict[str, bool]) -> dict:
        diagnostics = " ".join(
            [
                str(prompt_result.get("summary") or ""),
                *[str(item) for item in prompt_result.get("risks", []) if str(item).strip()],
            ]
        )
        if quality_flags.get("resume_summary_dump") or any(marker in diagnostics for marker in SEVERE_DIAGNOSTIC_MARKERS):
            return self._cap_payload_scores(
                base_payload,
                text_caps={
                    "accuracy": 18,
                    "completeness": 16,
                    "logic": 18,
                    "job_fit": 12,
                    "credibility": 10,
                },
                overall_cap=18,
            )
        if quality_flags.get("project_mismatch") or quality_flags.get("generated_template") or any(marker in diagnostics for marker in TEMPLATE_DIAGNOSTIC_MARKERS):
            return self._cap_payload_scores(
                base_payload,
                text_caps={
                    "accuracy": 32,
                    "completeness": 34,
                    "logic": 36,
                    "job_fit": 24,
                    "credibility": 20,
                },
                overall_cap=32,
            )
        return base_payload

    def _cap_payload_scores(self, base_payload: dict, text_caps: dict[str, float], overall_cap: float) -> dict:
        capped_text_scores = {
            key: round(min(float(base_payload["text_scores"].get(key, 0.0)), cap), 2)
            for key, cap in text_caps.items()
        }
        base_payload["text_scores"] = capped_text_scores
        base_payload["overall_score"] = round(min(float(base_payload.get("overall_score", 0.0)), overall_cap), 2)
        return base_payload

    def _build_fallback_feedback(self, competency_code: str, text_scores: dict[str, float], quality_flags: dict[str, bool]) -> tuple[str, list[str]]:
        if quality_flags["confused"]:
            return (
                f"这道 {competency_code} 题里，候选人已经明确表达对题意不够理解，因此当前回答暂时无法支撑有效评估。",
                [
                    "先确认题目在问什么，再用一个最熟悉的相关项目举例。",
                    "如果暂时没有思路，直接说明做过的最接近场景和自己负责的部分。",
                    "避免用‘不知道’结束回答，至少补一句你做过的相近经验。",
                ],
            )
        if quality_flags["off_topic"] or quality_flags["question_echo"]:
            return (
                f"这道 {competency_code} 题的回答没有真正切中题目核心，当前内容更多是偏题或重复题干，无法支撑有效评估。",
                [
                    "先用一句话直接回答题目核心，再补充原因和做法。",
                    "不要重复题目表述，直接说明你的判断、方案或结论。",
                    "补一个与你亲自处理过的具体场景，避免空泛绕述。",
                ],
            )
        if quality_flags["gibberish"] or quality_flags["low_signal"] or quality_flags["keyword_stuffing"] or quality_flags["repetitive"]:
            return (
                f"这道 {competency_code} 题的回答信息量明显不足，缺少可供继续评估的有效技术细节。",
                [
                    "先给出一句结论，再补充你具体负责的模块。",
                    "至少说清楚遇到的问题、采取的做法和最终结果中的一项。",
                    "不要只给口头化短句，尽量补一个可验证的事实或结果。",
                ],
            )
        return (
            f"本题围绕 {competency_code} 进行评估。回答在准确度、完整度和可信度上分别为 "
            f"{text_scores['accuracy']} / {text_scores['completeness']} / {text_scores['credibility']}。",
            [
                "先给结论，再补充原理、场景和取舍。",
                "补充量化结果和个人贡献，增强项目可信度。",
                "回答项目题时按背景、做法和结果组织，减少泛泛而谈。",
            ],
        )

    def _build_retrieval_context(self, evidence: list[RetrievalEvidence]) -> list[dict]:
        return [
            {
                "title": item.title,
                "snippet": item.snippet,
                "competency_code": item.competency_code,
                "score": item.score,
                "source_type": item.doc_type,
            }
            for item in evidence[:4]
        ]

    def _build_resume_context(self, summary: ResumeSummary | None, role_code: str) -> dict | None:
        if not summary:
            return None
        current_job_match = next((item for item in summary.job_matches if item.position_code == role_code), summary.best_job_match)
        return {
            "highlights": summary.highlights[:4],
            "risk_points": summary.risk_points[:4],
            "tech_stack": summary.tech_stack[:8],
            "interview_focuses": summary.interview_focuses[:4],
            "current_job_match": current_job_match.model_dump() if current_job_match else None,
        }

    def _fallback_strengths(self, text_scores: dict[str, float], quality_flags: dict[str, bool]) -> list[str]:
        if (
            quality_flags["confused"]
            or quality_flags["gibberish"]
            or quality_flags["off_topic"]
            or quality_flags["question_echo"]
        ):
            return []
        strengths: list[str] = []
        if text_scores["logic"] >= 70:
            strengths.append("回答结构比较清晰，能按步骤展开。")
        if text_scores["job_fit"] >= 70:
            strengths.append("内容和岗位能力维度有一定贴合。")
        if text_scores["credibility"] >= 70:
            strengths.append("回答里有一定的项目细节或可验证线索。")
        return strengths or ["回答覆盖了部分核心思路。"]

    def _fallback_risks(self, text_scores: dict[str, float], quality_flags: dict[str, bool]) -> list[str]:
        risks: list[str] = []
        if quality_flags["confused"]:
            risks.append("候选人已经明确表示未理解题意，当前回答无法继续深挖。")
            return risks
        if quality_flags["off_topic"]:
            risks.append("回答偏离题目核心，没有正面回应关键问题。")
        if quality_flags["question_echo"]:
            risks.append("回答主要在重复题干，缺少新的有效信息。")
        if quality_flags["gibberish"] or quality_flags["low_signal"]:
            risks.append("回答信息量过低，缺少可验证事实和技术细节。")
        if quality_flags["keyword_stuffing"] or quality_flags["repetitive"]:
            risks.append("回答存在堆砌词汇或重复表述，技术判断和论证不足。")
        if text_scores["accuracy"] < 70:
            risks.append("关键技术点还不够准确，容易停留在概念层。")
        if text_scores["completeness"] < 70:
            risks.append("缺少方案取舍、落地步骤或结果闭环。")
        if text_scores["credibility"] < 70:
            risks.append("缺少量化结果、个人贡献或可核验细节。")
        return risks or ["可以继续补充更具体的项目结果和取舍。"]

    def _compose_explanation(self, summary: str, strengths: list[str], risks: list[str]) -> str:
        parts = [summary]
        if strengths:
            parts.append(f"优势：{'；'.join(strengths[:2])}")
        if risks:
            parts.append(f"风险：{'；'.join(risks[:2])}")
        return " ".join(part.strip() for part in parts if part.strip())

    def _merge_llm_scores(self, base_payload: dict, llm_result: dict) -> dict:
        """混合规则引擎分数和 LLM 调整分数: rule × 0.4 + llm × 0.6"""
        RULE_WEIGHT = 0.2
        LLM_WEIGHT = 0.8
        MAX_DELTA = 20

        llm_text = llm_result.get("text_scores")
        if isinstance(llm_text, dict):
            merged_text = {}
            for dim in ("accuracy", "completeness", "logic", "job_fit", "credibility"):
                rule_val = base_payload["text_scores"].get(dim, 0)
                llm_val = llm_text.get(dim)
                if isinstance(llm_val, (int, float)):
                    clamped = max(rule_val - MAX_DELTA, min(rule_val + MAX_DELTA, float(llm_val)))
                    merged_text[dim] = round(rule_val * RULE_WEIGHT + clamped * LLM_WEIGHT, 2)
                else:
                    merged_text[dim] = rule_val
            base_payload["text_scores"] = merged_text

        llm_overall = llm_result.get("overall_score")
        if isinstance(llm_overall, (int, float)):
            rule_overall = base_payload["overall_score"]
            clamped = max(rule_overall - MAX_DELTA, min(rule_overall + MAX_DELTA, float(llm_overall)))
            base_payload["overall_score"] = round(rule_overall * RULE_WEIGHT + clamped * LLM_WEIGHT, 2)

        return base_payload

    def _normalize_text_list(self, payload, fallback: list[str]) -> list[str]:
        if not isinstance(payload, list):
            return fallback
        values = [str(item).strip() for item in payload if str(item).strip()]
        return values or fallback

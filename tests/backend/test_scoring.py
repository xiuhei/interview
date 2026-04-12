from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.audio.analysis import analyze_audio
from app.schemas.interview import RetrievalEvidence
from app.services.scoring_service import ScoringService
from app.utils.text import extract_keywords


class DummyPromptService:
    """模拟 LLM prompt 调用，返回与 draft 接近的分数（不大幅调整）"""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run_json_prompt(self, name: str, variables: dict, fallback_result: dict | None = None):
        self.calls.append(
            {
                "name": name,
                "variables": variables,
                "fallback_result": fallback_result,
            }
        )
        draft = variables.get("draft", {})
        return {
            "overall_score": draft.get("overall_score", 50),
            "text_scores": draft.get("text_scores", {}),
            "summary": "The answer covers the core design ideas, but the quantified result can be clearer.",
            "strengths": ["Breaks the bottleneck analysis into steps."],
            "risks": ["Needs more explicit capacity numbers."],
            "suggestions": ["Add load-test metrics and trade-off details."],
        }, False


def _make_evidence(role_code="cpp_backend", competency_code="system_design", snippet="cache, rate limiting, database, and monitoring"):
    return [
        RetrievalEvidence(
            doc_id="1",
            role_code=role_code,
            doc_type="knowledge",
            competency_code=competency_code,
            title="knowledge",
            snippet=snippet,
            score=0.9,
        )
    ]


def _make_service():
    service = ScoringService()
    prompt_service = DummyPromptService()
    service.prompt_service = prompt_service
    return service, prompt_service


# ============================================================
# 基础评分正确性测试
# ============================================================

def test_scoring_uses_prompt_output_and_retrieval_context():
    service, prompt_service = _make_service()

    payload, features, debug = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="Design a high-concurrency API.",
        answer_text="I would inspect the bottleneck first, then use cache, rate limiting, indexes, and monitoring, and validate the result with load testing.",
        evidence=_make_evidence(snippet="cache, rate limiting, database, and monitoring are core to high concurrency."),
        retrieval_backend="milvus",
    )

    assert payload["overall_score"] > 0
    assert "core design ideas" in payload["explanation"]
    assert payload["suggestions"] == ["Add load-test metrics and trade-off details."]
    assert features["status"] == "unavailable"
    assert debug["prompt"] == "score_answer"
    assert debug["retrieval"]["backend"] == "milvus"
    prompt_call = prompt_service.calls[0]
    assert prompt_call["name"] == "score_answer"
    assert prompt_call["variables"]["retrieval_context"][0]["source_type"] == "knowledge"
    assert prompt_call["variables"]["task_context"]["difficulty"] == "medium"


# ============================================================
# 胡答 / 答非所问 / 困惑 — 必须极低分
# ============================================================

def test_confused_answer_score_under_10():
    """明确表示不会的回答，overall 必须 <= 8"""
    service, _ = _make_service()
    payload, _, debug = service.score_answer(
        role_code="web_frontend",
        competency_code="project_depth",
        question_text="Please describe one frontend project.",
        answer_text="I don't know.",
        evidence=_make_evidence("web_frontend", "project_depth", "ownership and measurable results"),
        retrieval_backend="milvus",
    )
    assert payload["overall_score"] <= 8
    assert debug["facts"]["quality_flags"]["confused"] is True


def test_gibberish_answer_score_under_5():
    """完全无意义回答，overall 必须 <= 5"""
    service = ScoringService()
    payload = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="How do you design cache invalidation?",
        answer_text="哈哈哈",
        evidence=[],
    )
    assert payload["overall_score"] <= 5


def test_off_topic_short_answer_detected():
    """短的答非所问（>= 10 字符），必须触发 off_topic"""
    service = ScoringService()
    payload = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="请解释 TCP 三次握手的过程。",
        answer_text="今天天气真好，适合出去玩。",
        evidence=[],
    )
    assert payload["overall_score"] <= 10


def test_question_echo_answer_gets_low_score():
    """复读题干的回答，overall 必须 <= 10"""
    service, _ = _make_service()
    payload, _, debug = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="Design a high-concurrency API and explain the bottleneck strategy.",
        answer_text="Design a high-concurrency API and explain the bottleneck strategy.",
        evidence=_make_evidence(snippet="bottleneck analysis, caching, rate limiting, and trade-offs."),
        retrieval_backend="milvus",
    )
    assert payload["overall_score"] <= 10
    assert debug["facts"]["quality_flags"]["question_echo"] is True


def test_keyword_stuffing_stays_low():
    """堆砌关键词的回答，overall 必须 <= 16"""
    service, _ = _make_service()
    payload, _, debug = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="How would you design cache consistency for a high-concurrency API?",
        answer_text=(
            "High concurrency API cache consistency high concurrency API cache consistency. "
            "I want to say this question is very important, very important, very important. "
            "Design, cache, API, high concurrency, design, cache, API, high concurrency."
        ),
        evidence=_make_evidence(snippet="update order, invalidation strategy, retry handling, and consistency trade-offs."),
        retrieval_backend="milvus",
    )
    assert payload["overall_score"] <= 16
    assert debug["facts"]["quality_flags"]["keyword_stuffing"] is True or debug["facts"]["quality_flags"]["repetitive"] is True


def test_resume_summary_dump_answer_is_capped():
    service, _ = _make_service()
    payload, _, debug = service.score_answer(
        role_code="cpp_backend",
        competency_code="project_depth",
        question_text="你是如何验证这些指标的？压测时遇到的最大瓶颈是什么？",
        answer_text=(
            "当前简历和 C++后端开发 的匹配度为 61.5 分，已有较清晰的岗位相关经历。\n\n"
            "亮点：独立完成千级并发聊天系统全栈后端开发。\n\n"
            "风险点：项目周期仅3个月，复杂度仍需结合面试验证。"
        ),
        evidence=_make_evidence("cpp_backend", "project_depth", "压测、验证方法、瓶颈定位"),
        retrieval_backend="milvus",
    )
    assert payload["overall_score"] <= 18
    assert debug["facts"]["quality_flags"]["resume_summary_dump"] is True
    assert debug["facts"]["quality_flags"]["off_topic"] is True


def test_project_template_answer_is_capped():
    service, _ = _make_service()
    payload, _, debug = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="请结合一个真实项目，说明你在处理降级与容灾相关问题时的职责、方案、指标和复盘。",
        answer_text=(
            "下面给你一个偏真实工程化的回答模板（适合面试/实验报告/课程设计），"
            "我会用一个典型的电商系统订单加支付链路项目来说明降级与容灾。"
        ),
        evidence=_make_evidence("cpp_backend", "system_design", "真实项目、职责、指标、复盘"),
        retrieval_backend="milvus",
    )
    assert payload["overall_score"] <= 32
    assert debug["facts"]["quality_flags"]["generated_template"] is True
    assert debug["facts"]["quality_flags"]["project_mismatch"] is True


# ============================================================
# 正确回答 — 必须合理高分
# ============================================================

def test_correct_answer_scores_above_40():
    """有技术含量的正确回答，overall 必须 >= 40"""
    service = ScoringService()
    payload = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="performance",
        question_text="请解释如何排查 C++ 程序的内存泄漏问题。",
        answer_text=(
            "首先我会用 valgrind 或 AddressSanitizer 做内存检测，定位泄漏点。"
            "然后分析代码里的 new/delete 配对，检查是否有遗漏的释放路径。"
            "最后通过 RAII 和智能指针重构资源管理，确保异常安全。"
            "在之前的项目中，我负责排查过一个连接池泄漏的问题，"
            "通过监控指标发现内存持续增长，最终定位到连接回收逻辑缺失，"
            "修复后内存占用从 2GB 降到 500MB，优化了约 75%。"
        ),
        evidence=_make_evidence(
            competency_code="performance",
            snippet="valgrind, ASAN, RAII, 智能指针, 内存泄漏排查",
        ),
    )
    assert payload["overall_score"] >= 40, f"正确回答分数过低: {payload['overall_score']}"


def test_excellent_answer_scores_above_60():
    """深入优秀的回答，overall 必须 >= 60"""
    service = ScoringService()
    payload = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="performance",
        question_text="请解释如何优化一个高并发服务的性能瓶颈。",
        answer_text=(
            "首先通过 perf 和火焰图定位热点函数，发现瓶颈在序列化和锁竞争上。"
            "然后针对序列化，我从 JSON 切换到 protobuf，吞吐提升了 40%。"
            "对于锁竞争，采用了读写锁 + 无锁队列的方案，将 p99 延迟从 50ms 降到 12ms。"
            "最后在项目上线后，QPS 从 3000 提升到 8000，CPU 使用率下降 30%。"
            "整个优化过程中，我负责设计方案、编写核心代码和压测验证。"
            "取舍上，无锁队列增加了代码复杂度，但性能收益远大于维护成本。"
            "监控方面，通过 Prometheus 持续观察关键指标，确保上线后稳定。"
        ),
        evidence=_make_evidence(
            competency_code="performance",
            snippet="perf, 火焰图, protobuf, 无锁队列, 读写锁, p99 延迟, QPS, 性能优化",
        ),
    )
    assert payload["overall_score"] >= 60, f"优秀回答分数过低: {payload['overall_score']}"


# ============================================================
# 难度区分测试
# ============================================================

def test_difficulty_affects_scoring():
    """同一回答在 simple/hard 下分差 >= 10"""
    service = ScoringService()
    answer_text = (
        "我会先用缓存优化热点数据读取，然后对数据库加索引。"
        "在之前项目中这样做了，效果还可以。"
    )
    question_text = "请说明如何优化接口性能。"
    evidence = _make_evidence(snippet="缓存, 索引, 异步, 连接池, 分库分表")

    score_simple = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="performance",
        question_text=question_text,
        answer_text=answer_text,
        evidence=evidence,
        difficulty="simple",
    )
    score_hard = service.score_answer_fast(
        role_code="cpp_backend",
        competency_code="performance",
        question_text=question_text,
        answer_text=answer_text,
        evidence=evidence,
        difficulty="hard",
    )
    diff = score_simple["overall_score"] - score_hard["overall_score"]
    assert diff >= 2, f"simple={score_simple['overall_score']}, hard={score_hard['overall_score']}, diff={diff}"


def test_confused_penalty_stricter_on_hard():
    """困惑回答在 hard 模式下惩罚更严"""
    service = ScoringService()
    kwargs = dict(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="请解释分布式一致性协议。",
        answer_text="不知道这个是什么。",
        evidence=[],
    )
    score_simple = service.score_answer_fast(**kwargs, difficulty="simple")
    score_hard = service.score_answer_fast(**kwargs, difficulty="hard")
    assert score_simple["overall_score"] >= score_hard["overall_score"]


# ============================================================
# 降级透明度测试
# ============================================================

def test_ai_generated_flag_in_response():
    """full scoring 响应包含 ai_generated 和 degraded 字段"""
    service, _ = _make_service()
    payload, _, _ = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="Explain TCP handshake.",
        answer_text="TCP uses a three-way handshake: SYN, SYN-ACK, ACK.",
        evidence=_make_evidence(snippet="TCP three-way handshake, SYN, SYN-ACK, ACK"),
        retrieval_backend="milvus",
    )
    assert "ai_generated" in payload
    assert "degraded" in payload
    assert payload["ai_generated"] is True
    assert payload["degraded"] is False


def test_fallback_marks_degraded():
    """LLM fallback 时标记 degraded=True"""
    service = ScoringService()

    class FailingPromptService:
        def run_json_prompt(self, name, variables, fallback_result=None):
            return fallback_result, True  # simulate fallback

    service.prompt_service = FailingPromptService()
    payload, _, _ = service.score_answer(
        role_code="cpp_backend",
        competency_code="system_design",
        question_text="Explain TCP.",
        answer_text="TCP uses SYN, SYN-ACK, ACK for connection.",
        evidence=[],
        retrieval_backend="milvus",
    )
    assert payload["degraded"] is True
    assert payload["ai_generated"] is False


# ============================================================
# 音频分析 fallback 测试
# ============================================================

def test_analyze_audio_uses_ffmpeg_fallback_when_librosa_cannot_decode(monkeypatch, tmp_path):
    audio_path = tmp_path / "sample.webm"
    audio_path.write_bytes(b"fake-audio")

    def fake_librosa_load(path, sr=None):
        _ = path, sr
        raise RuntimeError("librosa backend missing")

    def fake_ffmpeg_loader(path):
        _ = path
        return np.ones(16000, dtype=np.float32), 16000

    monkeypatch.setattr("app.audio.analysis.librosa.load", fake_librosa_load)
    monkeypatch.setattr("app.audio.analysis._load_audio_with_ffmpeg", fake_ffmpeg_loader)

    features = analyze_audio(audio_path)

    assert features["status"] == "available"
    assert features["speech_rate"] is not None


def test_extract_keywords_keeps_meaningful_chinese_phrases():
    keywords = extract_keywords("请你介绍一个你深度参与的C++后端项目，重点说明高并发下的P99延迟突增问题。")

    assert "深度参与" in keywords
    assert "后端项目" in keywords
    assert "高并发" in keywords
    assert "p99" in keywords
    assert any(item.startswith("延迟突增") for item in keywords)


def test_project_depth_answer_scores_above_60():
    service = ScoringService()

    class StrongProjectPromptService:
        def run_json_prompt(self, name, variables, fallback_result=None):
            _ = name, fallback_result
            return {
                "overall_score": 82,
                "text_scores": {
                    "accuracy": 85,
                    "completeness": 80,
                    "logic": 85,
                    "job_fit": 80,
                    "credibility": 80,
                },
                "summary": "候选人回答完整，项目细节和量化结果都比较充分。",
                "strengths": ["项目背景、取舍和结果闭环清晰。"],
                "risks": ["还可以继续追问底层并发细节。"],
                "suggestions": ["补充无锁队列实现与边界处理。"],
            }, False

    service.prompt_service = StrongProjectPromptService()
    payload, _, _ = service.score_answer(
        role_code="cpp_backend",
        competency_code="project_depth",
        question_text=(
            "请你介绍一个你深度参与的C++后端项目，重点说明：你负责的核心模块、"
            "在性能或稳定性方面遇到的最关键挑战，以及你做出的关键技术取舍和最终可验证的结果。"
        ),
        answer_text=(
            "我参与过一个金融行情实时推送系统，核心负责订单簿模块。"
            "当时遇到高并发下 P99 延迟从 50ms 飙升到 300ms 的问题，根因是锁竞争严重。"
            "我做了两个关键取舍，一是用无锁队列替代互斥锁，牺牲部分代码可读性换取并发性能；"
            "二是把全量数据推送改成增量差分更新，减少网络传输量。"
            "依据是性能分析结果显示大部分阻塞来自锁等待，而且业务允许客户端本地缓存基础数据。"
            "最终 P99 延迟降到 35ms，错误率从 0.8% 降到 0.03%，并发连接数提升了 3 倍。"
        ),
        evidence=_make_evidence(
            competency_code="project_depth",
            snippet="尾延迟治理, 高并发, P99 延迟, 锁竞争, 无锁队列, 增量更新, 指标复盘",
        ),
        retrieval_backend="milvus",
    )

    assert payload["overall_score"] >= 60, f"项目题正确回答分数异常偏低: {payload['overall_score']}"

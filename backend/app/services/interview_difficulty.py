from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyProfile:
    code: str
    label: str
    audience_hint: str
    opening_focus: str
    main_focus: str
    follow_up_focus: str
    prompt_hint: str
    voice_style_name: str
    followup_intensity: str
    tolerance_for_generic: str
    guide_on_stuck: bool
    opening_suffix: str
    main_suffix: str
    redirect_suffix: str
    credibility_suffix: str


DIFFICULTY_PROFILES: dict[str, DifficultyProfile] = {
    "simple": DifficultyProfile(
        code="simple",
        label="简单",
        audience_hint="适合校招、转岗初期、基础摸底人群",
        opening_focus="从职责明确、容易展开的项目经历切入，优先确认基础概念和实际参与内容。",
        main_focus="优先考察基础概念、常见实现方式和项目里的直接实践，减少抽象架构压力。",
        follow_up_focus="一次只追一个点，优先帮候选人把回答范围缩小到可落地的经历。",
        prompt_hint="题目要更友好，先问基础、场景明确的问题，避免一上来要求复杂架构推演或高压质疑。",
        voice_style_name="简单难度",
        followup_intensity="low",
        tolerance_for_generic="high",
        guide_on_stuck=True,
        opening_suffix="请从你最熟悉、最容易讲清楚的一段经历开始。",
        main_suffix="先从基础做法和你亲手做过的部分讲起。",
        redirect_suffix="把范围缩小一点，只回答最核心的一步做法。",
        credibility_suffix="先别展开太多，补一条你亲自做过的具体细节就可以。",
    ),
    "medium": DifficultyProfile(
        code="medium",
        label="中等",
        audience_hint="适合社招主流岗位、常规筛选、日常晋升准备",
        opening_focus="围绕代表项目、关键职责和实际结果展开，兼顾基础与进阶能力。",
        main_focus="平衡考察方案设计、技术取舍、结果验证和岗位匹配度。",
        follow_up_focus="允许围绕关键缺口继续深挖，但保持节奏稳定。",
        prompt_hint="题目保持真实面试的常规强度，问题简短，少加说明。",
        voice_style_name="中等难度",
        followup_intensity="medium",
        tolerance_for_generic="medium",
        guide_on_stuck=False,
        opening_suffix="",
        main_suffix="",
        redirect_suffix="请直接回到题目核心，给出完整结论。",
        credibility_suffix="请补充更可验证的个人贡献和结果证据。",
    ),
    "hard": DifficultyProfile(
        code="hard",
        label="困难",
        audience_hint="适合高薪岗位、大厂面试、资深候选人和高要求场景",
        opening_focus="尽快进入复杂项目、关键 trade-off、性能瓶颈和架构决策。",
        main_focus="优先考察复杂场景下的架构能力、边界意识、量化结果和反思能力。",
        follow_up_focus="更强调方案取舍、失败复盘、指标验证和高压场景下的判断。",
        prompt_hint="题目要更有挑战，优先问复杂度、边界条件、性能瓶颈、故障处理、架构取舍和量化结果。",
        voice_style_name="困难难度",
        followup_intensity="high",
        tolerance_for_generic="low",
        guide_on_stuck=False,
        opening_suffix="优先讲复杂度最高、最能体现判断力的那一段。",
        main_suffix="需要覆盖复杂场景、边界条件、取舍依据和量化结果。",
        redirect_suffix="请不要停留在泛泛描述，直接回答最关键的技术判断。",
        credibility_suffix="请给出可验证的数据、容量、收益或失败复盘细节。",
    ),
}


DEFAULT_DIFFICULTY = "medium"


def normalize_difficulty(value: str | None) -> str:
    if value in DIFFICULTY_PROFILES:
        return value
    legacy_mapping = {
        "regular": "medium",
        "pressure": "hard",
        "normal": "medium",
        "stress": "hard",
        "guided": "simple",
    }
    normalized = legacy_mapping.get((value or "").strip().lower())
    return normalized or DEFAULT_DIFFICULTY


def get_difficulty_profile(value: str | None) -> DifficultyProfile:
    return DIFFICULTY_PROFILES[normalize_difficulty(value)]

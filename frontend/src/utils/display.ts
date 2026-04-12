const POSITION_LABELS: Record<string, string> = {
  cpp_backend: "C++后端开发",
  web_frontend: "Web前端开发",
  "CPP Backend": "C++后端开发",
  "C++ Backend": "C++后端开发",
  "C++后端开发": "C++后端开发",
  "Web Frontend": "Web前端开发",
  "Frontend": "Web前端开发",
  "Front End": "Web前端开发",
  "Web前端开发": "Web前端开发",
};

const COMPETENCY_LABELS: Record<string, string> = {
  project_depth: "项目深度",
  frontend_foundation: "前端基础",
  vue_engineering: "Vue 工程化",
  browser_principle: "浏览器原理",
  network_performance: "网络与性能",
  architecture: "架构设计",
  cpp_language: "C++ 语言",
  os_network: "操作系统与网络",
  algorithm: "算法与数据结构",
  system_design: "系统设计",
  performance: "性能优化",
};

const STYLE_LABELS: Record<string, string> = {
  simple: "简单",
  medium: "中等",
  hard: "困难",
};

const ANSWER_MODE_LABELS: Record<string, string> = {
  text: "文本回答",
  audio: "语音回答",
};

const INTERVIEW_STATUS_LABELS: Record<string, string> = {
  opening: "开场题",
  resume_clarification: "简历澄清",
  technical_question: "主问题",
  deep_follow_up: "追问中",
  candidate_question: "候选人提问",
  summary: "总结题",
  completed: "已完成",
};

const REPORT_LEVEL_LABELS: Record<string, string> = {
  Excellent: "表现优秀",
  Strong: "表现良好",
  Passing: "达到预期",
  "Needs Improvement": "需要加强",
  excellent: "表现优秀",
  good: "表现良好",
  medium: "达到预期",
  weak: "需要加强",
  优秀: "表现优秀",
  良好: "表现良好",
  中等: "达到预期",
  较弱: "需要加强",
  分析中: "分析中",
  Retrying: "重试中",
  Failed: "分析失败",
};

const SCORE_LABELS: Record<string, string> = {
  accuracy: "准确性",
  completeness: "完整度",
  logic: "逻辑性",
  job_fit: "岗位匹配度",
  credibility: "可信度",
  confidence: "语音自信度",
  clarity: "语音清晰度",
  fluency: "语音流畅度",
  emotion: "情绪稳定度",
  stability: "稳定性",
  speech_rate_comment: "语速评价",
  pause_comment: "停顿评价",
  status: "状态",
  speech_confidence: "语音自信度",
  speech_clarity: "语音清晰度",
  speech_fluency: "语音流畅度",
  speech_emotion: "情绪稳定度",
};

const VALUE_LABELS: Record<string, string> = {
  available: "可分析",
  unavailable: "未提供语音",
  pending: "分析中",
  processing: "分析中",
  success: "已完成",
  failed: "分析失败",
  dead: "分析终止",
  Retrying: "重试中",
  Failed: "分析失败",
  "Current competency has enough coverage, switch to the next competency.": "当前能力点覆盖已经足够，切换到下一个能力点。",
  "Candidate sounds confused, ask one narrower clarifying follow-up first.": "候选人明显有些困惑，先缩小范围补一个澄清追问。",
  "Overall score is low, so switch competency instead of stacking more follow-ups.": "当前这题得分较低，继续叠加追问收益有限，切换到下一个能力点。",
  "Overall score is already strong, so move to the next competency.": "当前回答已经比较稳，可以进入下一个能力点。",
  "Answer is still low signal after a follow-up, so switch competency.": "已经追问过一次，但回答仍然信息量不足，切换到下一个能力点。",
  "Answer drifted off the core topic, so redirect it back.": "回答偏离了题目核心，需要先拉回主线。",
  "Need more concrete evidence or verifiable detail.": "还需要更具体、可验证的细节支撑。",
  "Answer is already complete enough, so move forward.": "当前回答已经比较完整，可以继续往下推进。",
  "There are still missing points worth deepening.": "当前回答还有几个关键点没有展开，值得继续追问。",
  "This follow-up type already appeared in the round, so switch competency.": "这一轮已经出现过同类追问，切换到下一个能力点避免重复。",
  "This round already has enough follow-ups, so switch competency.": "这一轮追问已经足够，切换到下一个能力点。",
};

const ENGLISH_SUMMARY_PATTERNS = [
  /^This interview covered/i,
  /^AI is still analyzing this interview/i,
  /^AI analysis hit a temporary issue/i,
  /^AI analysis failed multiple times/i,
];

export function positionLabel(value?: string | null, code?: string | null) {
  if (code && POSITION_LABELS[code]) {
    return POSITION_LABELS[code];
  }
  if (!value) return "--";
  return POSITION_LABELS[value] || value;
}

export function competencyLabel(value?: string | null) {
  if (!value) return "综合能力";
  return COMPETENCY_LABELS[value] || value;
}

export function styleLabel(value?: string | null) {
  if (!value) return "--";
  return STYLE_LABELS[value] || value;
}

export function answerModeLabel(value?: string | null) {
  if (!value) return "--";
  return ANSWER_MODE_LABELS[value] || value;
}

export function interviewStatusLabel(value?: string | null) {
  if (!value) return "--";
  return INTERVIEW_STATUS_LABELS[value] || value;
}

export function reportLevelLabel(value?: string | null) {
  if (!value) return "--";
  return REPORT_LEVEL_LABELS[value] || value;
}

export function scoreLabel(value?: string | null) {
  if (!value) return "--";
  return SCORE_LABELS[value] || value;
}

export function translatedValue(value?: string | null) {
  if (!value) return "--";
  return VALUE_LABELS[value] || value;
}

export function isFallbackEnglishSummary(value?: string | null) {
  if (!value) return false;
  return ENGLISH_SUMMARY_PATTERNS.some((pattern) => pattern.test(value));
}

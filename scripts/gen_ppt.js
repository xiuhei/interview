const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const DIAG = path.join(__dirname, "diagrams");
const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "AI Mock Interview Team";
pres.title = "AI模拟面试与能力提升系统 - 初赛答辩";

// ===== Color Palette: Ocean Gradient (tech feel) =====
const C = {
  navy:     "1E2761",
  primary:  "2B579A",
  blue:     "4472C4",
  lightBlue:"D6E4F0",
  accent:   "ED7D31",
  green:    "70AD47",
  purple:   "7030A0",
  red:      "C00000",
  dark:     "1F1F1F",
  gray:     "666666",
  lightGray:"F2F2F2",
  white:    "FFFFFF",
  ice:      "CADCFC",
};
const FONT = "Microsoft YaHei";

// Helper: fresh shadow
const mkShadow = () => ({ type: "outer", blur: 6, offset: 2, angle: 135, color: "000000", opacity: 0.12 });

// Helper: add image preserving aspect ratio
function addImg(slide, filename, x, y, maxW, maxH) {
  const fpath = path.join(DIAG, filename);
  slide.addImage({ path: fpath, x, y, w: maxW, h: maxH, sizing: { type: "contain", w: maxW, h: maxH } });
}

// ============================================================
// SLIDE 1: Cover
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.navy };
  // Top accent bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });
  // Main title
  s.addText("AI模拟面试与能力提升系统", {
    x: 0.8, y: 1.2, w: 8.4, h: 1.2, fontSize: 36, fontFace: FONT,
    color: C.white, bold: true, align: "left", margin: 0
  });
  // Subtitle
  s.addText("基于 LLM + RAG + 多模态的智能面试训练平台", {
    x: 0.8, y: 2.4, w: 8.4, h: 0.6, fontSize: 20, fontFace: FONT,
    color: C.ice, align: "left", margin: 0
  });
  // Divider
  s.addShape(pres.shapes.RECTANGLE, { x: 0.8, y: 3.2, w: 2.5, h: 0.04, fill: { color: C.accent } });
  // Tech tags
  s.addText("FastAPI  ·  Vue 3  ·  MySQL  ·  Milvus  ·  Qwen LLM  ·  WebSocket  ·  Docker", {
    x: 0.8, y: 3.5, w: 8.4, h: 0.5, fontSize: 14, fontFace: FONT,
    color: C.gray, align: "left", margin: 0
  });
  // Bottom bar
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 5.0, w: 10, h: 0.625, fill: { color: C.primary } });
  s.addText("初赛答辩", {
    x: 0.8, y: 5.05, w: 8.4, h: 0.55, fontSize: 16, fontFace: FONT,
    color: C.white, align: "left", valign: "middle", margin: 0
  });
}

// ============================================================
// SLIDE 2: Background & Pain Points
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("项目背景与痛点", {
    x: 0.6, y: 0.3, w: 8.8, h: 0.7, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.95, w: 1.5, h: 0.04, fill: { color: C.accent } });

  // Pain point cards
  const cards = [
    { icon: "01", title: "训练效率低", desc: "需协调面试官时间\n难以随时练习\n反复训练成本极高", color: C.primary },
    { icon: "02", title: "评价主观性强", desc: "不同面试官标准不一\n无法形成量化评估\n用户难以客观了解水平", color: C.accent },
    { icon: "03", title: "反馈单一", desc: "仅提供简单评语\n缺乏多维度分析\n无法追踪成长轨迹", color: C.red },
  ];

  cards.forEach((c, i) => {
    const cx = 0.6 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: 1.4, w: 2.8, h: 2.4, fill: { color: C.white },
      line: { color: "DDDDDD", width: 1 }, shadow: mkShadow()
    });
    // Accent top bar
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.4, w: 2.8, h: 0.06, fill: { color: c.color } });
    // Number
    s.addText(c.icon, {
      x: cx + 0.2, y: 1.6, w: 0.6, h: 0.5, fontSize: 24, fontFace: FONT,
      color: c.color, bold: true, margin: 0
    });
    // Title
    s.addText(c.title, {
      x: cx + 0.2, y: 2.1, w: 2.4, h: 0.4, fontSize: 18, fontFace: FONT,
      color: C.dark, bold: true, margin: 0
    });
    // Desc
    s.addText(c.desc, {
      x: cx + 0.2, y: 2.5, w: 2.4, h: 1.2, fontSize: 13, fontFace: FONT,
      color: C.gray, margin: 0
    });
  });

  // Solution arrow
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 4.2, w: 8.8, h: 1.1, fill: { color: C.navy }, shadow: mkShadow() });
  s.addText([
    { text: "解决方案 → ", options: { bold: true, color: C.accent, fontSize: 18 } },
    { text: "构建基于 LLM 大语言模型的 AI 模拟面试系统，结合 RAG 检索增强、多模态输入、实时语音对话，提供智能化面试训练与能力评估", options: { color: C.white, fontSize: 15 } }
  ], { x: 1.0, y: 4.3, w: 8.0, h: 0.9, fontFace: FONT, valign: "middle", margin: 0 });
}

// ============================================================
// SLIDE 3: System Goals
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("系统目标", {
    x: 0.6, y: 0.3, w: 8.8, h: 0.7, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.95, w: 1.5, h: 0.04, fill: { color: C.accent } });

  const goals = [
    { n: "01", t: "AI 模拟面试平台", d: "支持文本与实时语音两种面试模式" },
    { n: "02", t: "智能提问与追问", d: "基于岗位能力维度与简历信息，支持多轮追问" },
    { n: "03", t: "多维度评价", d: "RAG 检索增强 + LLM 评分：正确性、深度、逻辑、匹配度、完整度" },
    { n: "04", t: "面试报告生成", d: "自动生成能力雷达图、逐题分析与改进建议" },
    { n: "05", t: "个人成长追踪", d: "展示多次面试能力变化趋势，识别薄弱项" },
  ];

  goals.forEach((g, i) => {
    const gy = 1.3 + i * 0.82;
    // Number circle
    s.addShape(pres.shapes.OVAL, { x: 0.8, y: gy + 0.05, w: 0.5, h: 0.5, fill: { color: C.primary } });
    s.addText(g.n, { x: 0.8, y: gy + 0.05, w: 0.5, h: 0.5, fontSize: 14, fontFace: FONT, color: C.white, bold: true, align: "center", valign: "middle", margin: 0 });
    // Title
    s.addText(g.t, { x: 1.5, y: gy, w: 3, h: 0.35, fontSize: 17, fontFace: FONT, color: C.dark, bold: true, margin: 0 });
    // Description
    s.addText(g.d, { x: 1.5, y: gy + 0.35, w: 7.5, h: 0.35, fontSize: 13, fontFace: FONT, color: C.gray, margin: 0 });
  });
}

// ============================================================
// SLIDE 4: System Architecture
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("系统总体架构", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });
  // Architecture image - centered
  addImg(s, "architecture.png", 0.4, 0.9, 9.2, 4.5);
}

// ============================================================
// SLIDE 5: Tech Stack
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("技术栈一览", {
    x: 0.6, y: 0.3, w: 8.8, h: 0.7, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.95, w: 1.5, h: 0.04, fill: { color: C.accent } });

  const hdr = { fill: { color: C.primary }, color: C.white, bold: true, fontSize: 13, fontFace: FONT, align: "center", valign: "middle" };
  const cellL = { fontSize: 12, fontFace: FONT, color: C.dark, valign: "middle" };
  const cellC = { fontSize: 12, fontFace: FONT, color: C.dark, valign: "middle", align: "center" };
  const cellB = { fontSize: 12, fontFace: FONT, color: C.dark, valign: "middle", bold: true };

  const rows = [
    [{ text: "层次", options: hdr }, { text: "技术选型", options: hdr }, { text: "说明", options: hdr }],
    [{ text: "前端", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "Vue 3 + TypeScript + Vite", options: cellB }, { text: "Element Plus UI、Pinia 状态管理、ECharts 图表", options: cellL }],
    [{ text: "后端", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "FastAPI (Python 3.12)", options: cellB }, { text: "SQLAlchemy 2.0 ORM、Alembic 迁移、uvicorn", options: cellL }],
    [{ text: "数据库", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "MySQL 8.4", options: cellB }, { text: "业务数据持久化，pymysql 驱动", options: cellL }],
    [{ text: "缓存", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "Redis 7.4", options: cellB }, { text: "会话缓存、热点数据缓存", options: cellL }],
    [{ text: "向量数据库", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "Milvus 2.5.4", options: cellB }, { text: "RAG 知识库向量检索，余弦相似度搜索", options: cellL }],
    [{ text: "LLM 服务", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "通义千问 Qwen", options: cellB }, { text: "OpenAI 兼容 API，JSON 结构化输出", options: cellL }],
    [{ text: "嵌入向量", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "text-embedding-v3", options: cellB }, { text: "128 维向量，批量嵌入（每批 10 条）", options: cellL }],
    [{ text: "语音服务", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "ASR + TTS (MIMO)", options: cellB }, { text: "语音识别、语音合成、webrtcvad 活动检测", options: cellL }],
    [{ text: "部署", options: { ...cellC, fill: { color: C.lightGray } } }, { text: "Docker Compose + Nginx", options: cellB }, { text: "全栈容器化，8 个服务容器一键部署", options: cellL }],
  ];

  s.addTable(rows, {
    x: 0.5, y: 1.2, w: 9.0, colW: [1.3, 2.8, 4.9],
    border: { pt: 0.5, color: "CCCCCC" },
    rowH: [0.38, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38, 0.38],
    margin: [3, 6, 3, 6],
  });
}

// ============================================================
// SLIDE 6: Module Overview
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("功能模块全景", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });

  addImg(s, "modules_overview.png", 0.3, 0.9, 9.4, 3.2);

  // Bottom note
  s.addText("★ 核心模块：模拟面试引擎、RAG 检索增强、多维评分引擎   |   辅助模块：认证、简历、岗位、报告、成长、语音", {
    x: 0.6, y: 4.4, w: 8.8, h: 0.5, fontSize: 12, fontFace: FONT, color: C.gray, margin: 0
  });
}

// ============================================================
// SLIDE 7: Core Module 1 - Interview Engine
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("核心模块① 面试流程引擎", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });

  addImg(s, "state_machine.png", 0.2, 0.85, 9.6, 3.3);

  // Bottom key points
  const points = [
    { t: "6 阶段状态机", d: "开场→简历追问→技术\n提问→深入追问→候选\n人提问→总结", c: C.primary },
    { t: "4 种追问策略", d: "深化 / 转向 / 可信度\n验证 / 切换维度", c: C.accent },
    { t: "3 种面试风格", d: "常规 / 压力 / 引导\n模拟不同场景", c: C.green },
  ];
  points.forEach((pt, i) => {
    const px = 0.6 + i * 3.1;
    s.addShape(pres.shapes.RECTANGLE, {
      x: px, y: 4.2, w: 2.8, h: 1.2, fill: { color: pt.c, transparency: 90 },
      line: { color: pt.c, width: 1 }
    });
    s.addText(pt.t, { x: px + 0.15, y: 4.25, w: 2.5, h: 0.35, fontSize: 14, fontFace: FONT, color: pt.c, bold: true, margin: 0 });
    s.addText(pt.d, { x: px + 0.15, y: 4.6, w: 2.5, h: 0.75, fontSize: 11, fontFace: FONT, color: C.dark, margin: 0 });
  });
}

// ============================================================
// SLIDE 8: Core Module 2 - RAG
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("核心模块② RAG 检索增强评分", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });

  addImg(s, "rag_pipeline.png", 0.2, 0.85, 9.6, 3.6);

  // Bottom highlight
  s.addShape(pres.shapes.RECTANGLE, { x: 0.5, y: 4.65, w: 9.0, h: 0.75, fill: { color: C.navy }, shadow: mkShadow() });
  s.addText([
    { text: "核心价值：", options: { bold: true, color: C.accent, fontSize: 14 } },
    { text: "传统方案仅依赖 LLM 直接评分，存在幻觉风险。RAG 方案通过检索专业知识库中的权威内容作为评分依据，使评分结果有据可依，显著提升专业性和客观性。", options: { color: C.white, fontSize: 13 } }
  ], { x: 0.8, y: 4.7, w: 8.4, h: 0.65, fontFace: FONT, valign: "middle", margin: 0 });
}

// ============================================================
// SLIDE 9: Core Module 3 - Scoring
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("核心模块③ 多维度评分体系", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });

  addImg(s, "scoring_system.png", 0.2, 0.85, 9.6, 3.5);

  // Bottom summary
  s.addText([
    { text: "文本语义 5 维度", options: { bold: true, color: C.primary, fontSize: 12 } },
    { text: "：正确性 · 深度 · 逻辑 · 匹配度 · 完整度    ", options: { color: C.dark, fontSize: 12 } },
    { text: "语音声学 5 指标", options: { bold: true, color: C.green, fontSize: 12 } },
    { text: "：音量 · 停顿 · 语速 · 音调 · 有声比例    ", options: { color: C.dark, fontSize: 12 } },
    { text: "RAG 证据融合", options: { bold: true, color: C.accent, fontSize: 12 } },
    { text: "：知识库匹配 · 对比验证 · 置信度", options: { color: C.dark, fontSize: 12 } },
  ], { x: 0.5, y: 4.55, w: 9.0, h: 0.6, fontFace: FONT, margin: 0 });
}

// ============================================================
// SLIDE 10: Deployment
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("系统部署方案", {
    x: 0.6, y: 0.15, w: 8.8, h: 0.6, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.7, w: 1.5, h: 0.04, fill: { color: C.accent } });

  addImg(s, "deployment.png", 0.2, 0.85, 9.6, 3.3);

  // Bottom highlight
  s.addText("Docker Compose 全栈容器化  |  8 个服务容器  |  Nginx 统一入口  |  Volume 数据持久化  |  一键部署", {
    x: 0.5, y: 4.4, w: 9.0, h: 0.5, fontSize: 13, fontFace: FONT, color: C.gray, align: "center", margin: 0
  });
}

// ============================================================
// SLIDE 11: Innovation
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.white };
  s.addText("创新亮点", {
    x: 0.6, y: 0.3, w: 8.8, h: 0.7, fontSize: 28, fontFace: FONT, color: C.navy, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.95, w: 1.5, h: 0.04, fill: { color: C.accent } });

  const innovations = [
    { n: "01", t: "多模态面试评价", d: "融合文本语义分析（5维度）与\n语音声学特征（5指标），突破\n单一文本评分局限性", c: C.primary },
    { n: "02", t: "RAG 检索增强评分", d: "基于 Milvus 向量数据库的专业\n知识检索，解决 LLM 评分幻觉\n问题，使评分有据可依", c: C.accent },
    { n: "03", t: "智能追问策略", d: "四种动态追问方向（深化/转向\n/可信度验证/切换维度），模拟\n真实面试官行为", c: C.green },
    { n: "04", t: "实时语音面试", d: "WebSocket 全双工语音对话，\n集成 ASR + TTS + VAD，\n提供沉浸式面试体验", c: C.purple },
    { n: "05", t: "全栈容器化部署", d: "Docker Compose 统一管理\n8 个服务容器，支持一键部署\n与环境一致性", c: C.red },
  ];

  // Row 1: 3 cards
  innovations.slice(0, 3).forEach((inn, i) => {
    const cx = 0.5 + i * 3.15;
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: 1.3, w: 2.9, h: 1.9, fill: { color: C.white },
      line: { color: "DDDDDD", width: 1 }, shadow: mkShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 1.3, w: 2.9, h: 0.06, fill: { color: inn.c } });
    s.addShape(pres.shapes.OVAL, { x: cx + 0.2, y: 1.5, w: 0.45, h: 0.45, fill: { color: inn.c } });
    s.addText(inn.n, { x: cx + 0.2, y: 1.5, w: 0.45, h: 0.45, fontSize: 13, fontFace: FONT, color: C.white, bold: true, align: "center", valign: "middle", margin: 0 });
    s.addText(inn.t, { x: cx + 0.8, y: 1.5, w: 1.9, h: 0.45, fontSize: 15, fontFace: FONT, color: C.dark, bold: true, valign: "middle", margin: 0 });
    s.addText(inn.d, { x: cx + 0.2, y: 2.1, w: 2.5, h: 1.0, fontSize: 11, fontFace: FONT, color: C.gray, margin: 0 });
  });

  // Row 2: 2 cards centered
  innovations.slice(3).forEach((inn, i) => {
    const cx = 2.05 + i * 3.15;
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: 3.5, w: 2.9, h: 1.9, fill: { color: C.white },
      line: { color: "DDDDDD", width: 1 }, shadow: mkShadow()
    });
    s.addShape(pres.shapes.RECTANGLE, { x: cx, y: 3.5, w: 2.9, h: 0.06, fill: { color: inn.c } });
    s.addShape(pres.shapes.OVAL, { x: cx + 0.2, y: 3.7, w: 0.45, h: 0.45, fill: { color: inn.c } });
    s.addText(inn.n, { x: cx + 0.2, y: 3.7, w: 0.45, h: 0.45, fontSize: 13, fontFace: FONT, color: C.white, bold: true, align: "center", valign: "middle", margin: 0 });
    s.addText(inn.t, { x: cx + 0.8, y: 3.7, w: 1.9, h: 0.45, fontSize: 15, fontFace: FONT, color: C.dark, bold: true, valign: "middle", margin: 0 });
    s.addText(inn.d, { x: cx + 0.2, y: 4.3, w: 2.5, h: 1.0, fontSize: 11, fontFace: FONT, color: C.gray, margin: 0 });
  });
}

// ============================================================
// SLIDE 12: Summary & Outlook
// ============================================================
{
  const s = pres.addSlide();
  s.background = { color: C.navy };
  s.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 10, h: 0.06, fill: { color: C.accent } });

  s.addText("总结与展望", {
    x: 0.6, y: 0.3, w: 8.8, h: 0.7, fontSize: 28, fontFace: FONT, color: C.white, bold: true, margin: 0
  });
  s.addShape(pres.shapes.RECTANGLE, { x: 0.6, y: 0.95, w: 1.5, h: 0.04, fill: { color: C.accent } });

  // Left: Achievements
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: 1.3, w: 4.3, h: 3.3, fill: { color: C.primary },
    shadow: mkShadow()
  });
  s.addText("已完成成果", {
    x: 0.7, y: 1.4, w: 3.9, h: 0.45, fontSize: 18, fontFace: FONT, color: C.accent, bold: true, margin: 0
  });
  s.addText([
    { text: "全栈系统开发（FastAPI + Vue 3）", options: { bullet: true, breakLine: true, fontSize: 13, color: C.white } },
    { text: "面试状态机与智能追问引擎", options: { bullet: true, breakLine: true, fontSize: 13, color: C.white } },
    { text: "RAG 知识库构建与检索增强评分", options: { bullet: true, breakLine: true, fontSize: 13, color: C.white } },
    { text: "多维评分体系（文本+语音+RAG融合）", options: { bullet: true, breakLine: true, fontSize: 13, color: C.white } },
    { text: "WebSocket 实时语音面试", options: { bullet: true, breakLine: true, fontSize: 13, color: C.white } },
    { text: "Docker Compose 全栈容器化部署", options: { bullet: true, fontSize: 13, color: C.white } },
  ], { x: 0.8, y: 1.95, w: 3.8, h: 2.5, fontFace: FONT, margin: 0, paraSpaceAfter: 6 });

  // Right: Future
  s.addShape(pres.shapes.RECTANGLE, {
    x: 5.2, y: 1.3, w: 4.3, h: 3.3, fill: { color: "2A2A5E" },
    shadow: mkShadow()
  });
  s.addText("后续计划", {
    x: 5.4, y: 1.4, w: 3.9, h: 0.45, fontSize: 18, fontFace: FONT, color: C.accent, bold: true, margin: 0
  });
  s.addText([
    { text: "更多岗位模板覆盖与行业扩展", options: { bullet: true, breakLine: true, fontSize: 13, color: C.ice } },
    { text: "评分模型持续优化与精度提升", options: { bullet: true, breakLine: true, fontSize: 13, color: C.ice } },
    { text: "移动端响应式适配", options: { bullet: true, breakLine: true, fontSize: 13, color: C.ice } },
    { text: "面试数据深度分析与洞察", options: { bullet: true, breakLine: true, fontSize: 13, color: C.ice } },
    { text: "AI 面试教练个性化推荐", options: { bullet: true, fontSize: 13, color: C.ice } },
  ], { x: 5.5, y: 1.95, w: 3.8, h: 2.5, fontFace: FONT, margin: 0, paraSpaceAfter: 6 });

  // Bottom: Thank you
  s.addText("感谢聆听！", {
    x: 0.6, y: 4.85, w: 8.8, h: 0.6, fontSize: 24, fontFace: FONT, color: C.white, bold: true, align: "center", margin: 0
  });
}

// ===== Write File =====
const outPath = process.argv[2] || "output.pptx";
pres.writeFile({ fileName: outPath }).then(() => {
  console.log("Created: " + outPath);
}).catch(err => {
  console.error("Error:", err);
  process.exit(1);
});

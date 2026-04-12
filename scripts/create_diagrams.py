"""Create all diagram images for the competition documents."""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SCRIPT_DIR = Path(__file__).resolve().parent
OUT_DIR = SCRIPT_DIR / "diagrams"
OUT_DIR.mkdir(exist_ok=True)

FONT_PATH = Path("C:/Windows/Fonts/msyh.ttc")
FONT_BOLD_PATH = Path("C:/Windows/Fonts/msyhbd.ttc")

def font(size, bold=False):
    path = FONT_BOLD_PATH if bold and FONT_BOLD_PATH.exists() else FONT_PATH
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()

# Color palette
BG = "#FFFFFF"
PRIMARY = "#2B579A"
PRIMARY_LIGHT = "#4472C4"
ACCENT = "#ED7D31"
GREEN = "#70AD47"
GRAY = "#D9D9D9"
GRAY_DARK = "#595959"
LIGHT_BLUE = "#D6E4F0"
LIGHT_GREEN = "#E2EFDA"
LIGHT_ORANGE = "#FCE4D6"
LIGHT_PURPLE = "#E8D5F5"
WHITE = "#FFFFFF"
TEXT_DARK = "#1F1F1F"
TEXT_WHITE = "#FFFFFF"


def rounded_rect(draw, xy, fill, radius=12, outline=None, width=1):
    """Draw a rounded rectangle."""
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, x1, y1, x2, y2, color=GRAY_DARK, width=2, head_size=8):
    """Draw an arrow from (x1,y1) to (x2,y2)."""
    draw.line([(x1, y1), (x2, y2)], fill=color, width=width)
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    lx = x2 - head_size * math.cos(angle - math.pi / 6)
    ly = y2 - head_size * math.sin(angle - math.pi / 6)
    rx = x2 - head_size * math.cos(angle + math.pi / 6)
    ry = y2 - head_size * math.sin(angle + math.pi / 6)
    draw.polygon([(x2, y2), (lx, ly), (rx, ry)], fill=color)


def center_text(draw, x, y, w, h, text, f, fill=TEXT_DARK):
    """Draw text centered in a box."""
    bbox = draw.textbbox((0, 0), text, font=f)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x + (w - tw) / 2, y + (h - th) / 2), text, font=f, fill=fill)


def multi_center_text(draw, x, y, w, h, lines, f, fill=TEXT_DARK, line_spacing=4):
    """Draw multiple lines of text centered in a box."""
    total_h = 0
    dims = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=f)
        lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        dims.append((lw, lh))
        total_h += lh + line_spacing
    total_h -= line_spacing
    cur_y = y + (h - total_h) / 2
    for i, line in enumerate(lines):
        lw, lh = dims[i]
        draw.text((x + (w - lw) / 2, cur_y), line, font=f, fill=fill)
        cur_y += lh + line_spacing


# ============================================================
# 1. System Architecture Diagram
# ============================================================
def create_architecture_diagram():
    W, H = 1100, 720
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    layer_f = font(16, bold=True)
    item_f = font(14)
    small_f = font(12)

    # Title
    center_text(d, 0, 10, W, 40, "系统总体架构图", title_f, PRIMARY)

    # Layers
    layers = [
        ("用户层", "#4472C4", ["浏览器 (PC / Mobile)", "WebSocket 语音通道"]),
        ("前端展示层", "#5B9BD5", ["Vue 3 + TypeScript + Vite", "Element Plus UI  |  Pinia 状态管理  |  ECharts 图表  |  Axios HTTP"]),
        ("API 网关层", "#2E75B6", ["Nginx 反向代理  →  /api/* → FastAPI  |  其他 → Vue 静态服务"]),
        ("后端服务层", "#70AD47", [
            "FastAPI (Python 3.12)  |  uvicorn ASGI",
            "认证服务 (JWT)  |  面试服务  |  简历服务  |  评分服务  |  成长服务  |  报告服务",
            "面试编排器  |  问题种子服务  |  WebSocket 语音处理"
        ]),
        ("AI 能力层", "#ED7D31", [
            "LLM 服务 (通义千问 Qwen)  |  嵌入向量 (text-embedding-v3)  |  RAG 检索服务",
            "ASR 语音识别  |  TTS 语音合成 (Qwen)  |  VAD 语音活动检测  |  音频特征提取"
        ]),
        ("数据存储层", "#7030A0", [
            "MySQL 8 (业务数据)  |  Redis 7 (缓存)  |  Milvus 2.5 (向量检索)  |  文件系统 (简历/音频)"
        ]),
    ]

    y = 60
    for i, (name, color, items) in enumerate(layers):
        layer_h = 40 + len(items) * 24
        # Layer background
        rounded_rect(d, (30, y, W - 30, y + layer_h), fill=color + "18", radius=10, outline=color, width=2)
        # Layer label
        lbl_w = 110
        rounded_rect(d, (35, y + 5, 35 + lbl_w, y + 30), fill=color, radius=6)
        center_text(d, 35, y + 5, lbl_w, 25, name, layer_f, WHITE)
        # Items
        for j, item in enumerate(items):
            d.text((160, y + 8 + j * 24), item, font=item_f, fill=TEXT_DARK)

        # Arrow to next layer
        if i < len(layers) - 1:
            next_y = y + layer_h + 8
            draw_arrow(d, W // 2, y + layer_h, W // 2, next_y + 2, color=GRAY_DARK, width=2, head_size=6)
            y = next_y
        else:
            y += layer_h + 10

    # Footer note
    d.text((40, y + 5), "API 前缀: /api/v1  |  文档: /docs (Swagger)  |  数据库迁移: Alembic  |  部署: Docker Compose", font=small_f, fill=GRAY_DARK)

    img.save(os.path.join(OUT_DIR, "architecture.png"), quality=95)
    print("Created architecture.png")


# ============================================================
# 2. Interview State Machine Diagram
# ============================================================
def create_state_machine():
    W, H = 1100, 500
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    state_f = font(14, bold=True)
    desc_f = font(11)
    arrow_f = font(11)

    center_text(d, 0, 10, W, 40, "面试流程状态机", title_f, PRIMARY)

    states = [
        ("opening", "开场阶段", "生成开场白\n引导进入状态", PRIMARY_LIGHT),
        ("resume\nclarification", "简历追问", "基于简历解析\n追问项目经历", "#5B9BD5"),
        ("technical\nquestion", "技术提问", "按能力维度\n生成专业问题", GREEN),
        ("deep\nfollow_up", "深入追问", "动态追问策略\n深化/转向/验证", ACCENT),
        ("candidate\nquestion", "候选人提问", "允许反向提问\n模拟真实面试", "#7030A0"),
        ("summary →\ncompleted", "总结完成", "生成总结\n触发报告生成", "#C00000"),
    ]

    box_w, box_h = 140, 100
    gap = 30
    total_w = len(states) * box_w + (len(states) - 1) * gap
    start_x = (W - total_w) / 2
    y = 100

    for i, (code, name, desc, color) in enumerate(states):
        x = start_x + i * (box_w + gap)
        # State box
        rounded_rect(d, (x, y, x + box_w, y + box_h), fill=color + "20", radius=10, outline=color, width=2)
        # State name
        center_text(d, x, y + 5, box_w, 30, name, state_f, color)
        # Description
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=desc_f)
            tw = bbox[2] - bbox[0]
            d.text((x + (box_w - tw) / 2, y + 40 + j * 18), line, font=desc_f, fill=TEXT_DARK)
        # Code below box
        bbox = d.textbbox((0, 0), code, font=desc_f)
        lines_code = code.split("\n")
        for j, lc in enumerate(lines_code):
            bbox2 = d.textbbox((0, 0), lc, font=desc_f)
            tw2 = bbox2[2] - bbox2[0]
            d.text((x + (box_w - tw2) / 2, y + box_h + 8 + j * 16), lc, font=desc_f, fill=GRAY_DARK)

        # Arrow to next
        if i < len(states) - 1:
            ax = x + box_w
            ay = y + box_h / 2
            draw_arrow(d, ax + 3, ay, ax + gap - 3, ay, color=GRAY_DARK, width=2, head_size=7)

    # Follow-up strategy detail box
    y2 = 280
    rounded_rect(d, (60, y2, W - 60, y2 + 180), fill=ACCENT + "10", radius=12, outline=ACCENT, width=2)
    center_text(d, 60, y2 + 5, W - 120, 30, "深入追问阶段 — 四种动态追问策略", font(16, bold=True), ACCENT)

    strategies = [
        ("深化追问 (deepen)", "回答质量好 → 同维度深入探究", GREEN),
        ("转向追问 (redirect)", "回答偏离主题 → 引导回正确方向", "#5B9BD5"),
        ("可信度验证 (credibility)", "回答疑似背诵 → 细节问题验证", "#C00000"),
        ("切换维度 (switch)", "当前维度已评估 → 切换能力维度", "#7030A0"),
    ]

    sx = 90
    for i, (name, desc, color) in enumerate(strategies):
        sy = y2 + 45 + i * 34
        rounded_rect(d, (sx, sy, sx + 220, sy + 28), fill=color + "20", radius=6, outline=color, width=1)
        center_text(d, sx, sy, 220, 28, name, font(12, bold=True), color)
        d.text((sx + 235, sy + 6), desc, font=font(12), fill=TEXT_DARK)

    img.save(os.path.join(OUT_DIR, "state_machine.png"), quality=95)
    print("Created state_machine.png")


# ============================================================
# 3. RAG Pipeline Diagram
# ============================================================
def create_rag_diagram():
    W, H = 1100, 520
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    box_f = font(14, bold=True)
    item_f = font(12)
    small_f = font(11)

    center_text(d, 0, 10, W, 40, "RAG 检索增强评分流程", title_f, PRIMARY)

    # === Left: Knowledge Base Build ===
    lx, ly = 40, 70
    rounded_rect(d, (lx, ly, lx + 480, ly + 200), fill=LIGHT_BLUE, radius=12, outline=PRIMARY_LIGHT, width=2)
    center_text(d, lx, ly + 5, 480, 28, "知识库构建流程 (离线)", font(15, bold=True), PRIMARY)

    steps_build = [
        ("专业文档收集", "data/content_source/", PRIMARY_LIGHT),
        ("文档分块", "按段落切分 + 元数据标注", GREEN),
        ("向量嵌入", "Qwen text-embedding-v3\n128维向量 | 批量10条", ACCENT),
        ("向量入库", "Milvus 集合:\ninterview_kb_chunks", "#7030A0"),
    ]

    bx, by = lx + 20, ly + 40
    bw, bh = 95, 70
    for i, (name, desc, color) in enumerate(steps_build):
        cx = bx + i * (bw + 20)
        rounded_rect(d, (cx, by, cx + bw, by + bh), fill=color + "20", radius=8, outline=color, width=1)
        center_text(d, cx, by + 2, bw, 22, name, font(11, bold=True), color)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=font(9))
            tw = bbox[2] - bbox[0]
            d.text((cx + (bw - tw) / 2, by + 26 + j * 14), line, font=font(9), fill=GRAY_DARK)
        if i < len(steps_build) - 1:
            draw_arrow(d, cx + bw + 2, by + bh / 2, cx + bw + 18, by + bh / 2, PRIMARY_LIGHT, 2, 6)

    # Metadata tags
    md_y = by + bh + 15
    d.text((bx, md_y), "元数据标签:", font=font(11, bold=True), fill=TEXT_DARK)
    tags = ["role_code (岗位)", "competency_code (能力维度)", "doc_type (文档类型)", "doc_id"]
    tx = bx + 90
    for tag in tags:
        rounded_rect(d, (tx, md_y - 2, tx + 160, md_y + 20), fill=LIGHT_PURPLE, radius=4)
        d.text((tx + 6, md_y), tag, font=font(10), fill="#7030A0")
        tx += 170

    # === Right: Retrieval Flow ===
    rx, ry = 40, 290
    rounded_rect(d, (rx, ry, rx + 1020, ry + 210), fill=LIGHT_GREEN, radius=12, outline=GREEN, width=2)
    center_text(d, rx, ry + 5, 1020, 28, "评分时检索流程 (在线)", font(15, bold=True), GREEN)

    flow_steps = [
        ("用户回答", "文本/语音转文本", PRIMARY_LIGHT, 130),
        ("生成查询向量", "embedding API", ACCENT, 130),
        ("Milvus 检索", "按岗位过滤\nTop-K=6\n余弦相似度", "#7030A0", 130),
        ("证据注入", "检索结果注入\nLLM Prompt", GREEN, 130),
        ("LLM 综合评分", "文本语义评分\n+ RAG证据对比\n→ 多维度得分", "#C00000", 150),
        ("评分结果", "分数 + 证据\n+ 改进建议", PRIMARY, 130),
    ]

    fx, fy = rx + 20, ry + 40
    for i, (name, desc, color, fw) in enumerate(flow_steps):
        fh = 70
        rounded_rect(d, (fx, fy, fx + fw, fy + fh), fill=color + "18", radius=8, outline=color, width=2)
        center_text(d, fx, fy + 2, fw, 22, name, font(12, bold=True), color)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=font(10))
            tw = bbox[2] - bbox[0]
            d.text((fx + (fw - tw) / 2, fy + 24 + j * 15), line, font=font(10), fill=TEXT_DARK)
        if i < len(flow_steps) - 1:
            draw_arrow(d, fx + fw + 2, fy + fh / 2, fx + fw + 16, fy + fh / 2, GRAY_DARK, 2, 6)
        fx += fw + 18

    # Key insight box
    ky = ry + 125
    rounded_rect(d, (rx + 30, ky, rx + 990, ky + 70), fill=WHITE, radius=8, outline=ACCENT, width=1)
    d.text((rx + 45, ky + 8), "核心价值:", font=font(12, bold=True), fill=ACCENT)
    d.text((rx + 45, ky + 30), "传统方案仅依赖 LLM 直接评分，存在幻觉风险。RAG 方案通过检索专业知识库中的权威内容作为评分依据，", font=font(11), fill=TEXT_DARK)
    d.text((rx + 45, ky + 48), "使评分结果有据可依，显著提升评分的专业性和客观性。", font=font(11), fill=TEXT_DARK)

    img.save(os.path.join(OUT_DIR, "rag_pipeline.png"), quality=95)
    print("Created rag_pipeline.png")


# ============================================================
# 4. Scoring System Diagram
# ============================================================
def create_scoring_diagram():
    W, H = 1100, 480
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    center_text(d, 0, 10, W, 40, "多维度评分体系", title_f, PRIMARY)

    # Three scoring pillars
    pillars = [
        ("文本语义评分", PRIMARY_LIGHT, [
            ("技术正确性", "对比RAG知识库验证准确性"),
            ("技术深度", "评估理解深度而非表面回答"),
            ("逻辑结构", "回答条理性和论证连贯性"),
            ("岗位匹配度", "是否贴合目标岗位要求"),
            ("表达完整度", "是否完整覆盖问题要点"),
        ]),
        ("语音声学分析", GREEN, [
            ("音量稳定性", "语音音量是否均匀稳定"),
            ("停顿比例", "停顿频率和时长分析"),
            ("语速", "回答速度是否适中"),
            ("音调变化", "语调自然度和变化性"),
            ("有声比例", "有效语音占总时长比例"),
        ]),
        ("RAG 证据融合", ACCENT, [
            ("知识库匹配", "检索相关专业知识片段"),
            ("证据对比", "将回答与权威知识比对"),
            ("评分增强", "提升评分客观性和准确性"),
            ("依据输出", "返回评分所用的参考片段"),
            ("置信度评估", "根据检索相似度调整权重"),
        ]),
    ]

    pw, ph = 320, 350
    gap = 30
    start_x = (W - 3 * pw - 2 * gap) / 2
    py = 60

    for i, (title, color, items) in enumerate(pillars):
        px = start_x + i * (pw + gap)
        # Pillar box
        rounded_rect(d, (px, py, px + pw, py + ph), fill=color + "08", radius=12, outline=color, width=2)
        # Title bar
        rounded_rect(d, (px, py, px + pw, py + 40), fill=color, radius=12)
        # Fix bottom corners of title bar
        d.rectangle((px, py + 28, px + pw, py + 40), fill=color)
        center_text(d, px, py + 2, pw, 38, title, font(16, bold=True), WHITE)

        # Items
        for j, (name, desc) in enumerate(items):
            iy = py + 52 + j * 58
            # Item box
            rounded_rect(d, (px + 12, iy, px + pw - 12, iy + 50), fill=WHITE, radius=8, outline=color + "60", width=1)
            d.text((px + 22, iy + 4), name, font=font(13, bold=True), fill=color)
            d.text((px + 22, iy + 26), desc, font=font(11), fill=GRAY_DARK)

    # Bottom: fusion arrow
    fy = py + ph + 15
    # Arrow lines from each pillar to center
    cx = W / 2
    for i in range(3):
        px = start_x + i * (pw + gap) + pw / 2
        draw_arrow(d, px, fy - 5, cx, fy + 20, GRAY_DARK, 2, 7)

    # Result box
    rounded_rect(d, (cx - 150, fy + 22, cx + 150, fy + 58), fill=PRIMARY, radius=10)
    center_text(d, cx - 150, fy + 22, 300, 36, "综合评分 + 面试报告", font(15, bold=True), WHITE)

    # Tech stack note
    d.text((50, fy + 40), "技术栈: librosa + webrtcvad + scipy (声学特征)  |  Qwen LLM (语义评分)  |  Milvus (向量检索)", font=font(11), fill=GRAY_DARK)

    img.save(os.path.join(OUT_DIR, "scoring_system.png"), quality=95)
    print("Created scoring_system.png")


# ============================================================
# 5. Deployment Architecture Diagram
# ============================================================
def create_deploy_diagram():
    W, H = 1100, 500
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    center_text(d, 0, 10, W, 40, "Docker Compose 部署架构", title_f, PRIMARY)

    # Nginx gateway
    rounded_rect(d, (350, 60, 750, 110), fill=PRIMARY + "18", radius=10, outline=PRIMARY, width=2)
    center_text(d, 350, 60, 400, 50, "Nginx  (端口 80)", font(15, bold=True), PRIMARY)
    d.text((360, 88), "/api/* → backend:8000  |  /* → frontend:4173", font=font(11), fill=GRAY_DARK)

    # Two columns: frontend/backend
    draw_arrow(d, 450, 110, 250, 145, GRAY_DARK, 2, 7)
    draw_arrow(d, 650, 110, 850, 145, GRAY_DARK, 2, 7)

    # Frontend
    rounded_rect(d, (100, 145, 400, 210), fill=PRIMARY_LIGHT + "18", radius=10, outline=PRIMARY_LIGHT, width=2)
    center_text(d, 100, 147, 300, 28, "Vue 3 Frontend", font(14, bold=True), PRIMARY_LIGHT)
    d.text((115, 178), "Node 24 | Vite | 端口 4173", font=font(11), fill=GRAY_DARK)

    # Backend
    rounded_rect(d, (700, 145, 1050, 230), fill=GREEN + "18", radius=10, outline=GREEN, width=2)
    center_text(d, 700, 147, 350, 28, "FastAPI Backend", font(14, bold=True), GREEN)
    d.text((715, 178), "Python 3.12 | uvicorn | 端口 8000", font=font(11), fill=GRAY_DARK)
    d.text((715, 198), "ffmpeg | libsndfile | SQLAlchemy", font=font(11), fill=GRAY_DARK)

    # Data layer
    dy = 260
    draw_arrow(d, 875, 230, 875, dy - 5, GRAY_DARK, 2, 7)

    services = [
        (50, dy, 210, 90, "MySQL 8.4", "业务数据持久化\n端口 3306", PRIMARY_LIGHT),
        (270, dy, 210, 90, "Redis 7.4", "缓存与会话\n端口 6379", "#C00000"),
        (490, dy, 260, 90, "Milvus 2.5.4", "向量检索服务\n端口 19530", "#7030A0"),
        (760, dy, 145, 90, "Etcd", "Milvus 元数据\n端口 2379", GRAY_DARK),
        (915, dy, 145, 90, "MinIO", "Milvus 对象存储\n端口 9000", ACCENT),
    ]

    for sx, sy, sw, sh, name, desc, color in services:
        rounded_rect(d, (sx, sy, sx + sw, sy + sh), fill=color + "15", radius=10, outline=color, width=2)
        center_text(d, sx, sy + 3, sw, 30, name, font(14, bold=True), color)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=font(11))
            tw = bbox[2] - bbox[0]
            d.text((sx + (sw - tw) / 2, sy + 35 + j * 17), line, font=font(11), fill=GRAY_DARK)

    # Connection lines from Milvus to Etcd and MinIO
    draw_arrow(d, 750, dy + 45, 762, dy + 45, "#7030A0", 1, 5)
    draw_arrow(d, 750, dy + 60, 917, dy + 60, ACCENT, 1, 5)

    # Connection lines from backend to data services
    draw_arrow(d, 770, 230, 155, dy - 2, PRIMARY_LIGHT, 1, 5)
    draw_arrow(d, 800, 230, 375, dy - 2, "#C00000", 1, 5)
    draw_arrow(d, 900, 230, 620, dy - 2, "#7030A0", 1, 5)

    # Volumes
    vy = dy + 105
    rounded_rect(d, (50, vy, W - 50, vy + 60), fill=LIGHT_BLUE, radius=10, outline=PRIMARY_LIGHT, width=1)
    d.text((70, vy + 8), "Docker Volumes (数据持久化):", font=font(12, bold=True), fill=PRIMARY)
    vols = ["mysql_data", "redis_data", "milvus_data", "etcd_data", "minio_data", "upload_data (简历/音频)"]
    vx = 70
    for vol in vols:
        rounded_rect(d, (vx, vy + 30, vx + 150, vy + 52), fill=WHITE, radius=4, outline=PRIMARY_LIGHT, width=1)
        center_text(d, vx, vy + 30, 150, 22, vol, font(10), PRIMARY)
        vx += 162

    img.save(os.path.join(OUT_DIR, "deployment.png"), quality=95)
    print("Created deployment.png")


# ============================================================
# 6. Module Overview Diagram
# ============================================================
def create_module_overview():
    W, H = 1100, 400
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    title_f = font(22, bold=True)
    center_text(d, 0, 10, W, 40, "系统功能模块全景图", title_f, PRIMARY)

    # Core modules (highlighted)
    core_modules = [
        ("模拟面试核心", "状态机流转\n智能提问追问\n多轮对话管理", ACCENT),
        ("RAG 检索增强", "知识库构建\n向量检索\n证据融合评分", "#7030A0"),
        ("多维评分引擎", "文本语义评分\n语音声学分析\nRAG 证据增强", "#C00000"),
    ]

    # Support modules
    support_modules = [
        ("用户认证", "注册登录\nJWT鉴权", PRIMARY_LIGHT),
        ("简历管理", "上传解析\nLLM提取", "#5B9BD5"),
        ("岗位管理", "岗位分类\n能力维度", GREEN),
        ("报告生成", "异步生成\n雷达图分析", ACCENT),
        ("成长追踪", "趋势分析\n薄弱项识别", "#7030A0"),
        ("语音面试", "WebSocket\nASR/TTS", "#C00000"),
    ]

    # Core section
    cy = 65
    d.text((50, cy), "★ 核心模块", font=font(15, bold=True), fill=ACCENT)
    cx = 50
    for name, desc, color in core_modules:
        cw, ch = 320, 110
        rounded_rect(d, (cx, cy + 30, cx + cw, cy + 30 + ch), fill=color + "12", radius=12, outline=color, width=3)
        center_text(d, cx, cy + 32, cw, 30, "★ " + name, font(15, bold=True), color)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=font(12))
            tw = bbox[2] - bbox[0]
            d.text((cx + (cw - tw) / 2, cy + 65 + j * 20), line, font=font(12), fill=TEXT_DARK)
        cx += cw + 30

    # Support section
    sy = 225
    d.text((50, sy), "辅助模块", font=font(15, bold=True), fill=GRAY_DARK)
    sx = 50
    for name, desc, color in support_modules:
        sw, sh = 155, 90
        rounded_rect(d, (sx, sy + 30, sx + sw, sy + 30 + sh), fill=color + "10", radius=10, outline=color + "80", width=1)
        center_text(d, sx, sy + 32, sw, 24, name, font(13, bold=True), color)
        lines = desc.split("\n")
        for j, line in enumerate(lines):
            bbox = d.textbbox((0, 0), line, font=font(11))
            tw = bbox[2] - bbox[0]
            d.text((sx + (sw - tw) / 2, sy + 58 + j * 18), line, font=font(11), fill=GRAY_DARK)
        sx += sw + 18

    img.save(OUT_DIR / "modules_overview.png", quality=95)
    print("Created modules_overview.png")


# ============================================================
# Run all
# ============================================================
if __name__ == "__main__":
    create_architecture_diagram()
    create_state_machine()
    create_rag_diagram()
    create_scoring_diagram()
    create_deploy_diagram()
    create_module_overview()
    print(f"\nAll diagrams saved to: {OUT_DIR}")

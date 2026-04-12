from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
TODAY = date(2026, 4, 4)

ROLE_SPECS = {
    "cpp_backend": {
        "display_name": "C++ 后端",
        "question_quotas": {
            "foundation": 52,
            "principle": 48,
            "scenario": 54,
            "project": 48,
            "design_coding": 40,
            "comparison": 36,
            "troubleshooting": 42,
        },
        "faq_quotas": {
            "language": 34,
            "memory": 34,
            "stl_template": 28,
            "concurrency": 34,
            "network_os": 30,
            "db_cache_mq": 30,
            "system_design": 30,
        },
        "competencies": {
            "cpp_language": "C++ 语言基础",
            "os_network": "操作系统与网络",
            "algorithm": "算法与数据结构",
            "system_design": "系统设计",
            "performance": "性能优化与排障",
            "project_depth": "项目深度与可信度",
        },
    },
    "web_frontend": {
        "display_name": "Web 前端",
        "question_quotas": {
            "foundation": 50,
            "principle": 52,
            "scenario": 54,
            "project": 48,
            "design_coding": 42,
            "comparison": 34,
            "troubleshooting": 40,
        },
        "faq_quotas": {
            "html_css": 24,
            "javascript_typescript": 40,
            "browser_rendering": 34,
            "async_event_loop": 26,
            "http_cache_network": 28,
            "react": 24,
            "vue": 18,
            "engineering_perf_security": 26,
        },
        "competencies": {
            "frontend_foundation": "前端基础",
            "vue_engineering": "Vue 工程化",
            "browser_principle": "浏览器原理",
            "network_performance": "网络与性能优化",
            "architecture": "前端架构设计",
            "project_depth": "项目深度与可信度",
        },
    },
}

CPP_TOPICS = [
    ("raii", "RAII", "language", "cpp_language", "move_semantics", ["cpp", "raii"]),
    ("move_semantics", "移动语义", "language", "cpp_language", "copy_control", ["cpp", "move"]),
    ("copy_control", "拷贝控制", "language", "cpp_language", "raii", ["cpp", "copy_control"]),
    ("virtual_dispatch", "虚函数与多态", "language", "cpp_language", "object_layout", ["cpp", "virtual"]),
    ("object_layout", "对象内存布局", "language", "cpp_language", "virtual_dispatch", ["cpp", "layout"]),
    ("lambda_capture", "Lambda 捕获", "language", "cpp_language", "thread_pool", ["cpp", "lambda"]),
    ("smart_pointer", "智能指针", "memory", "cpp_language", "weak_ptr", ["cpp", "smart_pointer"]),
    ("weak_ptr", "weak_ptr", "memory", "cpp_language", "smart_pointer", ["cpp", "weak_ptr"]),
    ("memory_leak", "内存泄漏与碎片", "memory", "performance", "smart_pointer", ["cpp", "memory"]),
    ("allocator", "STL 分配器", "stl_template", "cpp_language", "vector_growth", ["cpp", "allocator"]),
    ("vector_growth", "vector 扩容", "stl_template", "cpp_language", "iterator_invalidation", ["cpp", "vector"]),
    ("iterator_invalidation", "迭代器失效", "stl_template", "cpp_language", "vector_growth", ["cpp", "iterator"]),
    ("unordered_map", "unordered_map", "stl_template", "algorithm", "mysql_index", ["cpp", "hash"]),
    ("template_instantiation", "模板实例化", "stl_template", "cpp_language", "concepts", ["cpp", "template"]),
    ("concepts", "Concepts", "stl_template", "cpp_language", "template_instantiation", ["cpp", "concepts"]),
    ("binary_search", "二分边界", "stl_template", "algorithm", "mysql_index", ["cpp", "binary_search"]),
    ("condition_variable", "条件变量", "concurrency", "os_network", "mutex_spinlock", ["cpp", "condition_variable"]),
    ("mutex_spinlock", "互斥锁与自旋锁", "concurrency", "os_network", "condition_variable", ["cpp", "mutex"]),
    ("atomic_order", "原子操作与内存序", "concurrency", "os_network", "mutex_spinlock", ["cpp", "atomic"]),
    ("thread_pool", "线程池", "concurrency", "system_design", "lambda_capture", ["cpp", "thread_pool"]),
    ("deadlock", "死锁治理", "concurrency", "os_network", "mutex_spinlock", ["cpp", "deadlock"]),
    ("tcp_handshake", "TCP 建连与挥手", "network_os", "os_network", "tcp_sticky_packet", ["cpp", "tcp"]),
    ("tcp_sticky_packet", "TCP 粘包拆包", "network_os", "os_network", "tcp_handshake", ["cpp", "protocol"]),
    ("epoll", "epoll", "network_os", "os_network", "reactor_model", ["cpp", "epoll"]),
    ("reactor_model", "Reactor 模型", "network_os", "system_design", "epoll", ["cpp", "reactor"]),
    ("process_thread", "进程与线程", "network_os", "os_network", "context_switch", ["cpp", "thread"]),
    ("context_switch", "上下文切换", "network_os", "performance", "thread_pool", ["cpp", "context_switch"]),
    ("redis_breakdown", "缓存击穿与热点治理", "db_cache_mq", "system_design", "redis_persistence", ["cpp", "redis"]),
    ("redis_persistence", "Redis 持久化", "db_cache_mq", "system_design", "redis_breakdown", ["cpp", "redis"]),
    ("mysql_index", "MySQL 索引", "db_cache_mq", "system_design", "mysql_transaction", ["cpp", "mysql"]),
    ("mysql_transaction", "事务隔离级别", "db_cache_mq", "system_design", "mysql_index", ["cpp", "transaction"]),
    ("mq_idempotency", "消息幂等与顺序性", "db_cache_mq", "system_design", "distributed_lock", ["cpp", "mq"]),
    ("distributed_lock", "分布式锁", "system_design", "system_design", "mq_idempotency", ["cpp", "lock"]),
    ("rate_limiter", "限流与熔断", "system_design", "system_design", "service_degradation", ["cpp", "rate_limit"]),
    ("service_degradation", "降级与容灾", "system_design", "system_design", "rate_limiter", ["cpp", "degrade"]),
    ("observability", "可观测性", "system_design", "performance", "cpu_high", ["cpp", "observability"]),
    ("cpu_high", "CPU 飙高排查", "system_design", "performance", "p99_latency", ["cpp", "cpu"]),
    ("p99_latency", "尾延迟治理", "system_design", "performance", "cpu_high", ["cpp", "latency"]),
    ("gateway_architecture", "网关架构", "system_design", "project_depth", "project_authenticity", ["cpp", "gateway"]),
    ("project_authenticity", "项目真实性", "system_design", "project_depth", "gateway_architecture", ["cpp", "project"]),
]

WEB_TOPICS = [
    ("closure", "闭包", "javascript_typescript", "frontend_foundation", "scope_chain", ["web", "closure"]),
    ("scope_chain", "作用域链", "javascript_typescript", "frontend_foundation", "closure", ["web", "scope"]),
    ("prototype_chain", "原型链", "javascript_typescript", "frontend_foundation", "this_binding", ["web", "prototype"]),
    ("this_binding", "this 绑定", "javascript_typescript", "frontend_foundation", "prototype_chain", ["web", "this"]),
    ("typescript_generic", "TypeScript 泛型", "javascript_typescript", "frontend_foundation", "react_state", ["web", "typescript"]),
    ("dom_event", "DOM 事件模型", "javascript_typescript", "frontend_foundation", "event_loop", ["web", "dom"]),
    ("deep_shallow_copy", "深拷贝与浅拷贝", "javascript_typescript", "frontend_foundation", "react_state", ["web", "copy"]),
    ("html_semantics", "HTML 语义化", "html_css", "frontend_foundation", "accessibility", ["web", "html"]),
    ("css_layout", "CSS 布局", "html_css", "frontend_foundation", "reflow_repaint", ["web", "css"]),
    ("accessibility", "可访问性", "html_css", "architecture", "html_semantics", ["web", "a11y"]),
    ("event_loop", "事件循环", "async_event_loop", "browser_principle", "promise", ["web", "event_loop"]),
    ("promise", "Promise", "async_event_loop", "frontend_foundation", "async_await", ["web", "promise"]),
    ("async_await", "async/await", "async_event_loop", "frontend_foundation", "promise", ["web", "async"]),
    ("reflow_repaint", "回流与重绘", "browser_rendering", "browser_principle", "css_layout", ["web", "render"]),
    ("script_blocking", "脚本阻塞", "browser_rendering", "browser_principle", "event_loop", ["web", "script"]),
    ("ssr_hydration", "SSR 与 Hydration", "browser_rendering", "architecture", "micro_frontend", ["web", "ssr"]),
    ("browser_cache", "浏览器缓存", "http_cache_network", "network_performance", "service_worker", ["web", "cache"]),
    ("cookie_storage", "Cookie 与 Web Storage", "http_cache_network", "frontend_foundation", "xss_csrf", ["web", "cookie"]),
    ("cors", "同源策略与 CORS", "http_cache_network", "network_performance", "cookie_storage", ["web", "cors"]),
    ("react_state", "React 状态管理", "react", "frontend_foundation", "react_effect", ["web", "react"]),
    ("react_effect", "React 副作用", "react", "frontend_foundation", "react_rendering", ["web", "useEffect"]),
    ("react_rendering", "React 渲染机制", "react", "browser_principle", "react_effect", ["web", "rendering"]),
    ("vue_reactivity", "Vue 响应式", "vue", "vue_engineering", "vue_watch_computed", ["web", "vue"]),
    ("vue_diff_key", "Vue key 与 diff", "vue", "vue_engineering", "vue_reactivity", ["web", "key"]),
    ("vue_watch_computed", "watch 与 computed", "vue", "vue_engineering", "vue_reactivity", ["web", "watch"]),
    ("vue_router_guard", "路由守卫", "vue", "vue_engineering", "permission_system", ["web", "router"]),
    ("pinia_state", "Pinia 状态管理", "vue", "vue_engineering", "vue_router_guard", ["web", "pinia"]),
    ("webpack_vite", "Webpack 与 Vite", "engineering_perf_security", "architecture", "tree_shaking", ["web", "build"]),
    ("tree_shaking", "Tree Shaking", "engineering_perf_security", "network_performance", "code_split", ["web", "bundle"]),
    ("code_split", "代码分割", "engineering_perf_security", "network_performance", "tree_shaking", ["web", "code_split"]),
    ("bundle_analysis", "包体积分析", "engineering_perf_security", "network_performance", "code_split", ["web", "bundle"]),
    ("web_vitals", "Web Vitals", "engineering_perf_security", "network_performance", "lcp", ["web", "vitals"]),
    ("lcp", "LCP", "engineering_perf_security", "network_performance", "web_vitals", ["web", "lcp"]),
    ("image_optimization", "图片优化", "engineering_perf_security", "network_performance", "lcp", ["web", "image"]),
    ("xss_csrf", "XSS 与 CSRF", "engineering_perf_security", "network_performance", "csp", ["web", "security"]),
    ("csp", "CSP", "engineering_perf_security", "architecture", "xss_csrf", ["web", "csp"]),
    ("permission_system", "权限系统", "engineering_perf_security", "architecture", "vue_router_guard", ["web", "permission"]),
    ("component_library", "组件库", "engineering_perf_security", "architecture", "design_system", ["web", "component_library"]),
    ("design_system", "设计系统", "engineering_perf_security", "architecture", "component_library", ["web", "design_system"]),
    ("micro_frontend", "微前端", "engineering_perf_security", "architecture", "component_library", ["web", "micro_frontend"]),
    ("dashboard_performance", "大屏性能排查", "engineering_perf_security", "project_depth", "bundle_analysis", ["web", "dashboard"]),
    ("monitoring_debug", "监控与调试", "engineering_perf_security", "project_depth", "source_map", ["web", "monitoring"]),
]

COMMON_WEAKNESSES = [
    "回答结构松散", "只讲方案不讲取舍", "没有量化结果", "个人职责边界不清", "排障只讲现象不讲根因",
    "答题重点分散", "边界条件意识弱", "缺少降级与兜底意识", "缺少监控与验证闭环", "稳定性意识不足",
    "数据建模表达不清", "状态流描述混乱", "扩展性思考不足", "一致性与可用性取舍薄弱", "性能问题没有证据",
    "表达不够清晰", "项目故事线不完整", "无法区分主次矛盾", "接口边界定义模糊", "测试与验证意识不足",
    "安全边界意识不足", "缓存策略表达不完整", "异常处理策略不清", "调试路径缺少证据", "容量与成本估算不足",
    "依赖治理意识不足", "复用与抽象能力不足", "代码质量标准不清", "异步模型理解不稳", "渲染链路理解薄弱",
    "浏览器基础不扎实", "生命周期建模不稳定", "内存模型理解模糊", "锁策略选择缺少依据", "协议设计表达不足",
    "数据库取舍理由薄弱", "项目范围描述失真", "业务价值说明不足", "协作与推动细节不足", "故障复盘不完整",
    "工具链和工程化意识不足", "可访问性意识缺失", "包治理意识不足", "组件边界模糊", "状态归一化意识不足",
    "运维可操作性考虑不足", "成本意识不足", "延迟归因能力不足", "缓存失效策略薄弱", "回答缺乏结论",
]

COMMON_DEDUCTIONS = [
    "只罗列技术栈，没有职责和结果", "夸大能力词", "项目描述没有时间和范围", "没有任何量化指标", "把团队成果完全说成个人成果",
    "职责边界不清", "没有体现岗位相关性", "项目难点描述过于空泛", "结果只写提升了很多", "没有说明验证方式",
    "缺少线上问题处理经历", "技术动作不成链路", "没有表现 trade-off", "没有体现稳定性意识", "没有体现性能意识",
    "简历结构混乱", "关键词堆砌严重", "没有明确产出物", "只写参与，不写负责部分", "没有说明业务背景",
    "不同经历重复描述", "语言过于口语化", "专业名词使用不准确", "项目成果与岗位不匹配", "没有体现协作方式",
    "没有体现复盘意识", "无时间线或时间线混乱", "技能部分与项目事实脱节", "没有体现问题复杂度", "缺少工程化细节",
]

LEARNING_TRACKS = {
    "cpp_backend": ["C++ 生命周期与资源管理", "STL 与模板基础强化", "并发与同步专题", "Linux 网络编程路线", "缓存与数据库路线", "消息队列与幂等治理", "系统设计与容量评估", "性能分析与 Profiling", "线上故障排查方法", "项目表达与技术复盘"],
    "web_frontend": ["HTML/CSS 基础补齐", "JavaScript 异步与语言机制", "浏览器渲染链路专题", "HTTP 缓存与网络优化", "React 核心机制强化", "Vue 工程化与状态设计", "构建工具与包治理", "前端性能指标治理", "安全与权限设计", "项目表达与架构复盘"],
}

LEVEL_UP_TRACKS = {
    "cpp_backend": ["从语法熟练到所有权建模", "从 API 使用到机制解释", "从单机优化到链路治理", "从答题到系统设计", "从写功能到容量规划", "从能排障到能构建告警闭环", "从项目参与到项目主导", "从局部优化到稳定性治理", "从实现细节到业务价值表达", "从经验分享到账面可验证成果"],
    "web_frontend": ["从页面实现到状态建模", "从 API 记忆到机制解释", "从组件开发到系统设计", "从性能优化到指标治理", "从框架使用到工程化抽象", "从单点排查到可观测性建设", "从活动页开发到复杂工作台设计", "从功能交付到设计系统", "从个人开发到跨团队协同", "从简历叙述到架构复盘"],
}

RESUME_SCENARIOS = {
    "cpp_backend": ["网关低延迟优化", "撮合链路优化", "即时通讯后端", "风控规则引擎", "日志采集链路", "订单中心重构", "推荐召回服务", "对象存储代理", "任务调度系统", "告警平台", "自研 RPC 框架", "缓存治理项目", "检索服务优化", "计费系统", "直播后端", "配置中心", "报表引擎", "工作流后端", "部署平台", "认证鉴权服务"],
    "web_frontend": ["中后台大屏重构", "营销活动页优化", "权限工作台", "组件库建设", "CRM 工作台", "运营平台重构", "可视化编辑器", "内容平台前端", "直播控制台", "数据分析平台", "统一登录门户", "低代码配置台", "搜索结果页优化", "性能治理项目", "移动 H5 专题", "监控告警前端", "SSO 管理台", "国际化站点", "表单搭建器", "审批中心"],
}

COMPANY_STYLES = ["中后台业务平台", "高并发交易系统", "云原生基础设施", "广告投放平台", "直播互动平台", "电商履约系统", "AI 应用平台", "内容分发平台", "SaaS 管理后台", "金融风控系统", "搜索推荐平台", "数据可视化平台", "跨端协同平台", "ToB 工作台", "基础组件团队", "开放平台团队", "即时通讯团队", "运维自动化平台", "支付清结算团队", "海外业务站点"]

PERSONA_NAMES = ["演示用户", "林然", "周越", "陈舟", "宋闻", "唐语", "顾淮", "陆翎", "夏弥", "蒋衡", "许知", "白屿"]

QUESTION_OFFSETS = {"foundation": 0, "principle": 3, "scenario": 7, "project": 11, "design_coding": 17, "comparison": 23, "troubleshooting": 29}
QUESTION_DIFFICULTIES = {
    "foundation": ("easy", "easy", "medium"),
    "principle": ("medium", "medium", "hard"),
    "scenario": ("medium", "medium", "hard"),
    "project": ("medium", "hard"),
    "design_coding": ("hard", "hard", "medium"),
    "comparison": ("medium", "medium", "hard"),
    "troubleshooting": ("hard", "medium", "hard"),
}
FAQ_ANGLES = (("definition", "本质理解"), ("mechanism", "机制解释"), ("comparison", "对比辨析"), ("scenario", "场景应用"), ("pitfall", "误区与排障"))
LEVEL_SEQUENCE = ("beginner", "intermediate", "intermediate", "advanced")


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    ensure_parent(path)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, payload) -> None:
    ensure_parent(path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if any(ch in text for ch in [":", "#", "[", "]", "{", "}", ",", '"', "'"]):
        return json.dumps(text, ensure_ascii=False)
    return text


def render_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(yaml_scalar(item) for item in value)}]")
        else:
            lines.append(f"{key}: {yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def render_markdown(meta: dict, title: str, sections: list[tuple[str, str | list[str]]]) -> str:
    blocks = [render_frontmatter(meta), f"# {title}", ""]
    for heading, body in sections:
        blocks.append(f"## {heading}")
        if isinstance(body, list):
            blocks.extend(f"- {item}" for item in body)
        else:
            blocks.append(body)
        blocks.append("")
    return "\n".join(blocks).strip() + "\n"


def flatten_sections(sections: list[tuple[str, str | list[str]]]) -> dict:
    return {heading.lower().replace(" ", "_"): body for heading, body in sections}


def build_content(title: str, sections: list[tuple[str, str | list[str]]]) -> str:
    lines = [f"标题: {title}"]
    for heading, body in sections:
        lines.append(f"{heading}:")
        if isinstance(body, list):
            lines.extend(f"- {item}" for item in body)
        else:
            lines.append(body)
        lines.append("")
    return "\n".join(lines).strip()


def build_record(*, doc_id: str, role_code: str, doc_type: str, source_type: str, topic: str, difficulty: str, title: str, source_path: str, tags: list[str], sections: list[tuple[str, str | list[str]]], parsed_meta: dict, keyword: str, extra_metadata: dict | None = None) -> dict:
    content = build_content(title, sections)
    return {
        "id": doc_id,
        "source_id": doc_id,
        "source_dataset": "demo_rag_v2",
        "source_path": source_path,
        "role_code": role_code,
        "doc_type": doc_type,
        "source_type": source_type,
        "topic": topic,
        "difficulty": difficulty,
        "title": title,
        "content": content,
        "embedding_text": f"标题: {title}\n岗位: {role_code}\n文档类型: {doc_type}\n主题: {topic}\n难度: {difficulty}\n{content}",
        "tags": list(dict.fromkeys(tags)),
        "aliases": [],
        "keyword": keyword,
        "parsed_meta": parsed_meta,
        "sections": flatten_sections(sections),
        "metadata": {
            "role_code": role_code,
            "doc_type": doc_type,
            "source_type": source_type,
            "topic": topic,
            "difficulty": difficulty,
            "keyword": keyword,
            "source_path": source_path,
            "source_dataset": "demo_rag_v2",
            **(extra_metadata or {}),
        },
    }


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_topics(items: list[tuple]) -> list[dict]:
    payload = []
    for slug, label, domain, competency_code, related, tags in items:
        payload.append({"slug": slug, "label": label, "domain": domain, "competency_code": competency_code, "related": related, "tags": list(tags)})
    return payload


def topic_label(topics: list[dict], slug: str) -> str:
    for topic in topics:
        if topic["slug"] == slug:
            return topic["label"]
    return slug


def topic_summary(role_name: str, label: str) -> str:
    return f"{label} 是 {role_name} 面试里常见的高频知识点，回答时应覆盖定义、机制、适用场景、边界条件和代价。"


def reset_generated_dirs() -> None:
    for target in (
        DATA_DIR / "content_source",
        DATA_DIR / "metadata",
        DATA_DIR / "schemas",
        DATA_DIR / "demo" / "users",
        DATA_DIR / "demo" / "resumes",
        DATA_DIR / "demo" / "practice",
        DATA_DIR / "demo" / "interviews",
        DATA_DIR / "demo" / "growth",
        DATA_DIR / "runtime_corpus",
        DATA_DIR / "build_artifacts",
    ):
        if target.exists():
            shutil.rmtree(target)
    for target in (
        DATA_DIR / "demo" / "users.json",
    ):
        if target.exists():
            target.unlink()


def question_sections(role_name: str, topic: dict, category: str, pair_label: str) -> tuple[str, list[tuple[str, str | list[str]]], str]:
    label = topic["label"]
    summary = topic_summary(role_name, label)
    if category == "foundation":
        title = f"{label} 的核心概念是什么？"
        question = f"请解释 {label} 的核心概念，并说明它主要解决什么问题。"
        answer = f"{summary} 高分回答要先给结论，再说明它解决的问题、适用边界和真实使用场景。"
    elif category == "principle":
        title = f"{label} 的底层原理怎么解释？"
        question = f"请从机制角度解释 {label} 为什么能工作，并说明它的关键约束。"
        answer = f"{summary} 原理题需要把关键流程、收益来源、限制条件和代价讲清楚。"
    elif category == "scenario":
        title = f"在真实场景里你会怎样使用 {label}？"
        question = f"如果在项目里遇到和 {label} 相关的问题，你会如何判断是否采用它，并如何验证效果？"
        answer = f"{summary} 场景题的关键是说明为什么这样选、怎么验证结果以及不选时的替代方案。"
    elif category == "project":
        title = f"请结合项目讲讲 {label} 的落地经验"
        question = f"请结合一个真实项目，说明你在处理 {label} 相关问题时的职责、方案、指标和复盘。"
        answer = f"项目题应把 {label} 放回真实业务背景，讲清你本人职责、方案取舍、结果指标和后续优化。"
    elif category == "design_coding":
        title = f"围绕 {label} 设计一个可落地方案"
        question = f"如果让你设计一个和 {label} 强相关的模块，请说明核心接口、状态流转、监控指标和异常处理。"
        answer = f"{summary} 设计题要强调职责边界、关键数据结构、失败路径和可观测性。"
    elif category == "comparison":
        title = f"{label} 和 {pair_label} 应该怎么比较？"
        question = f"请对比 {label} 和 {pair_label} 的适用场景、优缺点以及你在项目里会如何选择。"
        answer = f"对比题要从目标、复杂度、维护成本、风险边界和团队成本几个维度回答，而不是只说哪个更好。"
    else:
        title = f"如果 {label} 出问题，你会怎么排查？"
        question = f"如果线上出现和 {label} 相关的故障，请给出你的排查顺序、证据来源和止血策略。"
        answer = f"{summary} 排障题的核心是分层定性、建立证据链、快速止血，再回到根因和长期治理。"
    sections = [
        ("question", question),
        ("reference_answer", answer),
        ("key_points", [f"先讲清 {label} 的定义或问题背景", "再说明机制、限制和真实场景", "补充项目证据、指标或验证方式", "明确边界条件与风险点"]),
        ("common_mistakes", ["只背结论，不解释为什么", "不说明适用边界和代价", "无法给出真实项目或验证证据"]),
        ("scoring_rubric", ["90+：原理、取舍、指标和项目复盘都能讲清", "75+：原理与场景清楚，但细节略少", "60+：只会背概念，没有真实落地证据", "40-：概念混乱或无法自洽"]),
        ("follow_up_questions", [f"{label} 在你的项目里最难的取舍是什么？", f"如果结果不符合预期，你会怎样验证是不是 {label} 引起的？", f"{label} 和 {pair_label} 的边界应该怎么划分？"]),
    ]
    return title, sections, question


def generate_questions(role_code: str, topics: list[dict]) -> tuple[list[dict], dict]:
    role_name = ROLE_SPECS[role_code]["display_name"]
    records: list[dict] = []
    buckets: defaultdict[str, list[str]] = defaultdict(list)
    seq = 1
    for category, quota in ROLE_SPECS[role_code]["question_quotas"].items():
        # Each category-question template only yields one semantically distinct prompt per topic.
        # Capping here prevents the seed pipeline from cycling the same topic set to fill quota.
        effective_quota = min(quota, len(topics))
        for index in range(effective_quota):
            topic = topics[(index + QUESTION_OFFSETS[category]) % len(topics)]
            pair = topics[(index + QUESTION_OFFSETS[category] + 5) % len(topics)]
            difficulty = QUESTION_DIFFICULTIES[category][index % len(QUESTION_DIFFICULTIES[category])]
            title, sections, question_text = question_sections(role_name, topic, category, pair["label"])
            doc_id = f"q_{role_code}_{category}_{seq:03d}"
            path = DATA_DIR / "content_source" / "roles" / role_code / "interview_questions" / category / f"{doc_id}_{topic['slug']}.md"
            meta = {"id": doc_id, "doc_type": "question", "role": role_code, "category": category, "subcategory": topic["slug"], "question_type": category, "difficulty": difficulty, "tags": [role_code, category, topic["slug"], topic["domain"], topic["competency_code"], *topic["tags"]], "source_priority": "high", "applicable_features": ["interview", "scoring", "practice", "follow_up"]}
            write_text(path, render_markdown(meta, title, sections))
            records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="question", source_type=topic["competency_code"], topic=topic["slug"], difficulty=difficulty, title=title, source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"题目": question_text, "岗位": role_code, "题型": category, "知识点": topic["label"]}, keyword=topic["label"], extra_metadata={"category": category, "subcategory": topic["slug"], "competency_code": topic["competency_code"]}))
            buckets[topic["competency_code"]].append(question_text)
            seq += 1
    seeds = {
        "opening": [{"question": question, "competency_code": "project_depth"} for question in buckets["project_depth"][:6]],
        "competencies": {code: [{"question": question} for question in questions[:6]] for code, questions in buckets.items()},
        "follow_up": {"deepen": "请继续围绕 {competency} 展开。", "redirect": "我们先回到题目核心，请直接回答 {competency}。", "credibility": "这件事里你具体负责什么？怎么验证结果？"},
    }
    return records, seeds


def generate_faq(role_code: str, topics: list[dict]) -> list[dict]:
    quotas = ROLE_SPECS[role_code]["faq_quotas"]
    domain_map = defaultdict(list)
    for topic in topics:
        domain_map[topic["domain"]].append(topic)
    alias_map = {
        "cpp_backend": {"language": {"language"}, "memory": {"memory"}, "stl_template": {"stl_template"}, "concurrency": {"concurrency"}, "network_os": {"network_os"}, "db_cache_mq": {"db_cache_mq"}, "system_design": {"system_design"}},
        "web_frontend": {"html_css": {"html_css"}, "javascript_typescript": {"javascript_typescript"}, "browser_rendering": {"browser_rendering"}, "async_event_loop": {"async_event_loop"}, "http_cache_network": {"http_cache_network"}, "react": {"react"}, "vue": {"vue"}, "engineering_perf_security": {"engineering_perf_security"}},
    }[role_code]
    records: list[dict] = []
    seq = 1
    for domain, quota in quotas.items():
        domain_topics = [topic for topic in topics if topic["domain"] in alias_map[domain]]
        combinations = [(topic, angle) for topic in domain_topics for angle in FAQ_ANGLES]
        # FAQ uniqueness is bounded by domain topics × angle variants.
        effective_quota = min(quota, len(combinations))
        for index in range(effective_quota):
            topic, (angle_key, angle_label) = combinations[index]
            level = LEVEL_SEQUENCE[index % len(LEVEL_SEQUENCE)]
            title = f"{topic['label']}：{angle_label}"
            question = {"definition": f"{topic['label']} 的核心概念是什么？", "mechanism": f"{topic['label']} 为什么会这样工作？", "comparison": f"{topic['label']} 和 {topic_label(topics, topic['related'])} 的关键区别是什么？", "scenario": f"{topic['label']} 在真实项目里适合怎么用？", "pitfall": f"{topic['label']} 最容易出现哪些误区或线上问题？"}[angle_key]
            answer = f"{topic_summary(ROLE_SPECS[role_code]['display_name'], topic['label'])} 回答时要强调定义、机制、场景和边界，而不是只背结论。"
            sections = [("question", question), ("answer", answer), ("extended_explanation", f"围绕 {topic['label']} 继续展开时，应补充真实项目中的收益、代价、监控方式和不适用场景。"), ("follow_up_questions", [f"{topic['label']} 和 {topic_label(topics, topic['related'])} 的边界该怎么划分？", f"你在项目里如何验证 {topic['label']} 的效果？"])]
            doc_id = f"faq_{role_code}_{domain}_{seq:03d}"
            path = DATA_DIR / "content_source" / "roles" / role_code / "faq" / domain / f"{doc_id}_{topic['slug']}_{angle_key}.md"
            meta = {"id": doc_id, "doc_type": "knowledge", "role": role_code, "category": domain, "subcategory": topic["slug"], "level": level, "tags": [role_code, domain, topic["slug"], topic["competency_code"], angle_key, *topic["tags"]], "applicable_features": ["search", "interview", "follow_up"]}
            write_text(path, render_markdown(meta, title, sections))
            records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="knowledge", source_type="knowledge", topic=topic["slug"], difficulty=level, title=title, source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"题目": question, "岗位": role_code, "知识域": domain}, keyword=topic["label"], extra_metadata={"category": domain, "subcategory": topic["slug"]}))
            seq += 1
    return records


def generate_competency_docs(role_code: str) -> list[dict]:
    role_name = ROLE_SPECS[role_code]["display_name"]
    competencies = ROLE_SPECS[role_code]["competencies"]
    records: list[dict] = []
    mains = [("level", "junior", "初级能力模型"), ("level", "mid", "中级能力模型"), ("rubric_support", "dimensions", "岗位考察维度说明"), ("qualified_signals", "qualified", "常见达标表现说明"), ("qualified_signals", "underqualified", "常见不达标表现说明"), ("rubric_support", "rubric", "典型面试评价维度说明")]
    for seq, (subdir, level, title) in enumerate(mains, start=1):
        doc_id = f"competency_{role_code}_main_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "competency_model" / subdir / f"{doc_id}.md"
        sections = [("summary", f"{role_name} 在 {title} 场景里，更关注候选人是否能把知识、工程判断、项目证据和结果闭环说清楚。"), ("signals", [f"能围绕 {name} 给出机制解释、场景取舍和可验证结果" for name in list(competencies.values())[:4]]), ("interview_focus", ["定义是否准确", "取舍是否自洽", "是否有真实项目证据", "是否能解释风险与边界"]), ("usage", "这些文档主要用于面试评分、简历评分和成长建议的解释层。")]
        meta = {"id": doc_id, "doc_type": "competency", "role": role_code, "category": "competency_model", "subcategory": subdir, "level": level, "tags": [role_code, "competency_model", subdir], "applicable_features": ["interview", "resume_review", "growth", "recommendation"]}
        write_text(path, render_markdown(meta, title, sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="competency", source_type="competency_model", topic=subdir, difficulty=level, title=title, source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "能力层级": level, "文档": title}, keyword=title))
    dimensions = ["基础概念准确性", "原理解释能力", "方案取舍表达", "复杂度意识", "稳定性意识", "性能分析能力", "异常处理策略", "数据结构选择", "协议与接口边界", "可观测性意识", "工程化思维", "测试与验证能力", "线上排障方法", "项目职责清晰度", "量化结果表达", "协作与推动能力", "风险识别能力", "学习迭代能力", "业务理解与价值表达"]
    seq = 1
    for level in ("junior", "mid"):
        for label in dimensions:
            doc_id = f"cap_{role_code}_{seq:03d}"
            path = DATA_DIR / "content_source" / "roles" / role_code / "competency_model" / "dimensions" / f"{doc_id}.md"
            sections = [("dimension", f"{label} 是 {role_name} {level} 候选人面试里非常高频的一条能力维度。"), ("qualified_signals", ["能先给结论，再补机制和边界", "能结合真实项目说明收益和代价", "能给出验证方式而不是停留在猜测"]), ("unqualified_signals", ["只会背结论，没有过程", "项目事实和技术动作对不上", "无法解释为什么这样做"]), ("scoring_hint", "评分时重点看事实密度、因果链路、风险意识和是否体现岗位相关性。")]
            meta = {"id": doc_id, "doc_type": "competency", "role": role_code, "category": "competency_dimension", "subcategory": label, "level": level, "tags": [role_code, "competency_dimension", level], "applicable_features": ["interview", "resume_review", "growth"]}
            write_text(path, render_markdown(meta, f"{label}（{level}）", sections))
            records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="competency", source_type="competency_dimension", topic=label, difficulty=level, title=f"{label}（{level}）", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "能力维度": label, "层级": level}, keyword=label))
            seq += 1
    return records


def generate_resume_docs(role_code: str) -> list[dict]:
    role_name = ROLE_SPECS[role_code]["display_name"]
    scenarios = RESUME_SCENARIOS[role_code]
    records: list[dict] = []
    profiles = [("excellent", "优秀简历片段", "职责清晰、技术动作明确、结果量化、岗位相关性强。"), ("average", "一般简历片段", "能看出经历，但结果和贡献边界不够清楚。"), ("weak", "较差简历片段", "关键词堆砌或职责模糊，缺少证据和结果。")]
    seq = 1
    for quality, title_prefix, summary in profiles:
        for scenario in scenarios:
            doc_id = f"resume_case_{role_code}_{quality}_{seq:03d}"
            path = DATA_DIR / "content_source" / "roles" / role_code / "resume_review" / "resume_snippets" / f"{doc_id}.md"
            excerpt = {"excellent": f"主导 {scenario}，明确负责模块、方案取舍和指标闭环，结果可被数据验证。", "average": f"参与 {scenario} 开发与优化，做过一些改造，但职责和结果说明不够具体。", "weak": f"参与过 {scenario}，熟悉相关技术栈，了解业务流程。"}[quality]
            sections = [("original_resume_excerpt", excerpt), ("strengths", [summary, "岗位相关性明确" if quality != "weak" else "至少出现了岗位关键词"]), ("issues", ["需要明确你本人负责的模块", "建议补充量化结果和验证方式"]), ("rewrite_suggestion", f"把 {scenario} 描述改成“职责-动作-结果-验证”的结构。"), ("reviewer_comments", f"{title_prefix} 主要用于 {role_name} 简历评分的对照样本。")]
            meta = {"id": doc_id, "doc_type": "resume", "role": role_code, "level": "junior_to_mid", "case_type": f"{quality}_snippet", "tags": [role_code, "resume", quality], "applicable_features": ["resume_review", "jd_match"]}
            write_text(path, render_markdown(meta, f"{title_prefix}：{scenario}", sections))
            records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="resume", source_type="resume_snippet", topic=f"snippet_{seq:03d}", difficulty="junior_to_mid", title=f"{title_prefix}：{scenario}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "案例类型": f"{quality}_snippet"}, keyword=scenario, extra_metadata={"case_type": f"{quality}_snippet"}))
            seq += 1
    for seq in range(1, 31):
        scenario = scenarios[(seq - 1) % len(scenarios)]
        doc_id = f"rewrite_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "resume_review" / "project_rewrite" / f"{doc_id}.md"
        sections = [("original_resume_excerpt", f"负责 {scenario} 开发，完成需求迭代和联调。"), ("strengths", ["说明了项目场景", "有一定岗位相关性"]), ("issues", ["没有职责边界", "没有技术动作", "没有结果和验证"]), ("rewrite_suggestion", f"建议改写为：围绕 {scenario} 的关键瓶颈提出方案，说明动作、指标和复盘。"), ("reviewer_comments", "项目改写案例主要用于演示系统如何把空泛表述改成更可信的工程表达。")]
        meta = {"id": doc_id, "doc_type": "resume", "role": role_code, "level": "junior_to_mid", "case_type": "project_rewrite", "tags": [role_code, "resume", "project_rewrite"], "applicable_features": ["resume_review", "rewrite"]}
        write_text(path, render_markdown(meta, f"项目改写案例：{scenario}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="resume", source_type="project_rewrite", topic=f"rewrite_{seq:03d}", difficulty="junior_to_mid", title=f"项目改写案例：{scenario}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "案例类型": "project_rewrite"}, keyword=scenario, extra_metadata={"case_type": "project_rewrite"}))
    for seq, issue in enumerate(COMMON_DEDUCTIONS, start=1):
        doc_id = f"deduction_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "resume_review" / "deductions" / f"{doc_id}.md"
        sections = [("diagnosis", issue), ("impact", f"这类问题会降低 {role_name} 简历的可信度、岗位匹配度或成长潜力判断。"), ("fix", "优先补齐职责边界、技术动作、结果指标和验证方式。"), ("reviewer_comments", "扣分项文档主要用于解释为什么系统给出低分。")]
        meta = {"id": doc_id, "doc_type": "resume", "role": role_code, "level": "mixed", "case_type": "deduction", "tags": [role_code, "resume", "deduction"], "applicable_features": ["resume_review"]}
        write_text(path, render_markdown(meta, f"常见扣分项：{issue}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="resume", source_type="resume_deduction", topic=f"deduction_{seq:03d}", difficulty="mixed", title=f"常见扣分项：{issue}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "案例类型": "deduction"}, keyword=issue, extra_metadata={"case_type": "deduction"}))
    tones = ["鼓励式反馈", "直接式反馈", "结构化反馈", "项目导向反馈", "能力导向反馈", "结果导向反馈", "岗位匹配反馈", "成长建议反馈", "指标补充反馈", "可信度反馈", "表达优化反馈", "工程化反馈", "性能优化反馈", "稳定性反馈", "架构反馈", "简历重写反馈", "项目深挖反馈", "补充证据反馈", "优先级建议反馈", "下一步行动反馈"]
    for seq, tone in enumerate(tones, start=1):
        doc_id = f"feedback_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "resume_review" / "feedback_templates" / f"{doc_id}.md"
        sections = [("template", f"{tone}：先肯定真实经验，再指出缺口，最后给出一条可执行修改建议。"), ("when_to_use", "适用于简历评分结果需要解释和安抚，同时推动候选人继续优化的场景。"), ("example", f"你在 {role_name} 方向上已经有一定项目素材，但当前最影响说服力的是职责边界和结果量化，建议优先补这一层。")]
        meta = {"id": doc_id, "doc_type": "resume", "role": role_code, "level": "mixed", "case_type": "feedback_template", "tags": [role_code, "resume", "feedback_template"], "applicable_features": ["resume_review", "report"]}
        write_text(path, render_markdown(meta, f"反馈模板：{tone}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="resume", source_type="feedback_template", topic=f"feedback_{seq:03d}", difficulty="mixed", title=f"反馈模板：{tone}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "案例类型": "feedback_template"}, keyword=tone, extra_metadata={"case_type": "feedback_template"}))
    for seq, company in enumerate(COMPANY_STYLES, start=1):
        doc_id = f"jd_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "resume_review" / "jd_digest" / f"{doc_id}.md"
        sections = [("position_summary", f"{company} 更关注 {role_name} 候选人的岗位相关经验、问题复杂度和实际产出。"), ("must_have", ["能解释核心技术原理", "有真实项目经验", "能说明结果与验证方式"]), ("bonus", ["有性能或稳定性优化案例", "能做取舍说明", "有复盘与治理意识"]), ("risk_signals", ["项目职责不清", "没有量化结果", "只堆技术关键词"])]
        meta = {"id": doc_id, "doc_type": "resume", "role": role_code, "level": "mixed", "case_type": "jd_digest", "tags": [role_code, "resume", "jd_digest"], "applicable_features": ["resume_review", "jd_match"]}
        write_text(path, render_markdown(meta, f"JD 摘要：{company}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="resume", source_type="jd_digest", topic=f"jd_{seq:03d}", difficulty="mixed", title=f"JD 摘要：{company}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "案例类型": "jd_digest"}, keyword=company, extra_metadata={"case_type": "jd_digest"}))
    return records


def generate_growth_docs(role_code: str) -> list[dict]:
    role_name = ROLE_SPECS[role_code]["display_name"]
    records: list[dict] = []
    for seq, track in enumerate(LEARNING_TRACKS[role_code], start=1):
        doc_id = f"path_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "growth" / "learning_paths" / f"{doc_id}.md"
        sections = [("diagnosis", f"{track} 适合用来补齐 {role_name} 候选人的基础链路，让知识点形成可检索、可复盘的体系。"), ("improvement_advice", "按“概念-原理-场景-项目证据”的顺序学习，每个阶段都要配专项题和复盘。"), ("recommended_practice", "每周完成 5 道专项题、1 次知识搜索总结、1 次结构化口述复盘。"), ("expected_outcome", "能从背概念过渡到讲机制、讲边界和讲项目证据。")]
        meta = {"id": doc_id, "doc_type": "growth", "role": role_code, "target_level": "junior_to_mid", "weakness_type": "learning_path", "tags": [role_code, "growth", "learning_path"], "applicable_features": ["growth", "recommendation", "report"]}
        write_text(path, render_markdown(meta, f"学习路线：{track}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="growth", source_type="learning_path", topic=f"path_{seq:03d}", difficulty="junior_to_mid", title=f"学习路线：{track}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "成长类型": "learning_path"}, keyword=track))
    for seq, weakness in enumerate(COMMON_WEAKNESSES, start=1):
        for source_type, prefix, subdir in (("weakness_fix", "薄弱项补强", "weakness_fixes"), ("error_correction", "常见错误纠偏", "error_corrections")):
            doc_id = f"{'weakfix' if source_type == 'weakness_fix' else 'correct'}_{role_code}_{seq:03d}"
            path = DATA_DIR / "content_source" / "roles" / role_code / "growth" / subdir / f"{doc_id}.md"
            sections = [("diagnosis", f"你在 {role_name} 面试或练习里经常表现出“{weakness}”这个问题。"), ("improvement_advice", "回答时固定加上结论、原因、做法、结果四段；如果是项目题，再补职责边界和验证方式。"), ("recommended_practice", "连续完成 3 道对应专项题，每题都做 1 次录音复盘，并记录改进前后的差异。"), ("expected_outcome", "回答会更完整、更有证据，也更容易体现岗位匹配度。")]
            meta = {"id": doc_id, "doc_type": "growth", "role": role_code, "target_level": "junior_to_mid", "weakness_type": weakness, "tags": [role_code, "growth", source_type], "applicable_features": ["growth", "recommendation", "report"]}
            write_text(path, render_markdown(meta, f"{prefix}：{weakness}", sections))
            records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="growth", source_type=source_type, topic=f"{source_type}_{seq:03d}", difficulty="junior_to_mid", title=f"{prefix}：{weakness}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "成长类型": source_type}, keyword=weakness))
    for seq, track in enumerate(LEVEL_UP_TRACKS[role_code], start=1):
        doc_id = f"levelup_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "growth" / "level_up_paths" / f"{doc_id}.md"
        sections = [("diagnosis", f"{track} 是很多 {role_name} 候选人从初级走向中级时的关键跃迁。"), ("improvement_advice", "每个阶段都要补机制、补取舍、补项目证据，不能只扩技术栈广度。"), ("recommended_practice", "为该阶段设计 2 周专项计划，完成题目训练、知识整理和项目复盘。"), ("expected_outcome", "回答会从执行层升级为工程判断层。")]
        meta = {"id": doc_id, "doc_type": "growth", "role": role_code, "target_level": "junior_to_mid", "weakness_type": "level_up_path", "tags": [role_code, "growth", "level_up_path"], "applicable_features": ["growth", "recommendation", "report"]}
        write_text(path, render_markdown(meta, f"进阶路径：{track}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="growth", source_type="level_up_path", topic=f"levelup_{seq:03d}", difficulty="junior_to_mid", title=f"进阶路径：{track}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "成长类型": "level_up_path"}, keyword=track))
    for seq in range(1, 31):
        weakness = COMMON_WEAKNESSES[(seq - 1) % len(COMMON_WEAKNESSES)]
        doc_id = f"reason_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "roles" / role_code / "growth" / "recommendation_reasons" / f"{doc_id}.md"
        sections = [("diagnosis", f"如果系统判断你当前最值得优先训练的是“{weakness}”，通常意味着这条短板在最近几次表现里重复出现。"), ("improvement_advice", "推荐题目时要优先覆盖高频短板，再逐步回补相关原理和项目表达。"), ("recommended_practice", "先做 2 道基础题、1 道场景题、1 次复盘，形成“知识点-场景-表达”闭环。"), ("expected_outcome", "让推荐结果看起来更个性化，也更符合成长路径。")]
        meta = {"id": doc_id, "doc_type": "growth", "role": role_code, "target_level": "junior_to_mid", "weakness_type": "recommendation_reason", "tags": [role_code, "growth", "recommendation_reason"], "applicable_features": ["growth", "recommendation", "report"]}
        write_text(path, render_markdown(meta, f"推荐理由模板 {seq:02d}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="growth", source_type="recommendation_reason", topic=f"reason_{seq:03d}", difficulty="junior_to_mid", title=f"推荐理由模板 {seq:02d}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "成长类型": "recommendation_reason"}, keyword=weakness))
    return records


def generate_personalization_docs(role_code: str) -> list[dict]:
    patterns = ["基础薄弱型", "原理不稳型", "项目空泛型", "排障链路弱型", "指标缺失型", "表达分散型", "取舍意识弱型", "稳定性薄弱型", "性能归因弱型", "协作推动弱型", "简历可信度弱型", "成长节奏失衡型"]
    records: list[dict] = []
    for seq, pattern in enumerate(patterns, start=1):
        doc_id = f"persona_template_{role_code}_{seq:03d}"
        path = DATA_DIR / "content_source" / "personalization" / "user_summary_templates" / f"{doc_id}.md"
        sections = [("diagnosis", f"{pattern} 候选人通常不是不会做，而是知识、表达和证据没有形成闭环。"), ("improvement_advice", "摘要生成时要强调最近高频短板、对应专项题和一条可执行建议。"), ("recommended_practice", "推荐顺序应是：基础题 -> 场景题 -> 项目题 -> 复盘建议。"), ("expected_outcome", "让个性化推荐更像真实产品，而不是固定话术。")]
        meta = {"id": doc_id, "doc_type": "growth", "role": role_code, "target_level": "junior_to_mid", "weakness_type": "persona_template", "tags": [role_code, "growth", "persona_template"], "applicable_features": ["growth", "recommendation"]}
        write_text(path, render_markdown(meta, f"个性化摘要模板：{pattern}", sections))
        records.append(build_record(doc_id=doc_id, role_code=role_code, doc_type="growth", source_type="personalization_template", topic=f"persona_{seq:03d}", difficulty="junior_to_mid", title=f"个性化摘要模板：{pattern}", source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": role_code, "成长类型": "persona_template"}, keyword=pattern))
    return records


def generate_common_docs() -> list[dict]:
    records: list[dict] = []
    groups = {"scoring": ["评分解释结构", "高分回答特征", "中分回答特征", "低分回答特征", "证据链使用原则", "评分建议写法"], "follow_up": ["追问加深策略", "追问回收策略", "可信度追问策略", "项目深挖策略", "换题判定策略", "追问措辞规范"], "writing_guidelines": ["简历反馈写作规范", "成长建议写作规范", "面试总结写作规范", "知识回答写作规范", "项目复盘写作规范", "推荐理由写作规范"]}
    seq = 1
    for subdir, titles in groups.items():
        for title in titles:
            doc_id = f"common_{subdir}_{seq:03d}"
            path = DATA_DIR / "content_source" / "common" / subdir / f"{doc_id}.md"
            sections = [("summary", f"{title} 主要用于统一系统输出的口径，让评分、追问和建议更稳定。"), ("key_points", ["先给判断，再给理由", "避免空泛赞美，强调可执行建议", "尽量引用事实、指标或答题行为"]), ("usage", "这些文档作为通用评分/追问/写作规范进入向量知识库，供多个功能共享。")]
            meta = {"id": doc_id, "doc_type": "scoring", "role": "common", "category": "common", "subcategory": subdir, "difficulty": "mixed", "tags": ["common", "scoring", subdir], "applicable_features": ["interview", "resume_review", "growth", "report"]}
            write_text(path, render_markdown(meta, title, sections))
            records.append(build_record(doc_id=doc_id, role_code="common", doc_type="scoring", source_type="scoring", topic=subdir, difficulty="mixed", title=title, source_path=rel(path), tags=meta["tags"], sections=sections, parsed_meta={"岗位": "common", "文档": title}, keyword=title))
            seq += 1
    return records


def generate_metadata_and_schemas() -> None:
    write_json(DATA_DIR / "metadata" / "taxonomies" / "roles.json", {"roles": [{"code": code, "name": spec["display_name"], "competencies": spec["competencies"]} for code, spec in ROLE_SPECS.items()]})
    write_json(DATA_DIR / "metadata" / "tag_dictionary" / "tags.json", {"core_tags": ["question", "knowledge", "resume", "growth", "competency", "scoring", "cpp_backend", "web_frontend", "common"]})
    write_json(DATA_DIR / "metadata" / "difficulty_rules" / "rules.json", {"question": {"easy": "单点概念清晰即可", "medium": "需要机制或场景说明", "hard": "需要 trade-off、证据链或设计能力"}, "knowledge": {"beginner": "定义和基本边界", "intermediate": "机制与应用", "advanced": "复杂场景与误区"}})
    write_json(
        DATA_DIR / "metadata" / "retrieval_profiles" / "default.json",
        {
            "default": {
                "top_k": 6,
                "allowed_doc_types": ["question", "knowledge", "competency", "scoring"],
                "question_filters": ["role_code", "category", "difficulty"],
                "resume_filters": ["role_code", "case_type"],
                "growth_filters": ["role_code", "weakness_type"],
            },
            "question_generation": {
                "top_k": 6,
                "search_multiplier": 8,
                "lexical_candidate_limit": 24,
                "allowed_doc_types": ["question", "knowledge", "competency"],
                "doc_type_boost": {"question": 3, "knowledge": 2, "competency": 1},
            },
            "answer_analysis": {
                "top_k": 6,
                "search_multiplier": 4,
                "lexical_candidate_limit": 12,
                "allowed_doc_types": ["knowledge", "competency"],
                "doc_type_boost": {"knowledge": 3, "competency": 2},
            },
            "answer_scoring": {
                "top_k": 6,
                "search_multiplier": 4,
                "lexical_candidate_limit": 12,
                "allowed_doc_types": ["knowledge", "competency", "scoring"],
                "doc_type_boost": {"scoring": 3, "competency": 2, "knowledge": 1},
            },
        },
    )
    base_schema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["id", "title", "role"], "properties": {"id": {"type": "string"}, "title": {"type": "string"}, "role": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}}}
    write_json(DATA_DIR / "schemas" / "interview_question.schema.json", {**base_schema, "required": ["id", "title", "role", "category", "difficulty", "question"]})
    write_json(DATA_DIR / "schemas" / "faq.schema.json", {**base_schema, "required": ["id", "title", "role", "category", "question", "answer"]})
    write_json(DATA_DIR / "schemas" / "competency_item.schema.json", {**base_schema, "required": ["id", "title", "role", "level"]})
    write_json(DATA_DIR / "schemas" / "resume_case.schema.json", {**base_schema, "required": ["id", "title", "role", "case_type"]})
    write_json(DATA_DIR / "schemas" / "growth_advice.schema.json", {**base_schema, "required": ["id", "title", "role", "weakness_type"]})
    write_json(DATA_DIR / "schemas" / "demo_record.schema.json", {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "required": ["user_id", "role_code"]})


def generate_demo_data() -> None:
    users = [{"email": "admin@example.com", "username": "admin", "full_name": "演示管理员", "password": "Admin123!", "role": "admin"}]
    role_cycle = ["web_frontend", "cpp_backend"] * 6
    for index, name in enumerate(PERSONA_NAMES, start=1):
        role_code = role_cycle[index - 1]
        username = "demo" if index == 1 else f"user{index:02d}"
        users.append({"email": f"{username}@example.com", "username": username, "full_name": name, "password": "Demo123!" if index == 1 else f"Demo{index:02d}Pass!", "role": "user", "preferred_role": role_code, "target_level": "junior_to_mid"})
        write_json(DATA_DIR / "demo" / "users" / "personas" / f"user_{index:03d}_{role_code}.json", {"user_id": f"user_{index:03d}", "username": username, "display_name": name, "role_code": role_code, "target_level": "junior_to_mid", "focuses": [COMMON_WEAKNESSES[index % len(COMMON_WEAKNESSES)], COMMON_WEAKNESSES[(index + 5) % len(COMMON_WEAKNESSES)]], "summary": f"{name} 是用于演示的 {ROLE_SPECS[role_code]['display_name']} 候选人画像。"})
        for version in (1, 2):
            write_text(DATA_DIR / "demo" / "resumes" / "raw_versions" / f"resume_user_{index:03d}_v{version}.md", f"# {name} 的简历版本 V{version}\n\n- 岗位方向：{ROLE_SPECS[role_code]['display_name']}\n- 目标级别：初中级\n- 项目亮点：版本 {version} 补充了职责边界和量化结果。\n")
            write_json(DATA_DIR / "demo" / "resumes" / "parsed_profiles" / f"resume_user_{index:03d}_v{version}.json", {"user_id": f"user_{index:03d}", "role_code": role_code, "version": version, "highlights": ["增加了职责边界说明", "增加了结果指标"], "risk_points": [COMMON_DEDUCTIONS[(index + version) % len(COMMON_DEDUCTIONS)]]})
        write_json(DATA_DIR / "demo" / "practice" / "recommendation_inputs" / f"recommend_user_{index:03d}.json", {"user_id": f"user_{index:03d}", "role_code": role_code, "recent_weaknesses": [COMMON_WEAKNESSES[(index + j) % len(COMMON_WEAKNESSES)] for j in range(3)]})
        for attempt in range(1, 21):
            write_json(DATA_DIR / "demo" / "practice" / "answer_logs" / f"practice_user_{index:03d}_{attempt:03d}.json", {"user_id": f"user_{index:03d}", "role_code": role_code, "attempt_no": attempt, "question_ref": f"q_{role_code}_foundation_{((attempt - 1) % 20) + 1:03d}", "score": 58 + ((index + attempt) % 35), "weakness_tag": COMMON_WEAKNESSES[(index + attempt) % len(COMMON_WEAKNESSES)], "created_at": (TODAY - timedelta(days=attempt)).isoformat()})
        for interview_no in range(1, 6):
            payload = {"user_id": f"user_{index:03d}", "role_code": role_code, "session_no": interview_no, "created_at": (TODAY - timedelta(days=interview_no * 3)).isoformat(), "total_score": 60 + ((index * 7 + interview_no * 5) % 28), "weaknesses": [COMMON_WEAKNESSES[(index + interview_no + j) % len(COMMON_WEAKNESSES)] for j in range(2)], "summary": "用于演示成长记录和报告详情的面试归档。"}
            write_json(DATA_DIR / "demo" / "interviews" / "session_archives" / f"interview_user_{index:03d}_{interview_no:03d}.json", payload)
            write_json(DATA_DIR / "demo" / "interviews" / "report_snapshots" / f"report_user_{index:03d}_{interview_no:03d}.json", {**payload, "report_ready": True})
        for snapshot_no in range(1, 11):
            write_json(DATA_DIR / "demo" / "growth" / "snapshots" / f"growth_user_{index:03d}_{snapshot_no:03d}.json", {"user_id": f"user_{index:03d}", "role_code": role_code, "snapshot_no": snapshot_no, "focus": COMMON_WEAKNESSES[(index + snapshot_no) % len(COMMON_WEAKNESSES)], "recommendation": "下一步优先做专项题并补指标与项目证据。", "created_at": (TODAY - timedelta(days=snapshot_no * 2)).isoformat()})
        for phase in range(1, 4):
            write_text(DATA_DIR / "demo" / "growth" / "rag_summaries" / f"growth_summary_user_{index:03d}_{phase}.md", f"# 用户成长摘要 {phase}\n\n- 用户：{name}\n- 岗位：{ROLE_SPECS[role_code]['display_name']}\n- 阶段重点：{COMMON_WEAKNESSES[(index + phase) % len(COMMON_WEAKNESSES)]}\n- 最近建议：优先补专项题，再回到项目表达和指标说明。\n")
    write_json(DATA_DIR / "demo" / "users" / "users.json", users)
    write_json(DATA_DIR / "demo" / "users.json", users)


def write_question_seeds(seed_payloads: dict[str, dict]) -> None:
    seed_dir = DATA_DIR / "content_source" / "question_seeds"
    seed_dir.mkdir(parents=True, exist_ok=True)
    for role_code, payload in seed_payloads.items():
        write_json(seed_dir / f"{role_code}.json", payload)


def write_rag_outputs(records: list[dict]) -> None:
    runtime_dir = DATA_DIR / "runtime_corpus"
    artifacts_dir = DATA_DIR / "build_artifacts"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    def write_jsonl(path: Path, items: list[dict]) -> None:
        ensure_parent(path)
        with path.open("w", encoding="utf-8") as handle:
            for item in items:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    write_jsonl(runtime_dir / "records.jsonl", records)

    role_counter = Counter(item["role_code"] for item in records)
    doc_counter = Counter(item["doc_type"] for item in records)

    write_json(
        runtime_dir / "manifest.json",
        {
            "dataset": "demo_rag_v2",
            "source_root": "data/content_source",
            "output_root": "data/runtime_corpus",
            "record_count": len(records),
            "roles": dict(role_counter),
            "doc_types": dict(doc_counter),
            "generated_at": TODAY.isoformat(),
            "source_note": "data/runtime_corpus/records.jsonl is the only canonical runtime input; edit data/content_source/ and rerun this script.",
        },
    )
    write_json(
        artifacts_dir / "build_report.json",
        {"generated_at": TODAY.isoformat(), "record_count": len(records), **dict(doc_counter)},
    )

    snapshot_path = artifacts_dir / "kb_chunks.jsonl"
    ensure_parent(snapshot_path)
    with snapshot_path.open("w", encoding="utf-8") as handle:
        for item in records:
            snapshot = {
                "id": item["id"],
                "role_code": item["role_code"],
                "doc_type": item["doc_type"],
                "competency_code": item["source_type"] if item["doc_type"] == "question" else item["topic"],
                "title": item["title"],
                "section": "1",
                "source_path": item["source_path"],
                "snippet": item["embedding_text"][:3900],
                "embedding": None,
            }
            handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for the split seed/build data pipeline.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate the demo content_source/metadata/schemas seed before rebuilding runtime artifacts.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether runtime/build artifacts are up to date without writing files.",
    )
    args = parser.parse_args()

    commands: list[list[str]] = []
    if not args.check:
        seed_command = [sys.executable, str(ROOT / "scripts" / "seed_demo_content_source.py")]
        if args.force:
            seed_command.append("--force")
        commands.append(seed_command)
    build_command = [sys.executable, str(ROOT / "scripts" / "build_runtime_corpus.py")]
    if args.check:
        build_command.append("--check")
    commands.append(build_command)

    for command in commands:
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode != 0:
            raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()

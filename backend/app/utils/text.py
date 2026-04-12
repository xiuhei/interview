import re
from pathlib import Path

from docx import Document
from pypdf import PdfReader


STAR_SECTIONS = [
    ("situation", ["situation", "背景", "场景"]),
    ("task", ["task", "任务", "目标"]),
    ("action", ["action", "行动", "做法", "负责", "优化", "设计"]),
    ("result", ["result", "结果", "指标", "收益", "效果"]),
]
KEYWORD_STOPWORDS = {
    "请介绍",
    "请讲讲",
    "可以",
    "一下",
    "这个",
    "那个",
    "以及",
    "如何",
    "什么",
    "为什么",
    "你会",
    "我们",
    "你们",
    "然后",
    "因为",
    "所以",
    "标题",
    "岗位",
    "文档类型",
    "主题",
    "难度",
    "question",
    "answer",
    "reference_answer",
    "knowledge",
    "medium",
    "simple",
    "hard",
}
CJK_KEYWORD_SPLIT_PHRASES = (
    "请你",
    "请",
    "介绍一下",
    "介绍",
    "讲讲",
    "重点说明",
    "重点讲清楚",
    "重点讲",
    "重点说说",
    "重点",
    "比如",
    "例如",
    "当时遇到的",
    "当时遇到",
    "主要解决什么问题",
    "主要解决",
    "并说明",
    "并说明它",
    "并说说",
    "并说",
    "可以从",
    "可以",
    "一个",
    "一次",
    "你",
    "我",
    "你的",
    "我的",
    "请解释",
    "请对比",
)
CJK_KEYWORD_SPLIT_RE = re.compile(r"[的了在是把将对从用按向里中上下吗吧呢啊呀哦题]")


def clean_text(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def strip_rtf(text: str) -> str:
    without_controls = re.sub(r"\\[a-z]+-?\d* ?", " ", text)
    without_braces = re.sub(r"[{}]", " ", without_controls)
    decoded_hex = re.sub(r"\\'[0-9a-fA-F]{2}", " ", without_braces)
    return clean_text(decoded_hex)


def read_resume_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return clean_text("\n".join(page.extract_text() or "" for page in reader.pages))
    if suffix == ".docx":
        doc = Document(str(path))
        return clean_text("\n".join(paragraph.text for paragraph in doc.paragraphs))
    if suffix == ".rtf":
        return strip_rtf(path.read_text(encoding="utf-8", errors="ignore"))
    return clean_text(path.read_text(encoding="utf-8", errors="ignore"))


def star_score(text: str) -> int:
    lowered = text.lower()
    hit = 0
    for _, aliases in STAR_SECTIONS:
        if any(alias in text or alias in lowered for alias in aliases):
            hit += 1
    return min(100, hit * 25)


def sentence_count(text: str) -> int:
    return len([item for item in re.split(r"[。！？!?\n]", text) if item.strip()])


def _split_cjk_keywords(token: str) -> list[str]:
    normalized = token
    for phrase in CJK_KEYWORD_SPLIT_PHRASES:
        normalized = normalized.replace(phrase, " ")
    normalized = CJK_KEYWORD_SPLIT_RE.sub(" ", normalized)
    pieces = [item.strip() for item in normalized.split() if item.strip()]
    keywords: list[str] = []
    for piece in pieces:
        if piece in KEYWORD_STOPWORDS:
            continue
        if 2 <= len(piece) <= 8:
            keywords.append(piece)
            continue
        for size in (4, 3, 2):
            for index in range(0, len(piece) - size + 1):
                candidate = piece[index : index + size]
                if candidate not in KEYWORD_STOPWORDS:
                    keywords.append(candidate)
    return list(dict.fromkeys(keywords))


def extract_keywords(text: str) -> list[str]:
    normalized = clean_text(text.lower())
    tokens = re.findall(r"[a-zA-Z0-9_+#.-]+|[\u4e00-\u9fff]{2,}", normalized)
    keywords: list[str] = []
    for token in tokens:
        if re.fullmatch(r"[a-zA-Z0-9_+#.-]+", token):
            if len(token) < 2 or token in KEYWORD_STOPWORDS:
                continue
            keywords.append(token)
            continue
        keywords.extend(_split_cjk_keywords(token))
    return keywords


def keyword_hits(text: str, keywords: list[str]) -> int:
    lowered = clean_text(text.lower())
    return sum(1 for keyword in dict.fromkeys(keywords) if keyword and keyword.lower() in lowered)

const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
        WidthType, ShadingType, PageNumber, PageBreak, LevelFormat } = require("docx");

const DIAG = path.join(__dirname, "diagrams");
const F = "Microsoft YaHei";

// ===== Helpers =====
const bd = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const bds = { top: bd, bottom: bd, left: bd, right: bd };
const cm = { top: 60, bottom: 60, left: 100, right: 100 };

function hC(t, w) {
  return new TableCell({ borders: bds, width: { size: w, type: WidthType.DXA },
    shading: { fill: "2B579A", type: ShadingType.CLEAR }, margins: cm, verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0 },
      children: [new TextRun({ text: t, bold: true, font: F, size: 20, color: "FFFFFF" })] })] });
}
function tC(t, w, o = {}) {
  return new TableCell({ borders: bds, width: { size: w, type: WidthType.DXA }, margins: cm,
    shading: o.sh ? { fill: o.sh, type: ShadingType.CLEAR } : undefined, verticalAlign: "center",
    children: [new Paragraph({ alignment: o.ct ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ text: t, font: F, size: 20, bold: !!o.b })] })] });
}

function h1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text: t, bold: true, font: F, size: 32 })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 300, after: 160 }, children: [new TextRun({ text: t, bold: true, font: F, size: 28 })] }); }
function h3(t) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, bold: true, font: F, size: 24 })] }); }
function p(text, o = {}) {
  const runs = [];
  if (o.label) runs.push(new TextRun({ text: o.label, font: F, size: 21, bold: true }));
  runs.push(new TextRun({ text, font: F, size: 21, ...(o.bold ? { bold: true } : {}), ...(o.color ? { color: o.color } : {}) }));
  return new Paragraph({ spacing: { before: 80, after: 80, line: 360 },
    indent: o.noIndent ? undefined : { firstLine: 420 }, children: runs });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 },
    spacing: { before: 30, after: 30, line: 340 },
    children: [new TextRun({ text, font: F, size: 21 })] });
}
function num(text) {
  return new Paragraph({ numbering: { reference: "numbers", level: 0 },
    spacing: { before: 50, after: 50, line: 360 },
    children: [new TextRun({ text, font: F, size: 21 })] });
}
function img(filename, w, h) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 80 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(path.join(DIAG, filename)),
      transformation: { width: w, height: h },
      altText: { title: filename, description: filename, name: filename } })] });
}
function cap(text) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40, after: 160 },
    children: [new TextRun({ text, font: F, size: 18, color: "666666", italics: true })] });
}
function gap() { return new Paragraph({ spacing: { before: 40, after: 40 } }); }

const TW = 9386; // page content width

// ===== Tables =====
function mkTable(cols, rows) {
  const cw = cols.map(c => c[1]);
  return new Table({
    width: { size: TW, type: WidthType.DXA }, columnWidths: cw,
    rows: [
      new TableRow({ children: cols.map(([t, w]) => hC(t, w)) }),
      ...rows.map(cells => new TableRow({
        children: cells.map((cell, i) => {
          if (typeof cell === "string") return tC(cell, cw[i]);
          return tC(cell.t, cw[i], cell);
        })
      }))
    ]
  });
}

// Tech stack table
const techTable = mkTable(
  [["\u5C42\u6B21", 1800], ["\u6280\u672F\u9009\u578B", 2600], ["\u8BF4\u660E", 4986]],
  [
    [{ t: "\u524D\u7AEF", ct: true, sh: "F0F4F8" }, { t: "Vue 3 + TypeScript + Vite", b: true }, "Element Plus UI\u7EC4\u4EF6\u5E93\uFF0CPinia\u72B6\u6001\u7BA1\u7406\uFF0CECharts\u56FE\u8868\uFF0CAxios HTTP"],
    [{ t: "\u540E\u7AEF", ct: true, sh: "F0F4F8" }, { t: "FastAPI (Python 3.12)", b: true }, "SQLAlchemy 2.0 ORM + Alembic\u8FC1\u79FB\uFF0Cuvicorn ASGI\u670D\u52A1\u5668"],
    [{ t: "\u6570\u636E\u5E93", ct: true, sh: "F0F4F8" }, { t: "MySQL 8.4", b: true }, "\u4E1A\u52A1\u6570\u636E\u6301\u4E45\u5316\uFF0C\u901A\u8FC7pymysql\u9A71\u52A8\u8FDE\u63A5"],
    [{ t: "\u7F13\u5B58", ct: true, sh: "F0F4F8" }, { t: "Redis 7.4", b: true }, "\u4F1A\u8BDD\u7F13\u5B58\u3001\u70ED\u70B9\u6570\u636E\u7F13\u5B58"],
    [{ t: "\u5411\u91CF\u6570\u636E\u5E93", ct: true, sh: "F0F4F8" }, { t: "Milvus 2.5.4", b: true }, "RAG\u77E5\u8BC6\u5E93\u5411\u91CF\u68C0\u7D22\uFF0C\u4F59\u5F26\u76F8\u4F3C\u5EA6\u641C\u7D22\uFF0C\u52A8\u6001Schema"],
    [{ t: "LLM\u670D\u52A1", ct: true, sh: "F0F4F8" }, { t: "\u901A\u4E49\u5343\u95EE Qwen", b: true }, "OpenAI\u517C\u5BB9API\u8C03\u7528\uFF0C\u652F\u6301JSON\u7ED3\u6784\u5316\u8F93\u51FA\uFF0Chttpx\u5F02\u6B65\u5BA2\u6237\u7AEF"],
    [{ t: "\u5D4C\u5165\u5411\u91CF", ct: true, sh: "F0F4F8" }, { t: "Qwen text-embedding-v3", b: true }, "\u6587\u6863\u5206\u5757\u5D4C\u5165\uFF0C128\u7EF4\u5411\u91CF\uFF0C\u6279\u91CF\u5904\u7406\uFF08\u6BCF\u62510\u6761\uFF09"],
    [{ t: "\u8BED\u97F3\u670D\u52A1", ct: true, sh: "F0F4F8" }, { t: "ASR + TTS (MIMO)", b: true }, "\u8BED\u97F3\u8BC6\u522B\u3001\u8BED\u97F3\u5408\u6210\u3001webrtcvad\u8BED\u97F3\u6D3B\u52A8\u68C0\u6D4B"],
    [{ t: "\u97F3\u9891\u5904\u7406", ct: true, sh: "F0F4F8" }, { t: "librosa + scipy + soundfile", b: true }, "\u97F3\u9891\u7279\u5F81\u63D0\u53D6\uFF08MFCC\u3001\u57FA\u9891\u3001\u80FD\u91CF\uFF09\uFF0Cffmpeg\u8F6C\u7801"],
    [{ t: "\u90E8\u7F72", ct: true, sh: "F0F4F8" }, { t: "Docker Compose + Nginx", b: true }, "\u5168\u6808\u5BB9\u5668\u5316\uFF0CNginx\u53CD\u5411\u4EE3\u7406\uFF0C8\u4E2A\u670D\u52A1\u5BB9\u5668"],
  ]
);

// Module overview table
const modTable = mkTable(
  [["\u6A21\u5757", 2400], ["\u529F\u80FD\u6982\u8FF0", 6986]],
  [
    [{ t: "\u7528\u6237\u4E0E\u8BA4\u8BC1", ct: true, sh: "F0F4F8" }, "\u6CE8\u518C\u3001JWT\u767B\u5F55\u3001\u4E2A\u4EBA\u4FE1\u606F\u7BA1\u7406\uFF0Cbcrypt\u52A0\u5BC6\uFF0C\u652F\u6301user/admin\u89D2\u8272"],
    [{ t: "\u7B80\u5386\u7BA1\u7406", ct: true, sh: "F0F4F8" }, "\u7B80\u5386\u4E0A\u4F20\u3001LLM\u667A\u80FD\u89E3\u6790\uFF08\u63D0\u53D6\u6559\u80B2\u3001\u6280\u80FD\u3001\u9879\u76EE\u7ECF\u5386\uFF09\u3001\u6458\u8981\u751F\u6210\uFF0CJSON\u7ED3\u6784\u5316\u5B58\u50A8"],
    [{ t: "\u5C97\u4F4D\u4E0E\u80FD\u529B\u7EF4\u5EA6", ct: true, sh: "F0F4F8" }, "\u5C97\u4F4D\u5206\u7C7B\u6D4F\u89C8\u3001\u6BCF\u4E2A\u5C97\u4F4D\u5B9A\u4E49\u591A\u4E2A\u80FD\u529B\u8BC4\u4F30\u7EF4\u5EA6\uFF08CompetencyDimension\uFF09"],
    [{ t: "\u2605 \u6A21\u62DF\u9762\u8BD5\u6838\u5FC3", ct: true, sh: "FFF2CC", b: true }, "\u9762\u8BD5\u4F1A\u8BDD\u521B\u5EFA\u3001\u72B6\u6001\u673A\u6D41\u8F6C\u30016\u9636\u6BB5\u6D41\u7A0B\u3001\u667A\u80FD\u63D0\u95EE\u4E0E\u8FFD\u95EE\u3001\u7B54\u6848\u63D0\u4EA4\u4E0E\u5B9E\u65F6\u8BC4\u4F30"],
    [{ t: "\u2605 RAG \u68C0\u7D22\u589E\u5F3A", ct: true, sh: "FFF2CC", b: true }, "Milvus\u5411\u91CF\u77E5\u8BC6\u5E93\u6784\u5EFA\u4E0E\u68C0\u7D22\uFF0C\u4E3A\u8BC4\u5206\u63D0\u4F9B\u4E13\u4E1A\u77E5\u8BC6\u4F9D\u636E\uFF0C\u89E3\u51B3LLM\u5E7B\u89C9\u95EE\u9898"],
    [{ t: "\u2605 \u591A\u7EF4\u8BC4\u5206\u5F15\u64CE", ct: true, sh: "FFF2CC", b: true }, "\u6587\u672C\u8BED\u4E495\u7EF4 + \u8BED\u97F3\u58F0\u5B665\u6307\u6807 + RAG\u8BC1\u636E\u878D\u5408\u7684\u7EFC\u5408\u8BC4\u5206\u4F53\u7CFB"],
    [{ t: "\u62A5\u544A\u751F\u6210", ct: true, sh: "F0F4F8" }, "\u5F02\u6B65\u4EFB\u52A1\u751F\u6210\u7EFC\u5408\u62A5\u544A\uFF0C\u542B\u603B\u5206\u3001\u80FD\u529B\u96F7\u8FBE\u56FE\u3001\u9010\u9898\u8BC4\u6790\u3001\u6539\u8FDB\u5EFA\u8BAE"],
    [{ t: "\u6210\u957F\u5206\u6790", ct: true, sh: "F0F4F8" }, "\u5386\u53F2\u9762\u8BD5\u6570\u636E\u5BF9\u6BD4\u3001\u80FD\u529B\u53D8\u5316\u8D8B\u52BF\u53EF\u89C6\u5316\u3001\u8584\u5F31\u9879\u8BC6\u522B"],
    [{ t: "\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5", ct: true, sh: "F0F4F8" }, "WebSocket\u5168\u53CC\u5DE5\u8BED\u97F3\u901A\u9053\u3001ASR/TTS\u5B9E\u65F6\u4EA4\u4E92\u3001VAD\u8BED\u97F3\u6D3B\u52A8\u68C0\u6D4B"],
  ]
);

// Database table
const dbTable = mkTable(
  [["\u6570\u636E\u8868", 2200], ["\u8BF4\u660E", 4400], ["\u5173\u952E\u5B57\u6BB5", 2786]],
  [
    [{ t: "User", ct: true, sh: "F0F4F8", b: true }, "\u7528\u6237\u4FE1\u606F\u8868\uFF0C\u542B\u89D2\u8272\u3001\u5BC6\u7801\u54C8\u5E0C", "role, hashed_password"],
    [{ t: "InterviewSession", ct: true, sh: "F0F4F8", b: true }, "\u9762\u8BD5\u4F1A\u8BDD\u8868\uFF0C\u8BB0\u5F55\u72B6\u6001\u3001\u98CE\u683C\u3001\u7B54\u9898\u6A21\u5F0F", "status, style, answer_mode"],
    [{ t: "InterviewQuestion", ct: true, sh: "F0F4F8", b: true }, "\u9762\u8BD5\u95EE\u9898\u8868\uFF0C\u542B\u8F6E\u6B21\u3001\u7C7B\u578B\u3001\u8FFD\u95EE\u7C7B\u578B", "turn_no, category, follow_up_type"],
    [{ t: "InterviewAnswer", ct: true, sh: "F0F4F8", b: true }, "\u7528\u6237\u56DE\u7B54\u8868\uFF0C\u542B\u6587\u672C\u3001\u97F3\u9891\u3001\u8BC4\u5206\u3001\u8BED\u97F3\u7279\u5F81", "text, audio_path, score_json"],
    [{ t: "InterviewReport", ct: true, sh: "F0F4F8", b: true }, "\u9762\u8BD5\u62A5\u544A\u8868\uFF0C\u542B\u603B\u5206\u3001\u7EF4\u5EA6\u5F97\u5206\u3001\u96F7\u8FBE\u56FE\u6570\u636E", "total_score, radar_data"],
    [{ t: "JobPosition", ct: true, sh: "F0F4F8", b: true }, "\u5C97\u4F4D\u4FE1\u606F\u8868\uFF0C\u542B\u5C97\u4F4D\u4EE3\u7801\u3001\u80FD\u529B\u7EF4\u5EA6\u5217\u8868", "code, competencies"],
    [{ t: "CompetencyDimension", ct: true, sh: "F0F4F8", b: true }, "\u80FD\u529B\u7EF4\u5EA6\u8868\uFF0C\u5B9A\u4E49\u5C97\u4F4D\u8BC4\u4F30\u7EF4\u5EA6", "name, weight, description"],
    [{ t: "Resume", ct: true, sh: "F0F4F8", b: true }, "\u7B80\u5386\u8868\uFF0C\u542BLLM\u89E3\u6790\u7ED3\u679C\u548C\u6458\u8981", "file_path, parsed_json"],
    [{ t: "AnalysisJob", ct: true, sh: "F0F4F8", b: true }, "\u5F02\u6B65\u5206\u6790\u4EFB\u52A1\u8868\uFF0C\u8DDF\u8E2A\u62A5\u544A\u751F\u6210\u72B6\u6001", "status, retry_count"],
  ]
);

// API endpoints table
const apiTable = mkTable(
  [["\u6A21\u5757", 1600], ["\u65B9\u6CD5", 800], ["\u8DEF\u5F84", 3400], ["\u529F\u80FD\u8BF4\u660E", 3586]],
  [
    [{ t: "\u8BA4\u8BC1", ct: true, sh: "F0F4F8" }, "POST", "/api/v1/auth/register", "\u7528\u6237\u6CE8\u518C"],
    [{ t: "\u8BA4\u8BC1", ct: true, sh: "F0F4F8" }, "POST", "/api/v1/auth/login", "\u767B\u5F55\u83B7\u53D6JWT Token"],
    [{ t: "\u8BA4\u8BC1", ct: true, sh: "F0F4F8" }, "GET", "/api/v1/auth/me", "\u83B7\u53D6\u5F53\u524D\u7528\u6237\u4FE1\u606F"],
    [{ t: "\u9762\u8BD5", ct: true, sh: "FFF2CC" }, "POST", "/api/v1/interviews", "\u521B\u5EFA\u9762\u8BD5\u4F1A\u8BDD"],
    [{ t: "\u9762\u8BD5", ct: true, sh: "FFF2CC" }, "POST", "/api/v1/interviews/{id}/answers", "\u63D0\u4EA4\u56DE\u7B54\uFF08\u6587\u672C/\u8BED\u97F3\uFF09"],
    [{ t: "\u9762\u8BD5", ct: true, sh: "FFF2CC" }, "GET", "/api/v1/interviews/{id}/next-question", "\u83B7\u53D6\u4E0B\u4E00\u9898"],
    [{ t: "\u9762\u8BD5", ct: true, sh: "FFF2CC" }, "POST", "/api/v1/interviews/{id}/complete", "\u7ED3\u675F\u9762\u8BD5"],
    [{ t: "\u9762\u8BD5", ct: true, sh: "FFF2CC" }, "GET", "/api/v1/interviews/{id}/report", "\u83B7\u53D6\u9762\u8BD5\u62A5\u544A"],
    [{ t: "\u7B80\u5386", ct: true, sh: "F0F4F8" }, "POST", "/api/v1/resumes/upload", "\u4E0A\u4F20\u7B80\u5386\u6587\u4EF6"],
    [{ t: "\u7B80\u5386", ct: true, sh: "F0F4F8" }, "POST", "/api/v1/resumes/{id}/parse", "LLM\u89E3\u6790\u7B80\u5386"],
    [{ t: "\u5C97\u4F4D", ct: true, sh: "F0F4F8" }, "GET", "/api/v1/positions", "\u83B7\u53D6\u5C97\u4F4D\u5217\u8868"],
    [{ t: "\u5C97\u4F4D", ct: true, sh: "F0F4F8" }, "GET", "/api/v1/positions/{code}/competencies", "\u83B7\u53D6\u5C97\u4F4D\u80FD\u529B\u7EF4\u5EA6"],
    [{ t: "\u8BB0\u5F55", ct: true, sh: "F0F4F8" }, "GET", "/api/v1/records/interviews", "\u5386\u53F2\u9762\u8BD5\u5217\u8868"],
    [{ t: "\u6210\u957F", ct: true, sh: "F0F4F8" }, "GET", "/api/v1/growth", "\u6210\u957F\u5206\u6790\u6570\u636E"],
    [{ t: "\u8BED\u97F3", ct: true, sh: "E8D5F5" }, "WS", "/ws/interview/{session_id}", "WebSocket\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5"],
  ]
);

// Deploy table
const deployTable = mkTable(
  [["\u670D\u52A1\u5BB9\u5668", 2000], ["\u955C\u50CF/\u7248\u672C", 2800], ["\u7AEF\u53E3", 1200], ["\u7528\u9014", 3386]],
  [
    [{ t: "Nginx", ct: true, sh: "F0F4F8", b: true }, "nginx:latest", "80", "\u53CD\u5411\u4EE3\u7406\u3001\u8DEF\u7531\u8F6C\u53D1"],
    [{ t: "Frontend", ct: true, sh: "F0F4F8", b: true }, "node:24-alpine", "4173", "Vue 3\u524D\u7AEF\u9759\u6001\u670D\u52A1"],
    [{ t: "Backend", ct: true, sh: "F0F4F8", b: true }, "python:3.12-slim", "8000", "FastAPI\u540E\u7AEF\u670D\u52A1"],
    [{ t: "MySQL", ct: true, sh: "F0F4F8", b: true }, "mysql:8.4", "3306", "\u4E1A\u52A1\u6570\u636E\u6301\u4E45\u5316"],
    [{ t: "Redis", ct: true, sh: "F0F4F8", b: true }, "redis:7.4-alpine", "6379", "\u7F13\u5B58\u4E0E\u4F1A\u8BDD\u7BA1\u7406"],
    [{ t: "Milvus", ct: true, sh: "F0F4F8", b: true }, "milvusdb/milvus:v2.5.4", "19530", "\u5411\u91CF\u68C0\u7D22\u670D\u52A1"],
    [{ t: "Etcd", ct: true, sh: "F0F4F8", b: true }, "quay.io/coreos/etcd:v3.5.5", "2379", "Milvus\u5143\u6570\u636E\u5B58\u50A8"],
    [{ t: "MinIO", ct: true, sh: "F0F4F8", b: true }, "minio/minio:latest", "9000", "Milvus\u5BF9\u8C61\u5B58\u50A8"],
  ]
);

// Scoring table
const scoreTable = mkTable(
  [["\u8BC4\u5206\u7C7B\u578B", 1400], ["\u7EF4\u5EA6/\u6307\u6807", 2200], ["\u8BF4\u660E", 3200], ["\u6280\u672F\u5B9E\u73B0", 2586]],
  [
    [{ t: "\u6587\u672C\u8BC4\u5206", ct: true, sh: "D6E4F0" }, { t: "\u6280\u672F\u6B63\u786E\u6027", b: true }, "\u56DE\u7B54\u5185\u5BB9\u662F\u5426\u51C6\u786E", "LLM + RAG\u8BC1\u636E\u5BF9\u6BD4"],
    [{ t: "\u6587\u672C\u8BC4\u5206", ct: true, sh: "D6E4F0" }, { t: "\u6280\u672F\u6DF1\u5EA6", b: true }, "\u662F\u5426\u6709\u6DF1\u5165\u7406\u89E3\u800C\u975E\u8868\u9762\u56DE\u7B54", "LLM\u8BED\u4E49\u5206\u6790"],
    [{ t: "\u6587\u672C\u8BC4\u5206", ct: true, sh: "D6E4F0" }, { t: "\u903B\u8F91\u7ED3\u6784", b: true }, "\u56DE\u7B54\u6761\u7406\u6027\u3001\u8BBA\u8BC1\u8FDE\u8D2F\u6027", "LLM\u8BED\u4E49\u5206\u6790"],
    [{ t: "\u6587\u672C\u8BC4\u5206", ct: true, sh: "D6E4F0" }, { t: "\u5C97\u4F4D\u5339\u914D\u5EA6", b: true }, "\u662F\u5426\u8D34\u5408\u76EE\u6807\u5C97\u4F4D\u8981\u6C42", "LLM + \u80FD\u529B\u7EF4\u5EA6"],
    [{ t: "\u6587\u672C\u8BC4\u5206", ct: true, sh: "D6E4F0" }, { t: "\u8868\u8FBE\u5B8C\u6574\u5EA6", b: true }, "\u662F\u5426\u5B8C\u6574\u8986\u76D6\u95EE\u9898\u8981\u70B9", "LLM\u8BED\u4E49\u5206\u6790"],
    [{ t: "\u8BED\u97F3\u5206\u6790", ct: true, sh: "E2EFDA" }, { t: "\u97F3\u91CF\u7A33\u5B9A\u6027", b: true }, "\u8BED\u97F3\u97F3\u91CF\u662F\u5426\u5747\u5300\u7A33\u5B9A", "librosa + RMS\u80FD\u91CF"],
    [{ t: "\u8BED\u97F3\u5206\u6790", ct: true, sh: "E2EFDA" }, { t: "\u505C\u987F\u6BD4\u4F8B", b: true }, "\u505C\u987F\u7684\u9891\u7387\u548C\u65F6\u957F", "webrtcvad"],
    [{ t: "\u8BED\u97F3\u5206\u6790", ct: true, sh: "E2EFDA" }, { t: "\u8BED\u901F", b: true }, "\u56DE\u7B54\u901F\u5EA6\u662F\u5426\u9002\u4E2D", "\u8BCD\u6570/\u65F6\u957F\u8BA1\u7B97"],
    [{ t: "\u8BED\u97F3\u5206\u6790", ct: true, sh: "E2EFDA" }, { t: "\u97F3\u8C03\u53D8\u5316", b: true }, "\u8BED\u8C03\u81EA\u7136\u5EA6\u548C\u53D8\u5316\u6027", "librosa + \u57FA\u9891\u63D0\u53D6"],
    [{ t: "\u8BED\u97F3\u5206\u6790", ct: true, sh: "E2EFDA" }, { t: "\u6709\u58F0\u6BD4\u4F8B", b: true }, "\u6709\u6548\u8BED\u97F3\u5360\u603B\u65F6\u957F\u7684\u6BD4\u4F8B", "webrtcvad"],
  ]
);

// Follow-up strategy table
const followUpTable = mkTable(
  [["\u8FFD\u95EE\u7B56\u7565", 2200], ["\u89E6\u53D1\u6761\u4EF6", 3600], ["\u884C\u4E3A", 3586]],
  [
    [{ t: "\u6DF1\u5316 (deepen)", ct: true, sh: "E2EFDA", b: true }, "\u56DE\u7B54\u8D28\u91CF\u8F83\u597D", "\u5728\u540C\u4E00\u7EF4\u5EA6\u6DF1\u5165\u63A2\u7A76\u66F4\u590D\u6742\u95EE\u9898"],
    [{ t: "\u8F6C\u5411 (redirect)", ct: true, sh: "D6E4F0", b: true }, "\u56DE\u7B54\u504F\u79BB\u4E3B\u9898", "\u5F15\u5BFC\u56DE\u6B63\u786E\u65B9\u5411"],
    [{ t: "\u53EF\u4FE1\u5EA6 (credibility)", ct: true, sh: "FCE4D6", b: true }, "\u56DE\u7B54\u7591\u4F3C\u80CC\u8BF5", "\u901A\u8FC7\u7EC6\u8282\u95EE\u9898\u9A8C\u8BC1\u771F\u5B9E\u6027"],
    [{ t: "\u5207\u6362 (switch_dimension)", ct: true, sh: "E8D5F5", b: true }, "\u5F53\u524D\u7EF4\u5EA6\u5DF2\u5145\u5206\u8BC4\u4F30", "\u5207\u6362\u5230\u4E0B\u4E00\u4E2A\u80FD\u529B\u7EF4\u5EA6"],
  ]
);

// ===== Document =====
const doc = new Document({
  styles: {
    default: { document: { run: { font: F, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: F, color: "2B579A" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: F, color: "2B579A" },
        paragraph: { spacing: { before: 300, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: F, color: "404040" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 2 } },
    ]
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.",
      alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
  ]},
  sections: [{
    properties: {
      page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 } }
    },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "2B579A", space: 4 } },
      children: [new TextRun({ text: "AI\u6A21\u62DF\u9762\u8BD5\u4E0E\u80FD\u529B\u63D0\u5347\u7CFB\u7EDF \u00B7 \u8BE6\u7EC6\u65B9\u6848\u521D\u7A3F", font: F, size: 18, color: "2B579A" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "- ", font: F, size: 18, color: "888888" }),
        new TextRun({ children: [PageNumber.CURRENT], font: F, size: 18, color: "888888" }),
        new TextRun({ text: " -", font: F, size: 18, color: "888888" })] })] }) },
    children: [
      // ===== TITLE PAGE =====
      new Paragraph({ spacing: { before: 2000 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "AI\u6A21\u62DF\u9762\u8BD5\u4E0E\u80FD\u529B\u63D0\u5347\u7CFB\u7EDF", bold: true, font: F, size: 52, color: "2B579A" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "2B579A", space: 8 } },
        children: [new TextRun({ text: "\u8BE6\u7EC6\u65B9\u6848\u521D\u7A3F", font: F, size: 32, color: "666666" })] }),
      new Paragraph({ spacing: { before: 400 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "FastAPI + Vue 3 + MySQL + Milvus + LLM", font: F, size: 22, color: "595959" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 },
        children: [new TextRun({ text: "\u5168\u6808\u5BB9\u5668\u5316\u90E8\u7F72 | \u591A\u6A21\u6001\u8BC4\u4EF7 | RAG\u68C0\u7D22\u589E\u5F3A | WebSocket\u8BED\u97F3\u9762\u8BD5", font: F, size: 22, color: "595959" })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // ===== 1 \u9879\u76EE\u6982\u8FF0 =====
      h1("1  \u9879\u76EE\u6982\u8FF0"),
      p("\u968F\u7740\u4EBA\u5DE5\u667A\u80FD\u6280\u672F\u7684\u5FEB\u901F\u53D1\u5C55\uFF0C\u5728\u7EBF\u6C42\u804C\u8BAD\u7EC3\u5E73\u53F0\u9010\u6E10\u6210\u4E3A\u63D0\u5347\u4E2A\u4EBA\u9762\u8BD5\u80FD\u529B\u7684\u91CD\u8981\u5DE5\u5177\u3002\u4F20\u7EDF\u9762\u8BD5\u8BAD\u7EC3\u4E3B\u8981\u4F9D\u8D56\u4EBA\u5DE5\u6A21\u62DF\uFF0C\u5B58\u5728\u6548\u7387\u4F4E\u3001\u8BC4\u4EF7\u4E3B\u89C2\u6027\u5F3A\u3001\u8BAD\u7EC3\u6210\u672C\u9AD8\u7B49\u95EE\u9898\u3002\u672C\u9879\u76EE\u8BBE\u8BA1\u5E76\u5B9E\u73B0\u4E00\u4E2A\u57FA\u4E8E LLM \u5927\u8BED\u8A00\u6A21\u578B\u7684 AI \u6A21\u62DF\u9762\u8BD5\u4E0E\u80FD\u529B\u63D0\u5347\u7CFB\u7EDF\uFF0C\u7ED3\u5408 RAG \u68C0\u7D22\u589E\u5F3A\u751F\u6210\u3001\u591A\u6A21\u6001\u8F93\u5165\uFF08\u6587\u672C + \u8BED\u97F3\uFF09\u3001WebSocket \u5B9E\u65F6\u8BED\u97F3\u5BF9\u8BDD\u7B49\u6280\u672F\uFF0C\u5BF9\u7528\u6237\u56DE\u7B54\u8FDB\u884C\u667A\u80FD\u8BC4\u4EF7\uFF0C\u5E76\u751F\u6210\u9762\u8BD5\u62A5\u544A\u548C\u6539\u8FDB\u5EFA\u8BAE\u3002"),

      // ===== 2 \u7CFB\u7EDF\u76EE\u6807 =====
      h1("2  \u7CFB\u7EDF\u76EE\u6807"),
      num("\u6784\u5EFA\u9762\u5411\u6C42\u804C\u8BAD\u7EC3\u573A\u666F\u7684 AI \u6A21\u62DF\u9762\u8BD5\u5E73\u53F0\uFF0C\u652F\u6301\u6587\u672C\u4E0E\u5B9E\u65F6\u8BED\u97F3\u4E24\u79CD\u9762\u8BD5\u6A21\u5F0F"),
      num("\u5B9E\u73B0\u57FA\u4E8E\u5C97\u4F4D\u80FD\u529B\u7EF4\u5EA6\u4E0E\u7B80\u5386\u4FE1\u606F\u7684\u667A\u80FD\u63D0\u95EE\uFF0C\u652F\u6301\u591A\u8F6E\u8FFD\u95EE\u4E0E\u6DF1\u5165\u8FFD\u95EE"),
      num("\u901A\u8FC7 RAG \u68C0\u7D22\u589E\u5F3A\u4E0E LLM \u7ED3\u5408\uFF0C\u5BF9\u56DE\u7B54\u8FDB\u884C\u591A\u7EF4\u5EA6\u8BC4\u4EF7\uFF08\u6280\u672F\u6B63\u786E\u6027\u3001\u6DF1\u5EA6\u3001\u903B\u8F91\u3001\u5339\u914D\u5EA6\u3001\u5B8C\u6574\u5EA6\uFF09"),
      num("\u81EA\u52A8\u751F\u6210\u7EFC\u5408\u9762\u8BD5\u62A5\u544A\uFF0C\u5305\u542B\u80FD\u529B\u96F7\u8FBE\u56FE\u3001\u9010\u9898\u5206\u6790\u4E0E\u6539\u8FDB\u5EFA\u8BAE"),
      num("\u63D0\u4F9B\u4E2A\u4EBA\u6210\u957F\u8FFD\u8E2A\u529F\u80FD\uFF0C\u5C55\u793A\u591A\u6B21\u9762\u8BD5\u7684\u80FD\u529B\u53D8\u5316\u8D8B\u52BF"),

      // ===== 3 \u7CFB\u7EDF\u603B\u4F53\u67B6\u6784 =====
      h1("3  \u7CFB\u7EDF\u603B\u4F53\u67B6\u6784"),
      p("\u7CFB\u7EDF\u91C7\u7528\u524D\u540E\u7AEF\u5206\u79BB\u67B6\u6784\u3002\u524D\u7AEF\u8D1F\u8D23\u7528\u6237\u4EA4\u4E92\u754C\u9762\uFF0C\u540E\u7AEF\u8D1F\u8D23\u4E1A\u52A1\u903B\u8F91\u5904\u7406\u3001AI \u63A5\u53E3\u8C03\u7528\u4EE5\u53CA\u6570\u636E\u7BA1\u7406\u3002\u67B6\u6784\u5206\u4E3A\u7528\u6237\u5C42\u3001\u524D\u7AEF\u5C55\u793A\u5C42\u3001API \u7F51\u5173\u5C42\u3001\u540E\u7AEF\u670D\u52A1\u5C42\u3001AI \u80FD\u529B\u5C42\u548C\u6570\u636E\u5B58\u50A8\u5C42\u5171\u516D\u5C42\u3002\u67B6\u6784\u56FE\u5982\u4E0B\uFF1A"),
      img("architecture.png", 550, 360),
      cap("\u56FE 1  \u7CFB\u7EDF\u603B\u4F53\u67B6\u6784\u56FE"),

      h2("3.1  \u6280\u672F\u6808\u660E\u7EC6"),
      gap(), techTable, gap(),
      p("\u67B6\u6784\u7279\u70B9\uFF1A\u524D\u7AEF\u901A\u8FC7 Axios \u8C03\u7528 REST API\uFF0C\u901A\u8FC7 WebSocket \u5B9E\u73B0\u5B9E\u65F6\u8BED\u97F3\u5BF9\u8BDD\uFF1B\u540E\u7AEF API \u7EDF\u4E00\u524D\u7F00 /api/v1\uFF0C\u81EA\u52A8\u751F\u6210 Swagger \u6587\u6863\uFF08/docs\uFF09\uFF1B\u6570\u636E\u5E93\u64CD\u4F5C\u901A\u8FC7 SQLAlchemy \u4F9D\u8D56\u6CE8\u5165\u7BA1\u7406\u4F1A\u8BDD\uFF1BLLM \u901A\u8FC7 httpx \u5F02\u6B65\u8C03\u7528 OpenAI \u517C\u5BB9 API\u3002"),

      // ===== 4 \u529F\u80FD\u6A21\u5757 =====
      new Paragraph({ children: [new PageBreak()] }),
      h1("4  \u7CFB\u7EDF\u529F\u80FD\u6A21\u5757\u8BBE\u8BA1"),
      p("\u7CFB\u7EDF\u5305\u542B 9 \u4E2A\u529F\u80FD\u6A21\u5757\uFF0C\u5176\u4E2D 3 \u4E2A\u6838\u5FC3\u6A21\u5757\uFF08\u6807\u8BB0 \u2605\uFF09\u662F\u7CFB\u7EDF\u7684\u6280\u672F\u6838\u5FC3\u3002\u6A21\u5757\u5168\u666F\u5982\u4E0B\uFF1A"),
      img("modules_overview.png", 550, 200),
      cap("\u56FE 2  \u7CFB\u7EDF\u529F\u80FD\u6A21\u5757\u5168\u666F\u56FE"),
      gap(), modTable,

      // --- 4.1 Interview Core ---
      new Paragraph({ children: [new PageBreak()] }),
      h2("4.1  \u6A21\u62DF\u9762\u8BD5\u6838\u5FC3\u6A21\u5757 \u2605"),
      p("\u8BE5\u6A21\u5757\u662F\u7CFB\u7EDF\u7684\u6838\u5FC3\u5F15\u64CE\uFF0C\u540E\u7AEF\u5B9E\u73B0\u4EE3\u7801\u8D85\u8FC7 3000 \u884C\uFF08interview_service.py\uFF09\uFF0C\u7BA1\u7406\u4ECE\u521B\u5EFA\u9762\u8BD5\u5230\u751F\u6210\u62A5\u544A\u7684\u5B8C\u6574\u751F\u547D\u5468\u671F\u3002"),

      h3("4.1.1  \u9762\u8BD5\u72B6\u6001\u673A"),
      p("\u9762\u8BD5\u6D41\u7A0B\u91C7\u7528\u4E25\u683C\u7684\u72B6\u6001\u673A\u6A21\u578B\uFF0C\u786E\u4FDD\u6D41\u7A0B\u6709\u5E8F\u8FDB\u884C\uFF0C\u5171 6 \u4E2A\u9636\u6BB5\uFF1A"),
      img("state_machine.png", 550, 250),
      cap("\u56FE 3  \u9762\u8BD5\u6D41\u7A0B\u72B6\u6001\u673A\u4E0E\u8FFD\u95EE\u7B56\u7565"),

      h3("4.1.2  \u667A\u80FD\u8FFD\u95EE\u7B56\u7565"),
      p("\u7CFB\u7EDF\u6839\u636E\u7528\u6237\u56DE\u7B54\u8D28\u91CF\u52A8\u6001\u51B3\u5B9A\u8FFD\u95EE\u65B9\u5411\uFF0C\u800C\u975E\u7B80\u5355\u7684\u987A\u5E8F\u51FA\u9898\uFF0C\u6A21\u62DF\u771F\u5B9E\u9762\u8BD5\u5B98\u884C\u4E3A\uFF1A"),
      gap(), followUpTable,

      h3("4.1.3  \u9762\u8BD5\u914D\u7F6E\u53C2\u6570"),
      bullet("\u9762\u8BD5\u98CE\u683C\uFF1A\u5E38\u89C4\u6A21\u5F0F (regular)\u3001\u538B\u529B\u6A21\u5F0F (pressure)\u3001\u5F15\u5BFC\u6A21\u5F0F (guided)"),
      bullet("\u7B54\u9898\u6A21\u5F0F\uFF1A\u6587\u672C\u56DE\u7B54 (text)\u3001\u8BED\u97F3\u56DE\u7B54 (audio)"),
      bullet("\u9898\u76EE\u6570\u91CF\uFF1A\u9ED8\u8BA4 6 \u9053\uFF0C\u53EF\u914D\u7F6E 5\u20138 \u9053\uFF08\u73AF\u5883\u53D8\u91CF DEFAULT_QUESTION_COUNT\uFF09"),
      bullet("\u4F1A\u8BDD TTL\uFF1A\u652F\u6301\u4F1A\u8BDD\u8D85\u65F6\u81EA\u52A8\u8FC7\u671F\u673A\u5236\uFF0C\u9632\u6B62\u5E7D\u7075\u4F1A\u8BDD"),
      bullet("\u95EE\u9898\u9884\u53D6\uFF1A\u652F\u6301\u4E0B\u4E00\u9898\u9884\u751F\u6210\uFF08prefetch\uFF09\uFF0C\u51CF\u5C11\u7528\u6237\u7B49\u5F85\u65F6\u95F4"),

      // --- 4.2 RAG ---
      h2("4.2  RAG \u68C0\u7D22\u589E\u5F3A\u6A21\u5757 \u2605"),
      p("\u7CFB\u7EDF\u6784\u5EFA\u4E86\u57FA\u4E8E Milvus \u5411\u91CF\u6570\u636E\u5E93\u7684\u4E13\u4E1A\u77E5\u8BC6\u5E93\uFF0C\u89E3\u51B3\u4E86\u7EAF\u4F9D\u8D56 LLM \u8BC4\u5206\u53EF\u80FD\u51FA\u73B0\u7684\u201C\u5E7B\u89C9\u201D\u95EE\u9898\uFF0C\u8BA9\u8BC4\u5206\u6709\u636E\u53EF\u4F9D\u3002\u5B8C\u6574\u6D41\u7A0B\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("rag_pipeline.png", 550, 260),
      cap("\u56FE 4  RAG \u68C0\u7D22\u589E\u5F3A\u8BC4\u5206\u6D41\u7A0B\uFF08\u79BB\u7EBF\u6784\u5EFA + \u5728\u7EBF\u68C0\u7D22\uFF09"),

      h3("\u77E5\u8BC6\u5E93\u6784\u5EFA\u6D41\u7A0B\uFF08\u79BB\u7EBF\uFF09"),
      bullet("\u6587\u6863\u6536\u96C6\uFF1A\u6309\u5C97\u4F4D\u6536\u96C6\u4E13\u4E1A\u6280\u672F\u6587\u6863\uFF0C\u5B58\u50A8\u4E8E data/content_source/ \u76EE\u5F55"),
      bullet("\u6587\u6863\u5206\u5757\uFF1A\u62C6\u5206\u4E3A chunk\uFF0C\u6BCF\u5757\u6253\u5143\u6570\u636E\u6807\u7B7E\uFF08role_code\u3001competency_code\u3001doc_type\u3001doc_id\uFF09"),
      bullet("\u5411\u91CF\u5D4C\u5165\uFF1AQwen text-embedding-v3 \u751F\u6210 128 \u7EF4\u5411\u91CF\uFF0C\u6279\u91CF\u5904\u7406\uFF08\u6BCF\u6279 10 \u6761\uFF09"),
      bullet("\u5411\u91CF\u5165\u5E93\uFF1A\u5B58\u5165 Milvus \u96C6\u5408 interview_kb_chunks\uFF0C\u652F\u6301\u4F59\u5F26\u76F8\u4F3C\u5EA6\u68C0\u7D22"),
      bullet("\u6784\u5EFA\u811A\u672C\uFF1Ascripts/build_kb.py\uFF0C\u8F93\u51FA data/runtime_corpus/records.jsonl"),

      h3("\u8BC4\u5206\u65F6\u68C0\u7D22\u6D41\u7A0B\uFF08\u5728\u7EBF\uFF09"),
      bullet("\u6839\u636E\u7528\u6237\u56DE\u7B54\u751F\u6210\u67E5\u8BE2\u5411\u91CF"),
      bullet("\u5728 Milvus \u4E2D\u6309\u5C97\u4F4D\u4EE3\u7801\u8FC7\u6EE4 + \u201Ccommon\u201D \u56DE\u9000\u68C0\u7D22\uFF0C\u53D6 Top-K\uFF08\u9ED8\u8BA4 6\uFF09\u6700\u76F8\u4F3C\u77E5\u8BC6\u7247\u6BB5"),
      bullet("\u5C06\u68C0\u7D22\u7ED3\u679C\u4F5C\u4E3A RetrievalEvidence \u6CE8\u5165 LLM Prompt\uFF0C\u63D0\u5347\u8BC4\u5206\u4E13\u4E1A\u6027\u548C\u5BA2\u89C2\u6027"),

      // --- 4.3 Scoring ---
      new Paragraph({ children: [new PageBreak()] }),
      h2("4.3  \u591A\u7EF4\u5EA6\u8BC4\u5206\u6A21\u5757 \u2605"),
      p("\u8BC4\u5206\u6A21\u5757\u878D\u5408\u6587\u672C\u8BED\u4E49\u5206\u6790\u548C\u8BED\u97F3\u58F0\u5B66\u7279\u5F81\uFF0C\u7ED3\u5408 RAG \u68C0\u7D22\u8BC1\u636E\u8FDB\u884C\u7EFC\u5408\u6253\u5206\u3002\u8BC4\u5206\u4F53\u7CFB\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("scoring_system.png", 550, 240),
      cap("\u56FE 5  \u591A\u7EF4\u5EA6\u8BC4\u5206\u4F53\u7CFB"),

      h3("\u8BC4\u5206\u7EF4\u5EA6\u660E\u7EC6"),
      gap(), scoreTable, gap(),
      p("\u8BED\u97F3\u7279\u5F81\u63D0\u53D6\u57FA\u4E8E librosa\u3001webrtcvad\u3001scipy \u7B49\u5E93\uFF0C\u63D0\u53D6 MFCC\u3001\u57FA\u9891\u3001\u80FD\u91CF\u7B49\u58F0\u5B66\u53C2\u6570\u540E\u8BA1\u7B97\u4E0A\u8FF0\u6307\u6807\u3002\u8BC4\u5206\u7ED3\u679C\u4EE5 AnswerEvaluation \u7ED3\u6784\u4F53\u8FD4\u56DE\uFF0C\u5305\u542B\u5404\u7EF4\u5EA6\u5206\u6570\u3001RAG \u68C0\u7D22\u8BC1\u636E\u548C\u6539\u8FDB\u5EFA\u8BAE\u3002"),

      // --- 4.4 Other modules ---
      h2("4.4  \u5176\u4ED6\u529F\u80FD\u6A21\u5757"),
      h3("\u7528\u6237\u4E0E\u8BA4\u8BC1"),
      p("\u57FA\u4E8E JWT Token \u7684\u65E0\u72B6\u6001\u8BA4\u8BC1\u3002\u7528\u6237\u6CE8\u518C\u65F6\u5BC6\u7801\u91C7\u7528 bcrypt \u54C8\u5E0C\u5B58\u50A8\uFF0C\u767B\u5F55\u6210\u529F\u8FD4\u56DE Bearer Token\uFF0C\u9ED8\u8BA4 1440 \u5206\u949F\u8FC7\u671F\u3002\u540E\u7AEF\u901A\u8FC7 FastAPI \u4F9D\u8D56\u6CE8\u5165 get_current_user() \u5B9E\u73B0\u7EDF\u4E00\u6743\u9650\u6821\u9A8C\uFF0C\u652F\u6301 user \u548C admin \u4E24\u79CD\u89D2\u8272\u3002"),
      h3("\u7B80\u5386\u7BA1\u7406"),
      p("\u7528\u6237\u4E0A\u4F20\u7B80\u5386\u6587\u4EF6\u540E\uFF0C\u901A\u8FC7 LLM \u667A\u80FD\u89E3\u6790\u63D0\u53D6\u7ED3\u6784\u5316\u4FE1\u606F\uFF08\u6559\u80B2\u7ECF\u5386\u3001\u6280\u672F\u6808\u3001\u9879\u76EE\u7ECF\u5386\uFF09\uFF0C\u89E3\u6790\u7ED3\u679C\u4EE5 JSON \u683C\u5F0F\u5B58\u50A8\u5728 Resume \u8868\u4E2D\uFF0C\u5E76\u751F\u6210\u7B80\u5386\u6458\u8981\u4F9B\u9762\u8BD5\u65F6\u4F7F\u7528\u3002"),
      h3("\u5C97\u4F4D\u4E0E\u80FD\u529B\u7EF4\u5EA6"),
      p("\u7CFB\u7EDF\u9884\u7F6E\u591A\u4E2A\u5C97\u4F4D\u6A21\u677F\uFF08JobPosition\uFF09\uFF0C\u6BCF\u4E2A\u5C97\u4F4D\u5B9A\u4E49\u591A\u4E2A\u80FD\u529B\u8BC4\u4F30\u7EF4\u5EA6\uFF08CompetencyDimension\uFF09\u3002\u4F8B\u5982\u524D\u7AEF\u5F00\u53D1\u5C97\u4F4D\u5305\u542B\u201CCSS\u5E03\u5C40\u201D\u201CJavaScript\u57FA\u7840\u201D\u201C\u6846\u67B6\u5E94\u7528\u201D\u7B49\u7EF4\u5EA6\uFF0C\u4E3A\u667A\u80FD\u51FA\u9898\u548C\u8BC4\u5206\u63D0\u4F9B\u57FA\u7840\u3002"),
      h3("\u62A5\u544A\u751F\u6210"),
      p("\u9762\u8BD5\u7ED3\u675F\u540E\uFF0C\u7CFB\u7EDF\u901A\u8FC7\u5F02\u6B65\u4EFB\u52A1\uFF08AnalysisJob\uFF09\u751F\u6210\u7EFC\u5408\u62A5\u544A\uFF08InterviewReport\uFF09\u3002\u62A5\u544A\u5305\u542B\u603B\u5206\u3001\u5404\u80FD\u529B\u7EF4\u5EA6\u5F97\u5206\u3001\u96F7\u8FBE\u56FE\u6570\u636E\u3001\u9010\u9898 QA \u8BB0\u5F55\u548C\u7EFC\u5408\u6539\u8FDB\u5EFA\u8BAE\u3002\u540E\u53F0 Worker \u5728\u670D\u52A1\u542F\u52A8\u65F6\u81EA\u52A8\u5904\u7406\u5F85\u751F\u6210\u7684\u62A5\u544A\uFF0C\u652F\u6301\u5931\u8D25\u91CD\u8BD5\u3002"),
      h3("\u6210\u957F\u5206\u6790"),
      p("\u57FA\u4E8E ECharts \u53EF\u89C6\u5316\u5C55\u793A\u7528\u6237\u591A\u6B21\u9762\u8BD5\u7684\u80FD\u529B\u53D8\u5316\u8D8B\u52BF\uFF0C\u8BC6\u522B\u8584\u5F31\u9879\uFF0C\u524D\u7AEF\u8DEF\u7531 /growth\u3002"),
      h3("\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5"),
      p("\u901A\u8FC7 WebSocket\uFF08/ws/interview/{session_id}\uFF09\u5B9E\u73B0\u5168\u53CC\u5DE5\u8BED\u97F3\u5BF9\u8BDD\u3002\u652F\u6301\u5B9E\u65F6\u8BED\u97F3\u6D41\u4F20\u8F93\u3001ASR \u8BED\u97F3\u8BC6\u522B\u3001TTS \u8BED\u97F3\u5408\u6210\uFF08\u57FA\u4E8E MIMO \u670D\u52A1\uFF09\u548C VAD \u8BED\u97F3\u6D3B\u52A8\u68C0\u6D4B\u3002\u6D88\u606F\u7C7B\u578B\u5305\u62EC\uFF1AHEARTBEAT\u3001SESSION_START\u3001AUDIO_CHUNK\u3001SPEAK_DONE\u3001END_INTERVIEW\u3002\u524D\u7AEF\u901A\u8FC7\u6C89\u6D78\u5F0F\u8BED\u97F3\u9762\u8BD5\u623F\u95F4\uFF08/interviews/:id/room\uFF09\u63D0\u4F9B\u7C7B\u4F3C\u771F\u5B9E\u9762\u8BD5\u7684\u4F53\u9A8C\u3002"),

      // ===== 5 \u6570\u636E\u5E93\u8BBE\u8BA1 =====
      new Paragraph({ children: [new PageBreak()] }),
      h1("5  \u6570\u636E\u5E93\u8BBE\u8BA1"),
      p("\u7CFB\u7EDF\u4F7F\u7528 MySQL 8.4 \u4F5C\u4E3A\u4E3B\u6570\u636E\u5E93\uFF0C\u901A\u8FC7 SQLAlchemy 2.0 ORM \u64CD\u4F5C\uFF0CAlembic \u7BA1\u7406\u6570\u636E\u5E93\u8FC1\u79FB\u3002\u4E3B\u8981\u6570\u636E\u8868\u5982\u4E0B\uFF1A"),
      gap(), dbTable, gap(),
      p("\u5173\u952E\u679A\u4E3E\u7C7B\u578B\uFF1A"),
      bullet("InterviewStatus: opening \u2192 resume_clarification \u2192 technical_question \u2192 deep_follow_up \u2192 candidate_question \u2192 summary \u2192 completed"),
      bullet("InterviewStyle: regular | pressure | guided"),
      bullet("AnswerMode: text | audio"),
      bullet("QuestionCategory: opening | clarification | technical | follow_up | wrap_up"),
      bullet("FollowUpType: none | deepen | redirect | credibility | switch_dimension"),

      // ===== 6 API =====
      h1("6  API \u63A5\u53E3\u8BBE\u8BA1"),
      p("\u7CFB\u7EDF API \u7EDF\u4E00\u524D\u7F00 /api/v1\uFF0C\u91C7\u7528 RESTful \u98CE\u683C\uFF0C\u540E\u7AEF\u81EA\u52A8\u751F\u6210 Swagger \u6587\u6863\uFF08/docs\uFF09\u548C ReDoc\uFF08/redoc\uFF09\u3002\u4E3B\u8981\u63A5\u53E3\u5217\u8868\uFF1A"),
      gap(), apiTable,

      // ===== 7 \u90E8\u7F72 =====
      new Paragraph({ children: [new PageBreak()] }),
      h1("7  \u7CFB\u7EDF\u90E8\u7F72\u65B9\u6848"),
      p("\u7CFB\u7EDF\u91C7\u7528 Docker Compose \u5168\u6808\u5BB9\u5668\u5316\u90E8\u7F72\uFF0C\u5171 8 \u4E2A\u670D\u52A1\u5BB9\u5668\uFF1A"),
      img("deployment.png", 550, 250),
      cap("\u56FE 6  Docker Compose \u90E8\u7F72\u67B6\u6784\u56FE"),
      gap(), deployTable, gap(),
      p("Nginx \u4F5C\u4E3A\u7EDF\u4E00\u5165\u53E3\uFF0C\u5C06 /api \u8BF7\u6C42\u4EE3\u7406\u5230 FastAPI \u540E\u7AEF\uFF08\u7AEF\u53E3 8000\uFF09\uFF0C\u5176\u4ED6\u8BF7\u6C42\u4EE3\u7406\u5230 Vue \u524D\u7AEF\u9759\u6001\u670D\u52A1\uFF08\u7AEF\u53E3 4173\uFF09\u3002\u5F00\u53D1\u73AF\u5883\u4E0B\uFF0C\u524D\u7AEF\u4F7F\u7528 Vite \u5F00\u53D1\u670D\u52A1\u5668\uFF08\u7AEF\u53E3 5173\uFF09\u5E76\u914D\u7F6E API \u4EE3\u7406\u3002\u6240\u6709\u6570\u636E\u901A\u8FC7 Docker Volume \u6301\u4E45\u5316\u3002"),

      // ===== 8 \u521B\u65B0 =====
      h1("8  \u521B\u65B0\u4EAE\u70B9"),
      num("\u591A\u6A21\u6001\u9762\u8BD5\u8BC4\u4EF7\uFF1A\u878D\u5408\u6587\u672C\u8BED\u4E49\u5206\u6790\uFF085 \u7EF4\u5EA6\uFF09\u4E0E\u8BED\u97F3\u58F0\u5B66\u7279\u5F81\uFF085 \u6307\u6807\uFF09\uFF0C\u7A81\u7834\u5355\u4E00\u6587\u672C\u8BC4\u5206\u7684\u5C40\u9650\u6027"),
      num("RAG \u68C0\u7D22\u589E\u5F3A\u8BC4\u5206\uFF1A\u57FA\u4E8E Milvus \u5411\u91CF\u6570\u636E\u5E93\u7684\u4E13\u4E1A\u77E5\u8BC6\u68C0\u7D22\uFF0C\u89E3\u51B3 LLM \u8BC4\u5206\u5E7B\u89C9\u95EE\u9898\uFF0C\u4F7F\u8BC4\u5206\u6709\u636E\u53EF\u4F9D"),
      num("\u667A\u80FD\u8FFD\u95EE\u7B56\u7565\uFF1A\u56DB\u79CD\u52A8\u6001\u8FFD\u95EE\u65B9\u5411\uFF08\u6DF1\u5316/\u8F6C\u5411/\u53EF\u4FE1\u5EA6\u9A8C\u8BC1/\u5207\u6362\u7EF4\u5EA6\uFF09\uFF0C\u6A21\u62DF\u771F\u5B9E\u9762\u8BD5\u5B98\u884C\u4E3A\u800C\u975E\u56FA\u5B9A\u51FA\u9898"),
      num("\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5\uFF1A\u57FA\u4E8E WebSocket \u7684\u5168\u53CC\u5DE5\u6C89\u6D78\u5F0F\u8BED\u97F3\u5BF9\u8BDD\uFF0C\u96C6\u6210 ASR + TTS + VAD"),
      num("\u5168\u6808\u5BB9\u5668\u5316\u90E8\u7F72\uFF1ADocker Compose \u7EDF\u4E00\u7BA1\u7406 8 \u4E2A\u670D\u52A1\u5BB9\u5668\uFF0C\u652F\u6301\u4E00\u952E\u90E8\u7F72"),

      // ===== 9 \u56E2\u961F =====
      h1("9  \u56E2\u961F\u5206\u5DE5\u4E0E\u65F6\u95F4\u5B89\u6392"),
      p("\u56E2\u961F\u6210\u5458\u4E0E\u804C\u8D23\u5982\u4E0B\uFF1A"),
      gap(),
      mkTable(
        [["\u89D2\u8272", 2000], ["\u804C\u8D23\u8303\u56F4", 7386]],
        [
          [{ t: "\u9879\u76EE\u7ECF\u7406", ct: true, sh: "F0F4F8", b: true }, "\u9879\u76EE\u89C4\u5212\u4E0E\u7BA1\u7406\u3001\u56E2\u961F\u534F\u8C03\u4E0E\u4EFB\u52A1\u5206\u914D\u3001\u8FDB\u5EA6\u63A7\u5236\u3001\u8D28\u91CF\u63A7\u5236\u3001\u6587\u6863\u7F16\u5199"],
          [{ t: "\u540E\u7AEF\u5F00\u53D1", ct: true, sh: "F0F4F8", b: true }, "FastAPI \u670D\u52A1\u5F00\u53D1\u3001\u6570\u636E\u5E93\u8BBE\u8BA1\u4E0E Alembic \u8FC1\u79FB\u3001WebSocket \u8BED\u97F3\u670D\u52A1\u3001Docker \u90E8\u7F72\u914D\u7F6E"],
          [{ t: "\u524D\u7AEF\u5F00\u53D1", ct: true, sh: "F0F4F8", b: true }, "Vue 3 \u754C\u9762\u5F00\u53D1\u3001Pinia \u72B6\u6001\u7BA1\u7406\u3001ECharts \u56FE\u8868\u3001\u524D\u540E\u7AEF\u63A5\u53E3\u8054\u8C03"],
          [{ t: "AI\u63A5\u53E3\u4E0E\u7B97\u6CD5", ct: true, sh: "F0F4F8", b: true }, "LLM \u63D0\u95EE\u4E0E\u8BC4\u5206\u7B97\u6CD5\u3001RAG \u77E5\u8BC6\u5E93\u6784\u5EFA\u3001\u8BED\u97F3\u5904\u7406\u6A21\u5757\u3001\u97F3\u9891\u7279\u5F81\u63D0\u53D6"],
        ]
      ),
    ]
  }]
});

const outPath = process.argv[2] || "detail_output.docx";
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(outPath, buf); console.log("Created: " + outPath); });

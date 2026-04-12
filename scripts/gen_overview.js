const fs = require("fs");
const path = require("path");
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
        ImageRun, Header, Footer, AlignmentType, HeadingLevel, BorderStyle,
        WidthType, ShadingType, PageNumber, PageBreak, LevelFormat } = require("docx");

const DIAG = path.join(__dirname, "diagrams");
const font = "Microsoft YaHei";

// ===== Helpers =====
const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const cm = { top: 70, bottom: 70, left: 110, right: 110 };

function hCell(text, w) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA },
    shading: { fill: "2B579A", type: ShadingType.CLEAR }, margins: cm, verticalAlign: "center",
    children: [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 0, after: 0 },
      children: [new TextRun({ text, bold: true, font, size: 20, color: "FFFFFF" })] })]
  });
}
function tCell(text, w, opts = {}) {
  return new TableCell({
    borders, width: { size: w, type: WidthType.DXA }, margins: cm,
    shading: opts.shade ? { fill: opts.shade, type: ShadingType.CLEAR } : undefined,
    verticalAlign: "center",
    children: [new Paragraph({ alignment: opts.center ? AlignmentType.CENTER : AlignmentType.LEFT,
      spacing: { before: 0, after: 0 },
      children: [new TextRun({ text, font, size: 20, bold: !!opts.bold })] })]
  });
}

function h1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 360, after: 200 }, children: [new TextRun({ text: t, bold: true, font, size: 32 })] }); }
function h2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 280, after: 160 }, children: [new TextRun({ text: t, bold: true, font, size: 28 })] }); }
function h3(t) { return new Paragraph({ heading: HeadingLevel.HEADING_3, spacing: { before: 220, after: 120 }, children: [new TextRun({ text: t, bold: true, font, size: 24 })] }); }
function p(text, opts = {}) {
  const runs = [];
  if (opts.label) runs.push(new TextRun({ text: opts.label, font, size: 21, bold: true }));
  runs.push(new TextRun({ text, font, size: 21, ...(opts.bold ? { bold: true } : {}) }));
  return new Paragraph({
    spacing: { before: 80, after: 80, line: 360 },
    indent: opts.noIndent ? undefined : { firstLine: 420 },
    children: runs
  });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: "bullets", level: 0 },
    spacing: { before: 30, after: 30, line: 340 },
    children: [new TextRun({ text, font, size: 21 })] });
}
function num(text) {
  return new Paragraph({ numbering: { reference: "numbers", level: 0 },
    spacing: { before: 50, after: 50, line: 360 },
    children: [new TextRun({ text, font, size: 21 })] });
}
function img(filename, w, h) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 120 },
    children: [new ImageRun({
      type: "png", data: fs.readFileSync(path.join(DIAG, filename)),
      transformation: { width: w, height: h },
      altText: { title: filename, description: filename, name: filename }
    })] });
}
function caption(text) {
  return new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40, after: 160 },
    children: [new TextRun({ text, font, size: 18, color: "666666", italics: true })] });
}

// ===== Document =====
const doc = new Document({
  styles: {
    default: { document: { run: { font, size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font, color: "2B579A" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font, color: "2B579A" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font, color: "404040" },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 2 } },
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
      children: [new TextRun({ text: "AI\u6A21\u62DF\u9762\u8BD5\u4E0E\u80FD\u529B\u63D0\u5347\u7CFB\u7EDF \u00B7 \u65B9\u6848\u6982\u8981", font, size: 18, color: "2B579A" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: "- ", font, size: 18, color: "888888" }),
        new TextRun({ children: [PageNumber.CURRENT], font, size: 18, color: "888888" }),
        new TextRun({ text: " -", font, size: 18, color: "888888" })] })] }) },
    children: [
      // ========== TITLE PAGE ==========
      new Paragraph({ spacing: { before: 2400 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "S1 \u65B9\u6848\u6982\u8981", bold: true, font, size: 52, color: "2B579A" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 100 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: "2B579A", space: 8 } },
        children: [new TextRun({ text: "AI\u6A21\u62DF\u9762\u8BD5\u4E0E\u80FD\u529B\u63D0\u5347\u7CFB\u7EDF", font, size: 28, color: "666666" })] }),
      new Paragraph({ spacing: { before: 600 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "\u57FA\u4E8ELLM\u5927\u8BED\u8A00\u6A21\u578B + RAG\u68C0\u7D22\u589E\u5F3A + \u591A\u6A21\u6001\u8F93\u5165", font, size: 22, color: "595959" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 40 }, children: [new TextRun({ text: "\u652F\u6301\u6587\u672C\u4E0E\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5 | \u591A\u7EF4\u5EA6\u667A\u80FD\u8BC4\u5206 | \u4E2A\u4EBA\u6210\u957F\u8FFD\u8E2A", font, size: 22, color: "595959" })] }),

      new Paragraph({ children: [new PageBreak()] }),

      // ========== 1 \u76EE\u6807\u95EE\u9898 ==========
      h1("1  \u76EE\u6807\u95EE\u9898"),

      h2("1.1  \u4E1A\u52A1\u80CC\u666F"),
      p("\u968F\u7740\u4EBA\u5DE5\u667A\u80FD\u6280\u672F\u7684\u5FEB\u901F\u53D1\u5C55\uFF0C\u5728\u7EBF\u6C42\u804C\u8BAD\u7EC3\u5E73\u53F0\u9010\u6E10\u6210\u4E3A\u63D0\u5347\u4E2A\u4EBA\u9762\u8BD5\u80FD\u529B\u7684\u91CD\u8981\u5DE5\u5177\u3002\u7136\u800C\uFF0C\u4F20\u7EDF\u9762\u8BD5\u8BAD\u7EC3\u65B9\u5F0F\u4E3B\u8981\u4F9D\u8D56\u4EBA\u5DE5\u6A21\u62DF\uFF0C\u5B58\u5728\u4EE5\u4E0B\u7A81\u51FA\u95EE\u9898\uFF1A"),
      p("\u8BAD\u7EC3\u6548\u7387\u4F4E\uFF1A", { label: "\u95EE\u9898\u4E00\uFF1A" }),
      p("\u9700\u8981\u534F\u8C03\u9762\u8BD5\u5B98\u65F6\u95F4\uFF0C\u96BE\u4EE5\u968F\u65F6\u968F\u5730\u8FDB\u884C\u7EC3\u4E60\uFF0C\u53CD\u590D\u8BAD\u7EC3\u7684\u6210\u672C\u6781\u9AD8\u3002", { noIndent: true }),
      p("\u8BC4\u4EF7\u4E3B\u89C2\u6027\u5F3A\uFF1A", { label: "\u95EE\u9898\u4E8C\uFF1A" }),
      p("\u4E0D\u540C\u9762\u8BD5\u5B98\u8BC4\u5206\u6807\u51C6\u4E0D\u4E00\uFF0C\u96BE\u4EE5\u5F62\u6210\u7EDF\u4E00\u91CF\u5316\u7684\u80FD\u529B\u8BC4\u4F30\uFF0C\u7528\u6237\u65E0\u6CD5\u5BA2\u89C2\u4E86\u89E3\u81EA\u8EAB\u6C34\u5E73\u3002", { noIndent: true }),
      p("\u53CD\u9988\u5355\u4E00\uFF1A", { label: "\u95EE\u9898\u4E09\uFF1A" }),
      p("\u4F20\u7EDF\u65B9\u5F0F\u4EC5\u63D0\u4F9B\u7B80\u5355\u7684\u8BC4\u8BED\uFF0C\u7F3A\u4E4F\u591A\u7EF4\u5EA6\u3001\u53EF\u8FFD\u8E2A\u7684\u6210\u957F\u5206\u6790\uFF0C\u7528\u6237\u65E0\u6CD5\u660E\u786E\u6539\u8FDB\u65B9\u5411\u3002", { noIndent: true }),
      p("\u56E0\u6B64\uFF0C\u672C\u9879\u76EE\u8BBE\u8BA1\u5E76\u5B9E\u73B0\u4E00\u4E2A\u57FA\u4E8E LLM \u5927\u8BED\u8A00\u6A21\u578B\u7684 AI \u6A21\u62DF\u9762\u8BD5\u7CFB\u7EDF\uFF0C\u7ED3\u5408 RAG \u68C0\u7D22\u589E\u5F3A\u751F\u6210\u3001\u591A\u6A21\u6001\u8F93\u5165\uFF08\u6587\u672C + \u8BED\u97F3\uFF09\u3001\u5B9E\u65F6\u8BED\u97F3\u5BF9\u8BDD\u7B49\u6280\u672F\uFF0C\u4E3A\u7528\u6237\u63D0\u4F9B\u667A\u80FD\u5316\u3001\u591A\u7EF4\u5EA6\u7684\u9762\u8BD5\u8BAD\u7EC3\u4E0E\u80FD\u529B\u8BC4\u4F30\u670D\u52A1\u3002"),

      h2("1.2  \u7CFB\u7EDF\u76EE\u6807"),
      num("\u6784\u5EFA AI \u9A71\u52A8\u7684\u6A21\u62DF\u9762\u8BD5\u8BAD\u7EC3\u5E73\u53F0\uFF0C\u652F\u6301\u6587\u672C\u4E0E\u5B9E\u65F6\u8BED\u97F3\u4E24\u79CD\u9762\u8BD5\u6A21\u5F0F"),
      num("\u5B9E\u73B0\u57FA\u4E8E\u5C97\u4F4D\u80FD\u529B\u7EF4\u5EA6\u4E0E\u7B80\u5386\u4FE1\u606F\u7684\u667A\u80FD\u63D0\u95EE\uFF0C\u652F\u6301\u591A\u8F6E\u8FFD\u95EE\u4E0E\u6DF1\u5165\u8FFD\u95EE"),
      num("\u901A\u8FC7 RAG \u68C0\u7D22\u589E\u5F3A\u4E0E LLM \u7ED3\u5408\uFF0C\u5BF9\u56DE\u7B54\u8FDB\u884C\u591A\u7EF4\u5EA6\u8BC4\u4EF7\uFF08\u6280\u672F\u6B63\u786E\u6027\u3001\u6DF1\u5EA6\u3001\u903B\u8F91\u3001\u5339\u914D\u5EA6\u3001\u5B8C\u6574\u5EA6\uFF09"),
      num("\u81EA\u52A8\u751F\u6210\u7EFC\u5408\u9762\u8BD5\u62A5\u544A\uFF0C\u5305\u542B\u80FD\u529B\u96F7\u8FBE\u56FE\u3001\u9010\u9898\u5206\u6790\u4E0E\u6539\u8FDB\u5EFA\u8BAE"),
      num("\u63D0\u4F9B\u4E2A\u4EBA\u6210\u957F\u8FFD\u8E2A\u529F\u80FD\uFF0C\u5C55\u793A\u591A\u6B21\u9762\u8BD5\u7684\u80FD\u529B\u53D8\u5316\u8D8B\u52BF"),

      // ========== 2 \u603B\u4F53\u601D\u8DEF ==========
      h1("2  \u603B\u4F53\u601D\u8DEF"),
      p("\u7CFB\u7EDF\u91C7\u7528\u524D\u540E\u7AEF\u5206\u79BB\u67B6\u6784\u3002\u524D\u7AEF\u57FA\u4E8E Vue 3 + TypeScript \u6784\u5EFA\u5355\u9875\u5E94\u7528\uFF0C\u540E\u7AEF\u57FA\u4E8E FastAPI\uFF08Python 3.12\uFF09\u63D0\u4F9B RESTful API \u4E0E WebSocket \u670D\u52A1\u3002\u6570\u636E\u5C42\u91C7\u7528 MySQL 8 \u5B58\u50A8\u4E1A\u52A1\u6570\u636E\u3001Milvus 2.5 \u5411\u91CF\u6570\u636E\u5E93\u652F\u6491 RAG \u68C0\u7D22\u3001Redis 7 \u63D0\u4F9B\u7F13\u5B58\u670D\u52A1\u3002AI \u80FD\u529B\u5C42\u96C6\u6210\u901A\u4E49\u5343\u95EE Qwen \u5927\u8BED\u8A00\u6A21\u578B\u7528\u4E8E\u667A\u80FD\u63D0\u95EE\u4E0E\u8BC4\u5206\u3002\u6574\u4F53\u67B6\u6784\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("architecture.png", 550, 360),
      caption("\u56FE 1  \u7CFB\u7EDF\u603B\u4F53\u67B6\u6784\u56FE"),

      p("\u5F00\u53D1\u5206\u4E3A\u56DB\u4E2A\u9636\u6BB5\uFF1A"),
      p("\u9700\u6C42\u5206\u6790\u2014\u2014\u660E\u786E\u9762\u8BD5\u6D41\u7A0B\u72B6\u6001\u673A\uFF08\u5F00\u573A\u2192\u7B80\u5386\u8FFD\u95EE\u2192\u6280\u672F\u63D0\u95EE\u2192\u6DF1\u5165\u8FFD\u95EE\u2192\u5019\u9009\u4EBA\u63D0\u95EE\u2192\u603B\u7ED3\uFF09\u3001\u591A\u7EF4\u5EA6\u8BC4\u5206\u4F53\u7CFB\u3001\u7B80\u5386\u89E3\u6790\u4E0E\u5C97\u4F4D\u80FD\u529B\u7EF4\u5EA6\u6A21\u578B\u3002", { label: "\u7B2C\u4E00\u9636\u6BB5\uFF1A" }),
      p("\u7CFB\u7EDF\u8BBE\u8BA1\u2014\u2014\u786E\u5B9A\u6280\u672F\u6808\u4E0E\u67B6\u6784\uFF0C\u8BBE\u8BA1\u6570\u636E\u5E93\u6A21\u578B\uFF08User\u3001InterviewSession\u3001InterviewQuestion \u7B49 9 \u5F20\u8868\uFF09\uFF0C\u89C4\u5212 API \u63A5\u53E3\u4E0E WebSocket \u534F\u8BAE\u3002", { label: "\u7B2C\u4E8C\u9636\u6BB5\uFF1A" }),
      p("\u7CFB\u7EDF\u5F00\u53D1\u2014\u2014\u5B9E\u73B0 FastAPI \u540E\u7AEF\u670D\u52A1\u3001\u96C6\u6210 LLM API\uFF08\u901A\u4E49\u5343\u95EE Qwen\uFF09\u3001\u6784\u5EFA Milvus \u5411\u91CF\u68C0\u7D22\u670D\u52A1\u3001\u5F00\u53D1 Vue 3 \u524D\u7AEF\u754C\u9762\u3001\u5B9E\u73B0 WebSocket \u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5\u3002", { label: "\u7B2C\u4E09\u9636\u6BB5\uFF1A" }),
      p("\u96C6\u6210\u90E8\u7F72\u2014\u2014\u901A\u8FC7 Docker Compose \u5B8C\u6210\u5168\u6808\u5BB9\u5668\u5316\u90E8\u7F72\uFF088 \u4E2A\u670D\u52A1\u5BB9\u5668\uFF09\uFF0C\u8FDB\u884C\u96C6\u6210\u6D4B\u8BD5\u4E0E\u6027\u80FD\u4F18\u5316\u3002", { label: "\u7B2C\u56DB\u9636\u6BB5\uFF1A" }),

      // ========== 3 \u5177\u4F53\u505A\u6CD5 ==========
      new Paragraph({ children: [new PageBreak()] }),
      h1("3  \u5177\u4F53\u505A\u6CD5"),
      p("\u7CFB\u7EDF\u7531 9 \u4E2A\u529F\u80FD\u6A21\u5757\u7EC4\u6210\uFF0C\u5176\u4E2D 3 \u4E2A\u6838\u5FC3\u6A21\u5757\uFF08\u6807\u8BB0 \u2605\uFF09\u662F\u7CFB\u7EDF\u7684\u6280\u672F\u6838\u5FC3\uFF0C\u5176\u4F59\u4E3A\u8F85\u52A9\u652F\u6491\u6A21\u5757\u3002\u6A21\u5757\u5168\u666F\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("modules_overview.png", 550, 200),
      caption("\u56FE 2  \u7CFB\u7EDF\u529F\u80FD\u6A21\u5757\u5168\u666F\u56FE"),

      // --- 3.1 Core: Interview ---
      h2("3.1  \u6A21\u62DF\u9762\u8BD5\u6838\u5FC3\u6A21\u5757 \u2605"),
      p("\u8BE5\u6A21\u5757\u662F\u7CFB\u7EDF\u7684\u6838\u5FC3\u5F15\u64CE\uFF0C\u7BA1\u7406\u4ECE\u521B\u5EFA\u9762\u8BD5\u5230\u751F\u6210\u62A5\u544A\u7684\u5B8C\u6574\u751F\u547D\u5468\u671F\u3002\u9762\u8BD5\u6D41\u7A0B\u91C7\u7528\u4E25\u683C\u7684\u72B6\u6001\u673A\u6A21\u578B\uFF0C\u4F9D\u6B21\u7ECF\u8FC7\u5F00\u573A\u2192\u7B80\u5386\u8FFD\u95EE\u2192\u6280\u672F\u63D0\u95EE\u2192\u6DF1\u5165\u8FFD\u95EE\u2192\u5019\u9009\u4EBA\u63D0\u95EE\u2192\u603B\u7ED3\u516D\u4E2A\u9636\u6BB5\u3002\u5176\u4E2D\u201C\u6DF1\u5165\u8FFD\u95EE\u201D\u9636\u6BB5\u6839\u636E\u56DE\u7B54\u8D28\u91CF\u52A8\u6001\u51B3\u5B9A\u8FFD\u95EE\u7B56\u7565\uFF08\u6DF1\u5316/\u8F6C\u5411/\u53EF\u4FE1\u5EA6\u9A8C\u8BC1/\u5207\u6362\u7EF4\u5EA6\uFF09\uFF0C\u6A21\u62DF\u771F\u5B9E\u9762\u8BD5\u5B98\u884C\u4E3A\u3002\u6D41\u7A0B\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("state_machine.png", 550, 250),
      caption("\u56FE 3  \u9762\u8BD5\u6D41\u7A0B\u72B6\u6001\u673A\u4E0E\u8FFD\u95EE\u7B56\u7565"),
      p("\u7CFB\u7EDF\u652F\u6301\u4E09\u79CD\u9762\u8BD5\u98CE\u683C\uFF1A\u5E38\u89C4\u6A21\u5F0F\u3001\u538B\u529B\u6A21\u5F0F\u3001\u5F15\u5BFC\u6A21\u5F0F\uFF1B\u652F\u6301\u6587\u672C\u4E0E\u8BED\u97F3\u4E24\u79CD\u7B54\u9898\u6A21\u5F0F\uFF1B\u6BCF\u573A\u9762\u8BD5\u9ED8\u8BA4 6 \u9053\u9898\uFF08\u53EF\u914D\u7F6E 5\u20138 \u9053\uFF09\u3002"),

      // --- 3.2 Core: RAG ---
      h2("3.2  RAG \u68C0\u7D22\u589E\u5F3A\u8BC4\u5206\u6A21\u5757 \u2605"),
      p("\u7CFB\u7EDF\u6784\u5EFA\u4E86\u57FA\u4E8E Milvus \u5411\u91CF\u6570\u636E\u5E93\u7684\u4E13\u4E1A\u77E5\u8BC6\u5E93\uFF0C\u89E3\u51B3\u7EAF\u4F9D\u8D56 LLM \u8BC4\u5206\u65F6\u53EF\u80FD\u51FA\u73B0\u7684\u201C\u5E7B\u89C9\u201D\u95EE\u9898\u3002\u79BB\u7EBF\u9636\u6BB5\u5C06\u4E13\u4E1A\u6587\u6863\u5206\u5757\u540E\u7ECF Qwen text-embedding-v3 \u5D4C\u5165\u4E3A 128 \u7EF4\u5411\u91CF\uFF0C\u6309\u5C97\u4F4D\u548C\u80FD\u529B\u7EF4\u5EA6\u6253\u6807\u7B7E\u540E\u5B58\u5165 Milvus\u3002\u5728\u7EBF\u8BC4\u5206\u65F6\uFF0C\u6839\u636E\u7528\u6237\u56DE\u7B54\u751F\u6210\u67E5\u8BE2\u5411\u91CF\uFF0C\u5728 Milvus \u4E2D\u6309\u5C97\u4F4D\u8FC7\u6EE4\u540E\u68C0\u7D22 Top-6 \u6700\u76F8\u4F3C\u77E5\u8BC6\u7247\u6BB5\uFF0C\u4F5C\u4E3A\u8BC4\u5206\u4F9D\u636E\u6CE8\u5165 LLM Prompt\u3002\u6D41\u7A0B\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("rag_pipeline.png", 550, 260),
      caption("\u56FE 4  RAG \u68C0\u7D22\u589E\u5F3A\u8BC4\u5206\u6D41\u7A0B"),

      // --- 3.3 Core: Scoring ---
      h2("3.3  \u591A\u7EF4\u5EA6\u8BC4\u5206\u6A21\u5757 \u2605"),
      p("\u8BC4\u5206\u6A21\u5757\u878D\u5408\u4E09\u5927\u8BC4\u5206\u6E90\uFF1A\u6587\u672C\u8BED\u4E49\u8BC4\u5206\uFF085 \u4E2A\u7EF4\u5EA6\uFF1A\u6280\u672F\u6B63\u786E\u6027\u3001\u6280\u672F\u6DF1\u5EA6\u3001\u903B\u8F91\u7ED3\u6784\u3001\u5C97\u4F4D\u5339\u914D\u5EA6\u3001\u8868\u8FBE\u5B8C\u6574\u5EA6\uFF09\u3001\u8BED\u97F3\u58F0\u5B66\u5206\u6790\uFF085 \u4E2A\u6307\u6807\uFF1A\u97F3\u91CF\u7A33\u5B9A\u6027\u3001\u505C\u987F\u6BD4\u4F8B\u3001\u8BED\u901F\u3001\u97F3\u8C03\u53D8\u5316\u3001\u6709\u58F0\u6BD4\u4F8B\uFF09\u3001RAG \u68C0\u7D22\u8BC1\u636E\u878D\u5408\u3002\u8BC4\u5206\u4F53\u7CFB\u5982\u4E0B\u56FE\u6240\u793A\uFF1A"),
      img("scoring_system.png", 550, 240),
      caption("\u56FE 5  \u591A\u7EF4\u5EA6\u8BC4\u5206\u4F53\u7CFB"),

      // --- 3.4 Other modules ---
      h2("3.4  \u8F85\u52A9\u652F\u6491\u6A21\u5757"),
      p("\u7528\u6237\u4E0E\u8BA4\u8BC1\uFF1A\u57FA\u4E8E JWT \u7684\u65E0\u72B6\u6001\u8BA4\u8BC1\uFF0C\u652F\u6301\u6CE8\u518C\u3001\u767B\u5F55\u3001\u4E2A\u4EBA\u4FE1\u606F\u7BA1\u7406\uFF0C\u5BC6\u7801 bcrypt \u54C8\u5E0C\u5B58\u50A8\u3002", { label: "\u2460 " }),
      p("\u7B80\u5386\u7BA1\u7406\uFF1A\u7528\u6237\u4E0A\u4F20\u7B80\u5386\u540E\uFF0C\u901A\u8FC7 LLM \u667A\u80FD\u89E3\u6790\u63D0\u53D6\u7ED3\u6784\u5316\u4FE1\u606F\uFF08\u6559\u80B2\u7ECF\u5386\u3001\u6280\u672F\u6808\u3001\u9879\u76EE\u7ECF\u5386\uFF09\uFF0C\u751F\u6210\u6458\u8981\u4F9B\u9762\u8BD5\u4F7F\u7528\u3002", { label: "\u2461 " }),
      p("\u5C97\u4F4D\u4E0E\u80FD\u529B\u7EF4\u5EA6\uFF1A\u9884\u7F6E\u591A\u4E2A\u5C97\u4F4D\u6A21\u677F\uFF0C\u6BCF\u4E2A\u5C97\u4F4D\u5B9A\u4E49\u591A\u4E2A\u80FD\u529B\u8BC4\u4F30\u7EF4\u5EA6\uFF08CompetencyDimension\uFF09\uFF0C\u4E3A\u667A\u80FD\u51FA\u9898\u548C\u8BC4\u5206\u63D0\u4F9B\u57FA\u7840\u3002", { label: "\u2462 " }),
      p("\u62A5\u544A\u751F\u6210\uFF1A\u9762\u8BD5\u7ED3\u675F\u540E\u901A\u8FC7\u5F02\u6B65\u4EFB\u52A1\u751F\u6210\u7EFC\u5408\u62A5\u544A\uFF0C\u5305\u542B\u80FD\u529B\u96F7\u8FBE\u56FE\u3001\u9010\u9898\u8BC4\u6790\u3001\u6539\u8FDB\u5EFA\u8BAE\u3002", { label: "\u2463 " }),
      p("\u6210\u957F\u8FFD\u8E2A\uFF1A\u57FA\u4E8E ECharts \u5C55\u793A\u591A\u6B21\u9762\u8BD5\u7684\u80FD\u529B\u53D8\u5316\u8D8B\u52BF\uFF0C\u8BC6\u522B\u8584\u5F31\u9879\u5E76\u63D0\u4F9B\u8BAD\u7EC3\u5EFA\u8BAE\u3002", { label: "\u2464 " }),
      p("\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5\uFF1A\u57FA\u4E8E WebSocket \u5168\u53CC\u5DE5\u8BED\u97F3\u5BF9\u8BDD\uFF0C\u652F\u6301 ASR \u8BED\u97F3\u8BC6\u522B\u3001TTS \u8BED\u97F3\u5408\u6210\u3001VAD \u8BED\u97F3\u6D3B\u52A8\u68C0\u6D4B\u3002", { label: "\u2465 " }),

      // ========== 4 \u521B\u65B0\u4EAE\u70B9 ==========
      h1("4  \u521B\u65B0\u4EAE\u70B9"),

      // Innovation table
      new Table({
        width: { size: 9386, type: WidthType.DXA },
        columnWidths: [600, 2200, 6586],
        rows: [
          new TableRow({ children: [hCell("\u5E8F\u53F7", 600), hCell("\u521B\u65B0\u70B9", 2200), hCell("\u5177\u4F53\u8BF4\u660E", 6586)] }),
          ...[
            ["1", "\u591A\u6A21\u6001\u9762\u8BD5\u8BC4\u4EF7", "\u878D\u5408\u6587\u672C\u8BED\u4E49\u5206\u6790\uFF085\u7EF4\u5EA6\uFF09\u4E0E\u8BED\u97F3\u58F0\u5B66\u7279\u5F81\uFF085\u6307\u6807\uFF09\uFF0C\u7A81\u7834\u5355\u4E00\u6587\u672C\u8BC4\u5206\u7684\u5C40\u9650\u6027"],
            ["2", "RAG \u68C0\u7D22\u589E\u5F3A\u8BC4\u5206", "\u57FA\u4E8E Milvus \u5411\u91CF\u6570\u636E\u5E93\u7684\u4E13\u4E1A\u77E5\u8BC6\u68C0\u7D22\uFF0C\u89E3\u51B3 LLM \u8BC4\u5206\u5E7B\u89C9\u95EE\u9898\uFF0C\u4F7F\u8BC4\u5206\u6709\u636E\u53EF\u4F9D"],
            ["3", "\u667A\u80FD\u8FFD\u95EE\u7B56\u7565", "\u56DB\u79CD\u52A8\u6001\u8FFD\u95EE\u65B9\u5411\uFF08\u6DF1\u5316/\u8F6C\u5411/\u53EF\u4FE1\u5EA6\u9A8C\u8BC1/\u5207\u6362\u7EF4\u5EA6\uFF09\uFF0C\u6A21\u62DF\u771F\u5B9E\u9762\u8BD5\u5B98\u884C\u4E3A\u800C\u975E\u56FA\u5B9A\u51FA\u9898"],
            ["4", "\u5B9E\u65F6\u8BED\u97F3\u9762\u8BD5", "WebSocket \u5168\u53CC\u5DE5\u8BED\u97F3\u5BF9\u8BDD\uFF0C\u96C6\u6210 ASR + TTS + VAD\uFF0C\u63D0\u4F9B\u6C89\u6D78\u5F0F\u9762\u8BD5\u4F53\u9A8C"],
            ["5", "\u5168\u6808\u5BB9\u5668\u5316\u90E8\u7F72", "Docker Compose \u7EDF\u4E00\u7BA1\u7406 8 \u4E2A\u670D\u52A1\u5BB9\u5668\uFF0C\u652F\u6301\u4E00\u952E\u90E8\u7F72\u4E0E\u73AF\u5883\u4E00\u81F4\u6027"],
          ].map(([n, t, d]) => new TableRow({ children: [
            tCell(n, 600, { center: true, shade: "F0F4F8" }),
            tCell(t, 2200, { bold: true }),
            tCell(d, 6586)
          ] }))
        ]
      }),
    ]
  }]
});

const outPath = process.argv[2] || "overview_output.docx";
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(outPath, buf); console.log("Created: " + outPath); });

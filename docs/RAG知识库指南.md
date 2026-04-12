# RAG 向量化与 Milvus 导入指南

本文档说明这个项目如何从 `data/` 目录的数据开始，完成数据准备、Embedding 向量化、Milvus 部署、向量导入，以及最终检索链路的接入与验证。

## 先看结论

这个项目现在有三条与 RAG 相关的主路径：

1. 构建路径：`scripts/build_kb.py`
   负责读取语料、调用 Embedding API、生成向量，并在 Milvus 可用时导入向量库。

2. 在线检索路径：`backend/app/rag/service.py`
   当前正式走 `MilvusVectorStore`，运行时检索直接依赖 Milvus。

3. 提示词消费路径：
   当前面试主链里的 `opening_question`、`answer_analysis`、`follow_up`、`score_answer` 都会接收统一的 `retrieval_context`，也就是检索证据已经真正进入大模型提示词。

这意味着：

- 你现在可以把 `data/` 下的静态语料全量导入 Milvus
- 运行时检索主路径已经切到 Milvus
- `data/build_artifacts/kb_chunks.jsonl` 仍然保留为本地构建快照和排障材料，但现在是瘦身版 summary snapshot
- 运行时如果 Milvus 异常，接口会明确返回知识库不可用，而不是再走旧的本地向量分支
- `report_summary` 和 `growth_plan` 提示词文件目前仍保留，但还没有接入运行时流程

## 一、项目里哪些目录和文件参与了 RAG

### 1. 原始数据目录（重构后的分层）

项目里与 RAG 相关的主要目录有：

- `data/content_source/` —— 唯一可编辑的知识源（人工维护）
- `data/runtime_corpus/` —— 由 `scripts/build_runtime_corpus.py` 生成的运行时权威语料
- `data/build_artifacts/` —— 构建产物与排障快照

当前真正参与向量化构建的入口只有两个：

- `data/runtime_corpus/records.jsonl`（唯一的 JSONL 主源）
- `data/content_source/question_seeds/*.json`（题目种子）

辅助文件：

- `data/runtime_corpus/manifest.json`
- `data/build_artifacts/duplicate_report.json`
- `data/build_artifacts/kb_chunks.jsonl`
- `data/build_artifacts/build_report.json`

### 2. 关键脚本

- `scripts/build_kb.py`
- `scripts/init_db.py`
- `scripts/seed_demo.py`

### 3. 关键代码

- `backend/app/ai/embeddings.py`
- `backend/app/rag/vector_store.py`
- `backend/app/rag/service.py`
- `backend/app/core/config.py`

## 二、从 0 开始部署前需要准备什么

### 1. 本机软件

建议本机先准备：

- Python 3.12
- Node.js 20+
- Docker Desktop
- PowerShell

### 2. 复制环境变量

先在项目根目录执行：

```powershell
Copy-Item .env.example .env -Force
```

### 3. 配置 `.env`

至少确认下面这些配置：

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=123456
MYSQL_DB=interview
DATABASE_URL=mysql+pymysql://root:123456@localhost:3306/interview?charset=utf8mb4

MILVUS_URI=http://localhost:19530
MILVUS_COLLECTION=interview_kb_chunks
MILVUS_TOKEN=

QWEN_BASE_URL=https://dashscope.aliyuncs.com
QWEN_API_KEY=你的Key
QWEN_EMBEDDING_MODEL=text-embedding-v3
QWEN_EMBEDDING_DIMENSION=512
```

注意：

- `QWEN_API_KEY` 必须有值，否则 `scripts/build_kb.py` 无法生成向量
- `QWEN_EMBEDDING_DIMENSION` 必须和实际 Embedding 模型输出维度一致
- 当前默认值是 `512`
- 如果你换了模型，必须同步修改 Milvus collection 的向量维度

## 三、启动 MySQL、Redis、Milvus

项目根目录已经有 `docker-compose.yml`，可以直接起基础服务。

### 1. 启动容器

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d mysql redis etcd minio milvus-standalone
```

这个命令会启动：

- MySQL
- Redis
- Etcd
- MinIO
- Milvus Standalone

Milvus 依赖 `etcd` 和 `minio`，所以不要只起 `milvus-standalone` 一个容器。

### 2. 验证 Milvus 端口

Milvus 默认暴露：

- `19530`：Milvus SDK 连接端口
- `9091`：健康与管理相关端口

可以简单确认：

```powershell
docker compose ps
```

或者：

```powershell
Test-NetConnection localhost -Port 19530
```

## 四、初始化数据库与演示数据

虽然向量化本身不依赖 MySQL 表结构，但建议把整套链路一起初始化，方便后续联调。

### 1. 初始化数据库

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

作用：

- 自动创建 `interview` 数据库
- 创建后端 ORM 定义的所有表

### 2. 导入演示用户和岗位

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

作用：

- 导入 demo 用户
- 导入岗位和能力维度

## 五、理解 `data/runtime_corpus/records.jsonl` 的结构

当前向量化脚本读取的唯一权威 JSONL：

- `data/runtime_corpus/records.jsonl`

每一行都是一个 JSON record，核心字段通常包括：

- `id`
- `role_code`
- `doc_type`
- `topic`
- `title`
- `content`
- `embedding_text`
- `source_path`

其中最关键的是：

- `embedding_text`

脚本在向量化时会优先使用：

- `embedding_text`

如果没有，才会退回：

- `content`

你可以把它理解为“专门为了检索召回优化过的文本”。

### 1. 为什么推荐用 `embedding_text`

因为它通常会把：

- 标题
- 岗位
- 文档类型
- 主题
- 关键定义
- 核心要点

组织成更适合做向量召回的文本，比直接拿原始正文更稳定。

### 2. 如果要新增数据，应该改哪里

优先改源头（编辑后必须重新跑生成脚本）：

- `data/content_source/`（人工维护的主源）

然后执行 `python scripts/build_runtime_corpus.py` 重新生成：

- `data/runtime_corpus/records.jsonl`
- `data/runtime_corpus/manifest.json`

并保持字段风格与 `data/runtime_corpus/manifest.json` 一致。

## 六、`scripts/build_kb.py` 到底做了什么

这个脚本的流程可以概括成 5 步。

### 第 1 步：选择数据源

重构后建库只走单一权威源，不再做 fallback：

- `data/runtime_corpus/records.jsonl`
- `data/content_source/question_seeds/*.json`

如果 `records.jsonl` 不存在，必须先运行 `scripts/build_runtime_corpus.py` 重新生成。首次需要重建 demo 主源时，再执行 `python scripts/seed_demo_content_source.py --force`。

### 第 2 步：规范化成 chunk 列表

脚本会把每条记录转成统一结构，大概包含：

- `id`
- `role_code`
- `doc_type`
- `competency_code`
- `title`
- `section`
- `source_path`
- `snippet`

这里的 `snippet` 就是后面真正拿去做向量化的文本。

### 第 3 步：调用 Embedding API

脚本会收集所有 `snippet`，然后一次性调用：

- `backend/app/ai/embeddings.py` 中的 `embed()`

默认请求的是 OpenAI-compatible `/embeddings` 接口。

### 第 4 步：落地本地调试文件

脚本会把结果写到：

- `data/build_artifacts/kb_chunks.jsonl`

这个文件非常重要，因为它可以让你在不连 Milvus 的情况下检查：

- 一共切了多少条 chunk
- 每条 chunk 的 title / source_path / role_code 是否正确
- `snippet` 是否已被截断到 200 字符
- `embedding_dim` 是否已经回填

### 第 5 步：Milvus 可用时导入向量库

脚本随后会尝试：

- 连接 Milvus
- 确保 collection 存在
- 插入所有向量
- 执行 flush

如果 Milvus 不可用，它不会让整个脚本报废，而是会提示：

- 本地 chunks 已写出，但 Milvus 不可用

## 七、真正执行向量化和导入

确保：

- `.env` 已配置好 `QWEN_API_KEY`
- Milvus 已启动
- Python 虚拟环境可用

然后执行：

```powershell
.\.venv\Scripts\python.exe scripts\build_kb.py
```

正常情况下你会看到类似输出：

```text
indexed N chunks into Milvus
```

如果 Milvus 没连上，可能看到类似：

```text
milvus unavailable, wrote local chunks only: ...
```

这说明：

- 向量化本身可能已经成功
- 只是没有成功写进 Milvus

## 八、Milvus collection 是怎么创建的

Milvus collection 定义在：

- `backend/app/rag/vector_store.py`

默认 collection 名：

- `interview_kb_chunks`

字段包括：

- `id`
- `role_code`
- `doc_type`
- `competency_code`
- `title`
- `source_path`
- `snippet`
- `embedding`

其中：

- `id` 是主键
- `embedding` 是 `FLOAT_VECTOR`
- 向量维度取自 `QWEN_EMBEDDING_DIMENSION`

索引策略：

- `metric_type = COSINE`
- `index_type = AUTOINDEX`

## 九、如何确认向量已经导入成功

### 方法 1：看脚本输出

最直接：

- `indexed xxx chunks into Milvus`

### 方法 2：检查本地输出文件

看：

- `data/build_artifacts/kb_chunks.jsonl`

如果这个文件已经生成，而且每条记录都有 `embedding`，说明向量化已经完成。

### 方法 3：用 Python 直接读 Milvus

可以在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -c "from pymilvus import Collection, connections; connections.connect(alias='default', uri='http://localhost:19530'); c=Collection('interview_kb_chunks'); c.load(); print(c.num_entities)"
```

如果能输出实体数量，说明导入成功。

## 十、如果你要从 `data/` 新增资料再重新向量化

推荐顺序：

1. 编辑 `data/content_source/` 下的源文件
2. 运行 `scripts/build_runtime_corpus.py` 重新生成 `data/runtime_corpus/records.jsonl`、`manifest.json`、`build_report.json` 与 `duplicate_report.json`
3. 重新执行 `scripts/build_kb.py`
4. 检查 `data/build_artifacts/kb_chunks.jsonl`
5. 再检查 Milvus collection 的 entity 数量

### 注意重复导入问题

当前脚本使用固定 `id` 作为 Milvus 主键。

如果你：

- 重复执行导入
- 且 collection 里已经有相同主键

通常会触发主键冲突。

因此常见做法有两种：

1. 开发阶段直接删除旧 collection，再重建
2. 或者保证新增记录使用全新的 `id`

如果你要彻底重建，最简单的做法是：

- 删掉旧 collection
- 再重新运行 `scripts/build_kb.py`

## 十一、从 0 到导入完成的完整命令顺序

下面是一套最稳妥的完整流程。

### 1. 复制环境变量

```powershell
Copy-Item .env.example .env -Force
```

### 2. 编辑 `.env`

确保至少填写：

- `DATABASE_URL`
- `MILVUS_URI`
- `QWEN_API_KEY`
- `QWEN_EMBEDDING_MODEL`
- `QWEN_EMBEDDING_DIMENSION`

### 3. 启动基础服务

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d mysql redis etcd minio milvus-standalone
```

### 4. 初始化数据库

```powershell
.\.venv\Scripts\python.exe scripts\init_db.py
```

### 5. 导入演示数据

```powershell
.\.venv\Scripts\python.exe scripts\seed_demo.py
```

### 6. 执行向量化与导入

```powershell
.\.venv\Scripts\python.exe scripts\build_kb.py
```

### 7. 检查本地输出

```powershell
Get-Content data\build_artifacts\kb_chunks.jsonl -TotalCount 3
```

### 8. 检查 Milvus 实体数

```powershell
.\.venv\Scripts\python.exe -c "from pymilvus import Collection, connections; connections.connect(alias='default', uri='http://localhost:19530'); c=Collection('interview_kb_chunks'); c.load(); print(c.num_entities)"
```

## 十二、常见失败原因

### 1. Embedding API 没配

现象：

- `scripts/build_kb.py` 一启动就报错
- 提示 Embedding API 未配置

解决：

- 检查 `.env` 里的 `QWEN_API_KEY`
- 检查 `QWEN_EMBEDDING_MODEL`

### 2. 维度不一致

现象：

- Milvus 插入时报向量维度错误

解决：

- 检查 `.env` 里的 `QWEN_EMBEDDING_DIMENSION`
- 确认它和真实模型输出维度一致

### 3. Milvus 没起来

现象：

- `build_kb.py` 提示 `milvus unavailable`

解决：

- 检查 `docker compose ps`
- 检查 `MILVUS_URI`
- 确认 `19530` 端口可连

### 4. 重复主键导入

现象：

- 再次导入时报主键重复

解决：

- 删除旧 collection 重建
- 或者换新的 chunk id

### 5. 语料本身字段不完整

现象：

- 导出的 `kb_chunks.jsonl` 中 title、role_code、snippet 异常

解决：

- 回查 `data/runtime_corpus/records.jsonl`
- 检查 `embedding_text`、`title`、`role_code`、`doc_type`

## 十三、当前运行时检索说明

当前在线检索默认优先使用：

- `backend/app/rag/service.py` 中的 `MilvusVectorStore`

系统运行时会：

- 先对 query 做 embedding
- 在 Milvus 中按 `role_code == 当前岗位 or role_code == common` 做检索
- 返回检索证据给面试答题评分链路

如果 Milvus 连接、load 或 search 失败：

- 接口会直接返回 `503`
- 日志会记录 `milvus retrieval failed`
- 需要优先检查 Milvus 和 Embedding 配置，而不是期待系统回退到旧的本地向量检索

也就是说：

- Milvus 是唯一运行时检索路径
- 本地快照只用于建库排障，不再承担在线检索职责
- 运行时和建库都使用统一的静态语料扫描规则

## 十四、建议的下一步

如果你的目标是“把 RAG 链路真正跑通”，建议按这个顺序继续：

1. 先保证 `scripts/build_runtime_corpus.py` + `scripts/build_kb.py` 能稳定生成 `data/build_artifacts/kb_chunks.jsonl`
2. 再保证 Milvus entity 数量正确
3. 观察运行日志，确认线上检索大多数请求都在走 `backend=milvus`
4. 稳定后继续清理历史遗留的旧命名和无引用文件

## 一句话总结

这个项目现在已经支持从 `data/` 下的静态语料全量构建向量、导入 Milvus，并在运行时直接使用 Milvus 检索。

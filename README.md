# AI 模拟面试平台

面向中文面试训练场景的 AI 练习平台，支持简历驱动的智能出题、文本/语音面试、自动追问与评分、RAG 知识库检索、结构化面试报告与成长建议。

## 核心功能

- **简历驱动面试** — 上传简历自动解析，生成岗位相关问题
- **双模式面试** — 普通文本面试 + 沉浸式语音面试
- **智能追问** — 基于回答质量自动决策追问或换题
- **多维评分** — 准确性、岗位匹配度、置信度、表达清晰度等
- **RAG 检索** — 基于 Milvus 向量数据库的知识库增强
- **面试报告** — 结构化总结 + 分维度评分 + 成长建议
- **成长追踪** — 历史趋势、薄弱环节分析、提升计划

## 技术栈

| 层次 | 技术 |
|------|------|
| 后端 | Python 3.12 / FastAPI / SQLAlchemy / Alembic |
| 前端 | Vue 3 / TypeScript / Vite / Element Plus / ECharts |
| 数据库 | MySQL 8.4 / Redis 7.4 |
| 向量数据库 | Milvus v2.5.4 (etcd + MinIO) |
| AI 服务 | 通义千问 (LLM / Embedding / ASR / TTS) |
| 部署 | Docker Compose / Nginx |


---

## 部署


### Docker 容器部署

所有服务在 Docker 容器中运。一键启动 8 个独立容器，分阶段部署并实时输出状态。


### 1. 准备环境配置

```bash
cp .env.example .env
```

编辑 `.env`，至少填入以下 API Key：

```env
QWEN_API_KEY=你的通义千问Key
```

### 2. 部署


```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh up
```



### 3. 构建知识库（首次部署）



PowerShell 执行：

```bash
docker exec interview_backend python /app/scripts/build_kb.py
```

> 更新 `data/content_source/` 目录下的文档后，先运行 `python scripts/build_runtime_corpus.py` 重新生成 `data/runtime_corpus/` 与 `data/build_artifacts/`；如果你要整套重置 demo 主源，再执行 `python scripts/seed_demo_content_source.py --force`。`scripts/generate_demo_rag_data.py` 仍可用，但现在只是兼容入口。

### 4. 访问服务

| 地址 | 说明 |
|------|------|
| http://localhost | 前端页面 |
| http://localhost/docs | Swagger API 文档 |
| http://localhost/redoc | ReDoc API 文档 |

---


详细说明请参阅 **[Docker 部署指南](docs/Docker部署指南.md)**




## 文档

- [Docker 部署指南](docs/Docker部署指南.md) — 容器部署、运维、验证（推荐）
- [RAG 知识库指南](docs/RAG知识库指南.md) — 向量化与 Milvus 导入
- [Data Asset Inventory](docs/data-asset-inventory.md) — data/ 目录资产归属与数据流
- [Data Record Schema](docs/data-record-schema.md) — runtime_corpus/records.jsonl 字段说明
- [接口参考](docs/接口参考.md) — 接口列表与返回格式
- [系统架构](docs/系统架构.md) — 架构图与主链路说明
- [故障排查](docs/故障排查.md) — 错误码与调试方法

# Docker 容器部署指南

本文档详细说明如何通过 Docker Compose 一键部署 AI 模拟面试平台的全部服务。

---

## 环境要求

- Docker Engine 24+
- Docker Compose V2（Docker Desktop 已内置）
- 最低配置：4 核 CPU / 8 GB 内存 / 20 GB 磁盘

---


## 快速开始

### 1. 准备环境配置

```bash
cp .env.example .env
```

编辑 `.env`，至少填入以下 API Key：

```env
QWEN_API_KEY=你的通义千问Key
```

> `.env.example` 默认使用 Docker Hub / Quay 官方镜像。如需切换到其他仓库，可覆盖 `PYTHON_BASE_IMAGE`、`NODE_BASE_IMAGE`、`MYSQL_IMAGE`、`REDIS_IMAGE`、`ETCD_IMAGE`、`MINIO_IMAGE`、`MILVUS_IMAGE`、`NGINX_IMAGE`。

### 2. 一键部署

推荐使用部署脚本，会分阶段启动并输出每个服务的部署状态：

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh up
```



### 3. 构建知识库（首次部署）

如果你在 Windows 的 Git Bash / MINGW64 中执行 `docker exec`，`/app/...` 这类容器内路径可能会被自动改写成宿主机 Windows 路径，导致类似下面的报错：

```text
python: can't open file '/app/C:/Program Files/Git/app/scripts/build_kb.py'
```

此时请关闭路径自动转换后再执行：

```bash
MSYS_NO_PATHCONV=1 docker exec interview_backend python /app/scripts/build_kb.py
```

PowerShell / CMD 可直接执行：

```bash
docker exec interview_backend python /app/scripts/build_kb.py
```

> 更新 `data/content_source/` 目录下的文档后，先运行 `python scripts/build_runtime_corpus.py` 重新生成 `data/runtime_corpus/` 与 `data/build_artifacts/`，再执行此命令重建向量库。如果你要整套重置 demo 主源，运行 `python scripts/seed_demo_content_source.py --force`。`scripts/generate_demo_rag_data.py` 现在只是兼容别名。

### 4. 访问服务

| 地址 | 说明 |
|------|------|
| http://localhost | 前端页面 |
| http://localhost/docs | Swagger API 文档 |
| http://localhost/redoc | ReDoc API 文档 |

---


## 服务架构

部署共包含 **8 个独立容器**，通过自定义网络 `interview_network` 互联：

```
用户浏览器 → interview_nginx:80
  ├─ /api/*        → interview_backend:8000
  ├─ /uploads/*    → interview_backend:8000
  ├─ /docs,/redoc  → interview_backend:8000
  └─ /*            → interview_frontend:4173

interview_backend:8000
  ├─ → interview_mysql:3306      (关系型数据)
  ├─ → interview_redis:6379      (缓存)
  └─ → interview_milvus:19530    (向量检索)

interview_milvus:19530
  ├─ → interview_etcd:2379       (元数据)
  └─ → interview_minio:9000      (对象存储)
```

### 容器清单

| 容器名 | 镜像 | 作用 | 端口(容器内) |
|--------|------|------|-------------|
| interview_mysql | mysql:8.4 | 业务数据库 | 3306 |
| interview_redis | redis:7.4-alpine | 缓存与会话 | 6379 |
| interview_etcd | quay.io/coreos/etcd:v3.5.5 | Milvus 元数据 | 2379 |
| interview_minio | minio/minio:RELEASE.2024-12-18T13-15-44Z | Milvus 对象存储 | 9000 |
| interview_milvus | milvusdb/milvus:v2.5.4 | 向量数据库 (RAG) | 19530 |
| interview_backend | 自构建 (Python 3.12 + FastAPI) | 后端 API | 8000 |
| interview_frontend | 自构建 (Node + Vue3) | 前端页面 | 4173 |
| interview_nginx | nginx:1.27-alpine | 反向代理网关 | 80 |

### 端口策略

- **仅 `interview_nginx` 暴露 80 端口到宿主机**
- 其余所有容器不映射任何端口，完全隔离在 Docker 内网
- 即使宿主机已运行 MySQL / Redis / Milvus，也不会端口冲突

### 命名策略

所有资源统一 `interview_` 前缀（容器名、服务名、卷名、网络名），不会与宿主机已有容器冲突。

### 数据持久化

| 卷名 | 挂载路径 | 说明 |
|------|---------|------|
| interview_mysql_data | /var/lib/mysql | MySQL 数据 |
| interview_redis_data | /data | Redis AOF 持久化 |
| interview_etcd_data | /etcd | etcd 元数据 |
| interview_minio_data | /minio_data | MinIO 对象数据 |
| interview_milvus_data | /var/lib/milvus | Milvus 向量数据 |
| ./data (bind mount) | /app/data | 知识主源、运行时语料、构建报告、演示数据 |

---

## 运维命令

### 使用部署脚本

```bash
# 完整部署
./deploy/deploy.sh up

# 停止所有服务（保留数据卷）
./deploy/deploy.sh down

# 查看所有容器状态
./deploy/deploy.sh status

# 查看全部日志
./deploy/deploy.sh logs

# 查看单个服务日志
./deploy/deploy.sh logs interview_backend

# 重启指定服务
./deploy/deploy.sh restart interview_backend

# 验证 backend 到各服务的连通性
./deploy/deploy.sh verify
```

### 直接使用 docker compose

```bash
# 查看所有容器状态
docker compose ps

# 查看后端实时日志
docker compose logs -f interview_backend

# 重启单个服务
docker compose restart interview_backend

# 停止并保留数据卷
docker compose down

# 停止并删除所有数据（慎用）
docker compose down -v
```

### 进入容器

```bash
# 进入后端容器
docker exec -it interview_backend bash

# 进入 MySQL 命令行
docker exec -it interview_mysql mysql -uroot -p123456

# 进入 Redis 命令行
docker exec -it interview_redis redis-cli
```

---

## 连通性验证

使用部署脚本一键验证：

```bash
./deploy/deploy.sh verify
```

或手动验证：

```bash
# 验证 MySQL
docker exec interview_backend python -c "
from app.db.session import engine
with engine.connect() as conn:
    conn.execute(__import__('sqlalchemy').text('SELECT 1'))
print('MySQL OK')
"

# 验证 Redis
docker exec interview_backend python -c "
import redis
r = redis.from_url('redis://interview_redis:6379/0')
r.ping()
print('Redis OK')
"

# 验证 Milvus
docker exec interview_backend python -c "
from pymilvus import connections
connections.connect(uri='http://interview_milvus:19530')
print('Milvus OK')
connections.disconnect('default')
"
```

---

## 常见问题

### 宿主机 80 端口被占用

修改 `docker-compose.yml` 中 `interview_nginx` 的端口映射：

```yaml
ports:
  - "8080:80"  # 改为 8080 或其他可用端口
```

然后通过 `http://localhost:8080` 访问。

### 构建镜像很慢

如果官方仓库拉取不稳定，可以在 `.env` 中覆盖以下变量：

```env
PYTHON_BASE_IMAGE=python:3.12-slim
NODE_BASE_IMAGE=node:24-alpine
MYSQL_IMAGE=mysql:8.4
REDIS_IMAGE=redis:7.4-alpine
ETCD_IMAGE=quay.io/coreos/etcd:v3.5.5
MINIO_IMAGE=minio/minio:RELEASE.2024-12-18T13-15-44Z
MILVUS_IMAGE=milvusdb/milvus:v2.5.4
NGINX_IMAGE=nginx:1.27-alpine
```

例如优先使用 DaoCloud Mirror，但 `etcd` 保持官方 `quay.io`，避免部分镜像站对该路径返回 403：

```env
PYTHON_BASE_IMAGE=docker.m.daocloud.io/python:3.12-slim
NODE_BASE_IMAGE=docker.m.daocloud.io/library/node:24-alpine
MYSQL_IMAGE=docker.m.daocloud.io/library/mysql:8.4
REDIS_IMAGE=docker.m.daocloud.io/library/redis:7.4-alpine
ETCD_IMAGE=quay.io/coreos/etcd:v3.5.5
MINIO_IMAGE=docker.m.daocloud.io/minio/minio:RELEASE.2024-12-18T13-15-44Z
MILVUS_IMAGE=docker.m.daocloud.io/milvusdb/milvus:v2.5.4
NGINX_IMAGE=docker.m.daocloud.io/library/nginx:1.27-alpine
```

### 如何重建单个服务

```bash
docker compose up -d --build --force-recreate interview_backend
```

### 如何清理旧数据重新部署

```bash
# 停止并删除所有容器和卷
docker compose down -v

# 重新部署
./deploy/deploy.sh up

# 重建知识库
# Git Bash / MINGW64
MSYS_NO_PATHCONV=1 docker exec interview_backend python /app/scripts/build_kb.py

# PowerShell / CMD
docker exec interview_backend python /app/scripts/build_kb.py
```

### 面试时报 “Milvus collection 缺失：interview_kb_chunks”

这通常表示 Milvus 已启动，但知识库还没有成功写入 collection。按下面顺序处理：

```bash
# 1. 确认 Milvus 容器健康
docker compose ps

# 2. 重建知识库
# Git Bash / MINGW64
MSYS_NO_PATHCONV=1 docker exec interview_backend python /app/scripts/build_kb.py

# PowerShell / CMD
docker exec interview_backend python /app/scripts/build_kb.py

# 3. 验证 collection 是否已创建
docker exec interview_backend python -c "from pymilvus import connections, utility; connections.connect(uri='http://interview_milvus:19530'); print(utility.has_collection('interview_kb_chunks')); connections.disconnect('default')"
```

如果最后输出 `True`，就可以重新开始面试。

### QWEN_EMBEDDING_DIMENSION 变更后

修改 `QWEN_EMBEDDING_DIMENSION` 后必须重建 Milvus collection：

```bash
# 删除旧 collection
docker exec interview_backend python -c "
from pymilvus import connections, utility
connections.connect(uri='http://interview_milvus:19530')
utility.drop_collection('interview_kb_chunks')
print('collection dropped')
"

# Git Bash / MINGW64 重建
MSYS_NO_PATHCONV=1 docker exec interview_backend python /app/scripts/build_kb.py

# PowerShell / CMD 重建
docker exec interview_backend python /app/scripts/build_kb.py
```

<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

## 🚀 快速开始

### 一、源码部署（推荐）

#### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|---------|------|---------|
| **Node.js** | 18+ | 前端运行环境，包含 npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | 后端运行环境 | `python --version` |
| **uv** | 最新版 | Python 包管理器 | `uv --version` |

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cp .env.example .env

# 编辑项目根目录 .env
```

根目录 `.env` 是唯一的手动配置入口。数据库、Chroma、Embedding、World Info 与运行参数都在这里配置，不需要再修改 `backend/application.yml`。

**完整环境变量清单：**

```env
# ===== 基础运行 =====
SECRET_KEY=mirofish-secret-key
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# ===== LLM =====
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
LLM_DEFAULT_MAX_TOKENS=4096

# ===== 可选 LLM 加速 =====
LLM_BOOST_API_KEY=your_boost_api_key
LLM_BOOST_BASE_URL=your_boost_base_url
LLM_BOOST_MODEL_NAME=your_boost_model_name

# ===== Zep =====
ZEP_API_KEY=your_zep_api_key

# ===== MySQL =====
DATASOURCE_URL=jdbc:mysql://127.0.0.1:3306/mirofish?useUnicode=true&characterEncoding=utf8&serverTimezone=Asia/Shanghai
DATASOURCE_USERNAME=root
DATASOURCE_PASSWORD=123456

# ===== Chroma =====
CHROMA_MODE=persistent
CHROMA_PERSIST_DIRECTORY=backend/uploads/chroma
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
CHROMA_COLLECTION_NAME=world_info

# ===== Embedding =====
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5
EMBEDDING_BATCH_SIZE=16

# ===== World Info =====
WORLD_INFO_ENABLED=true
WORLD_INFO_CHUNK_SIZE=1200
WORLD_INFO_CHUNK_OVERLAP=200
WORLD_INFO_SEARCH_TOP_K=8
SIMULATION_CONTEXT_BUDGET_CHARS=50000
REPORT_CONTEXT_BUDGET_CHARS=20000
WORLD_INFO_INJECTION_CHARS=12000

# ===== 运行调优 =====
OASIS_DEFAULT_MAX_ROUNDS=10
REPORT_AGENT_MAX_TOOL_CALLS=5
REPORT_AGENT_MAX_REFLECTION_ROUNDS=2
REPORT_AGENT_TEMPERATURE=0.5
```

**Chroma 配置方式：**

```env
# 本地持久化模式
CHROMA_MODE=persistent
CHROMA_PERSIST_DIRECTORY=backend/uploads/chroma
```

```env
# 外部 Chroma 服务模式
CHROMA_MODE=http
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
```

#### 2. 安装依赖

```bash
# 一键安装所有依赖（根目录 + 前端 + 后端）
npm run setup:all
```

或者分步安装：

```bash
# 安装 Node 依赖（根目录 + 前端）
npm run setup

# 安装 Python 依赖（后端，自动创建虚拟环境）
npm run setup:backend
```

#### 3. 启动服务

```bash
# 同时启动前后端（在项目根目录执行）
npm run dev
```

**服务地址：**
- 前端：`http://localhost:3000`
- 后端 API：`http://localhost:5001`

**单独启动：**

```bash
npm run backend   # 仅启动后端
npm run frontend  # 仅启动前端
```

### 二、Docker 部署

```bash
# 1. 配置环境变量（同源码部署）
cp .env.example .env

# 2. 拉取镜像并启动
docker compose up -d
```

默认会读取项目根目录下的 `.env`，并映射端口 `3000（前端）/5001（后端）`。如果使用 `CHROMA_MODE=persistent`，Chroma 数据默认持久化到 `backend/uploads/chroma`，会被现有 volume 一并挂载。

> 在 `docker-compose.yml` 中已通过注释提供加速镜像地址，可按需替换

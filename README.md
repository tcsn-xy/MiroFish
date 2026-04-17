<div align="center">

<img src="./static/image/MiroFish_logo_compressed.jpeg" alt="MiroFish Logo" width="75%"/>

## 🚀 Quick Start

### Option 1: Source Code Deployment (Recommended)

#### Prerequisites

| Tool | Version | Description | Check Installation |
|------|---------|-------------|-------------------|
| **Node.js** | 18+ | Frontend runtime, includes npm | `node -v` |
| **Python** | ≥3.11, ≤3.12 | Backend runtime | `python --version` |
| **uv** | Latest | Python package manager | `uv --version` |

#### 1. Configure Environment Variables

```bash
# Copy the example configuration file
cp .env.example .env

# Edit the root .env file
```

The repository-root `.env` is the only manual configuration entrypoint. Database, Chroma, embedding, World Info, and runtime tuning are all configured there. You no longer need to edit `backend/application.yml`.

**Full Environment Variable List:**

```env
# ===== Base runtime =====
SECRET_KEY=mirofish-secret-key
FLASK_DEBUG=True
FLASK_HOST=0.0.0.0
FLASK_PORT=5001

# ===== LLM =====
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL_NAME=qwen-plus
LLM_DEFAULT_MAX_TOKENS=4096

# ===== Optional LLM boost =====
LLM_BOOST_API_KEY=your_boost_api_key
LLM_BOOST_BASE_URL=your_boost_base_url
LLM_BOOST_MODEL_NAME=your_boost_model_name

# ===== Zep =====
ZEP_API_KEY=your_zep_api_key

# ===== MySQL datasource =====
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

# ===== Runtime tuning =====
OASIS_DEFAULT_MAX_ROUNDS=10
REPORT_AGENT_MAX_TOOL_CALLS=5
REPORT_AGENT_MAX_REFLECTION_ROUNDS=2
REPORT_AGENT_TEMPERATURE=0.5
```

**Chroma Modes:**

```env
# Local persistent mode
CHROMA_MODE=persistent
CHROMA_PERSIST_DIRECTORY=backend/uploads/chroma
```

```env
# External Chroma server mode
CHROMA_MODE=http
CHROMA_HOST=127.0.0.1
CHROMA_PORT=8000
```

#### 2. Install Dependencies

```bash
# One-click installation of all dependencies (root + frontend + backend)
npm run setup:all
```

Or install step by step:

```bash
# Install Node dependencies (root + frontend)
npm run setup

# Install Python dependencies (backend, auto-creates virtual environment)
npm run setup:backend
```

#### 3. Start Services

```bash
# Start both frontend and backend (run from project root)
npm run dev
```

**Service URLs:**
- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

**Start Individually:**

```bash
npm run backend   # Start backend only
npm run frontend  # Start frontend only
```

### Option 2: Docker Deployment

```bash
# 1. Configure environment variables (same as source deployment)
cp .env.example .env

# 2. Pull image and start
docker compose up -d
```

Reads the repository-root `.env` by default and maps ports `3000 (frontend) / 5001 (backend)`. When `CHROMA_MODE=persistent`, Chroma data is stored under `backend/uploads/chroma`, which remains covered by the existing volume mapping.

> Mirror address for faster pulling is provided as comments in `docker-compose.yml`, replace if needed.

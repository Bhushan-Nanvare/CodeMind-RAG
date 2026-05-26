# CodeMind RAG

**Natural-language Q&A over GitHub repositories** — index a public repository, ask questions in plain language, and receive answers with **file paths, line ranges, and code citations**. Retrieval combines **hybrid search** (dense embeddings plus keyword signals, fused with reciprocal rank fusion). Answers are produced with **Groq** (`llama-3.1-70b-versatile`) when configured, with deterministic fallbacks when API keys are not set.

---

## Features

- **Ingestion** — Clone a GitHub URL and branch, filter and chunk source code, embed, and store vectors in Qdrant (or an in-memory fallback).
- **Hybrid search** — Semantic retrieval (MiniLM-class embeddings) plus in-process keyword scoring, merged with reciprocal rank fusion.
- **RAG answers** — Context-grounded responses with citations; optional Groq-backed generation or a local mock when no key is present.
- **Web UI** — Next.js 14 (App Router): repository URL input, ingestion progress, and chat-style Q&A connected to the API.

---

## Repository layout

| Path | Role |
|------|------|
| [`apps/api`](apps/api) | FastAPI service — ingest, search, query, health. |
| [`apps/web`](apps/web) | Next.js frontend (`@workspace/web`). |
| [`apps/mockup-sandbox`](apps/mockup-sandbox) | Optional Vite sandbox for UI experiments. |
| [`apps/api-server`](apps/api-server) | Optional Node API scaffold (workspace package). |
| [`doc/`](doc) | Maintainer notes and documentation index. |
| [`lib/`](lib) | Shared TypeScript libraries for workspace packages. |

---

## Quick start

### Prerequisites

- **Node.js** 20+ and **pnpm** 9+ (the root `preinstall` script enforces pnpm via `scripts/ensure-pnpm.cjs`).
- **Python** 3.11+ for the API (`apps/api` uses `requirements.txt`; the repository root includes `pyproject.toml` and `uv.lock` for workspace-level Python tooling).

### 1. Install JavaScript dependencies (monorepo root)

```bash
pnpm install
```

### 2. API — virtual environment, dependencies, configuration

```bash
cd apps/api
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env   # Windows; use cp on Unix
# Edit .env: QDRANT_*, HUGGINGFACE_API_KEY, GROQ_API_KEY (all optional — mocks apply when missing)
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Web — development server

From the **monorepo root**:

```bash
pnpm --filter @workspace/web dev
```

Open [http://localhost:3000](http://localhost:3000). Point the UI at your API (default `http://localhost:8000`) using `NEXT_PUBLIC_BACKEND_URL` in `apps/web/.env.local` if needed.

### 4. Typecheck and tests

```bash
pnpm run typecheck
cd apps/api && pytest tests/ -v
```

---

## Environment variables

Configure **`apps/api/.env`** (start from [`apps/api/.env.example`](apps/api/.env.example) when available).

| Variable | Purpose |
|----------|---------|
| `QDRANT_URL` / `QDRANT_API_KEY` | Qdrant Cloud (optional; in-memory fallback). |
| `HUGGINGFACE_API_KEY` | Real embeddings via the Hugging Face Inference API (optional; deterministic mock vectors otherwise). |
| `GROQ_API_KEY` | LLM-backed answers (optional; pattern-based mock otherwise). |

Frontend (optional), for example `apps/web/.env.local`:

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_BACKEND_URL` | Base URL of the FastAPI application (default `http://localhost:8000`). |

All listed API keys and external services are **optional**. If a dependency is missing or unreachable, the stack uses the documented mock or in-process fallback so the full pipeline remains runnable for local development.

---

## HTTP API (summary)

Routes are served under the `/api/...` prefix (see `apps/api/routers/`). Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while the API is running.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health and dependency status. |
| `POST` | `/api/ingest` | Start an ingestion job (`202` and `job_id`). |
| `GET` | `/api/ingest/status/{job_id}` | Poll ingestion progress. |
| `POST` | `/api/search` | Hybrid search (JSON body). |
| `GET` | `/api/search/repos` | List indexed repository names. |
| `POST` | `/api/query` | RAG question, answer, sources, and citations. |

---

## System overview

High-level data flow:

```
┌─────────────────────────────────────────────────────────┐
│                   Next.js 14 frontend                   │
│  Repo input  │  Chat UI  │  Code viewer  │  File tree   │
└──────────────────────────┬──────────────────────────────┘
                           │  HTTP (Axios)
┌──────────────────────────▼──────────────────────────────┐
│              FastAPI backend (Python)                    │
│                                                          │
│  /api/ingest  →  clone / filter  →  chunk  →  embed     │
│                        ↓              ↓         ↓      │
│                 Keyword index     Vector store (Qdrant)│
│                                                          │
│  /api/query  →  hybrid search  →  LLM  →  citations     │
│                    (RRF k=60)                            │
└──────────────────────────────────────────────────────────┘
```

---

## Technology stack

| Layer | Technology |
|-------|------------|
| Frontend | Next.js 14, React 18, Tailwind CSS v4, Monaco Editor |
| Backend | FastAPI, Python 3.11, Uvicorn |
| Vector database | Qdrant (cloud or in-memory fallback) |
| Embeddings | Hugging Face Inference API — `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions) |
| LLM | Groq — `llama-3.1-70b-versatile` |
| Chunking | LangChain `RecursiveCharacterTextSplitter` and custom separators |
| Keyword layer | In-process TF-IDF (`KeywordIndex`) |
| Search fusion | Reciprocal rank fusion (k = 60) |
| HTTP | `httpx` (backend), Axios (frontend) |
| Logging | `structlog` (JSON structured logs) |

---

## Project structure

```
apps/
├── web/                    # Next.js 14 (@workspace/web)
│   ├── app/                # App Router
│   ├── features/rag/     # Ingestion and chat UI
│   ├── components/       # Shared UI
│   ├── lib/              # API client and constants
│   └── types/
└── api/                    # FastAPI service
    ├── main.py
    ├── config.py
    ├── routers/          # health, ingest, search, query
    ├── services/
    ├── models/
    ├── utils/
    └── tests/

lib/                        # Shared TypeScript packages
doc/                        # Index and maintainer notes (see doc/README.md)
```

---

## Optional services and fallbacks

```
QDRANT_URL + QDRANT_API_KEY  →  Qdrant Cloud
  (missing or unreachable)   →  in-memory Qdrant client

HUGGINGFACE_API_KEY          →  Hugging Face Inference API (384-dimensional embeddings)
  (missing or error)         →  deterministic mock embedding vector

GROQ_API_KEY                 →  Groq chat completion
  (missing or error)         →  local mock answer path (no external LLM)
```

---

## Search and retrieval

1. **Semantic search** — Embed the query with the configured embedding model; retrieve top candidates from the vector store by cosine similarity.
2. **Keyword search** — Tokenize the query, score chunks with TF-IDF, and return a ranked list.
3. **Fusion** — Combine both ranked lists with reciprocal rank fusion: for each chunk, `score += 1 / (60 + rank)` from each list, then sort by combined score.

---

## Ingestion pipeline

```
GitHub URL
  → git clone (branch-specific)
  → file filter (allowed extensions, size limits, common vendor and test exclusions)
  → RecursiveCharacterTextSplitter (chunk size and overlap as configured)
  → token and quality filters
  → function-name hints (AST or regex where applicable)
  → batch embedding → vector upserts and keyword index updates
  → progress reporting for the UI
```

---

## RAG pipeline

```
User question
  → hybrid_search (top chunks, optional repository filter)
  → context formatting (file paths and line-bounded code blocks)
  → LLM (system and user prompts) or mock path
  → citation extraction from model output
  → response payload (answer, citations, sources, confidence)
```

---

## Web interface

The default layout is a three-column IDE-style view: repository input and file tree on the left, chat in the center, and Monaco-based code viewing with citation highlights on the right. Narrow viewports use a tabbed layout with a client-side mount guard to avoid hydration mismatches.

---

## Documentation and maintainers

| Resource | Contents |
|----------|----------|
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Issues, pull requests, checks, and coding expectations. |
| [`doc/README.md`](doc/README.md) | Index of `doc/` (links back to this file). |

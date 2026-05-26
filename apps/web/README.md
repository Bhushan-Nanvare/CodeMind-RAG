# CodeMind RAG — Web application

Next.js frontend for natural-language Q&A over indexed repositories, backed by the FastAPI service in `apps/api`.

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Next.js 14 (App Router) + TypeScript strict mode |
| **Styling** | Tailwind CSS v4 |
| **UI** | Tailwind-based layout; feature code under `features/rag/` |
| **Code Viewer** | Monaco Editor (VS Code engine) |
| **Backend** | FastAPI (Python 3.11+) |
| **Vector DB** | Qdrant (cloud or in-memory fallback) |
| **LLM** | Groq llama-3.1-70b-versatile |
| **Embeddings** | sentence-transformers/all-MiniLM-L6-v2 |

## Setup

### Frontend

```bash
pnpm install
pnpm --filter @workspace/web run dev
```

### Environment Variables

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_API_TIMEOUT=30000
NEXT_PUBLIC_MAX_QUERY_LENGTH=500
```

### Backend (FastAPI in `apps/api`)

```bash
cd apps/api
python -m venv venv
# Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Status

Ingestion, hybrid search, `/api/query`, and this UI are documented in the repository root [`README.md`](../../README.md).

## Features

- Natural language Q&A over code repositories
- Hybrid search combining vector and keyword matching
- Real-time code exploration with syntax highlighting
- Support for multiple programming languages

## Architecture

```
User Question
    │
    ▼
Next.js 14 Frontend (App Router)
    │
    ▼ HTTPS REST API
FastAPI Backend (Python 3.11+)
    │
    ├─ Qdrant (vector storage) + in-process keyword (TF-IDF) + RRF
    │
    └─ Groq (LLM) or configured fallback
```

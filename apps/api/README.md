# CodeMind RAG — Backend API

FastAPI backend for the CodeMind RAG codebase search engine.

## Setup

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env
```

## Running

```bash
# Development (auto-reload)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check with service statuses |
| POST | `/api/ingest` | Submit a GitHub repo for ingestion |
| GET | `/api/ingest/status/{job_id}` | Poll ingestion job status |

## Testing with curl

```bash
# Health check
curl http://localhost:8000/api/health

# Submit valid repo
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"https://github.com/facebook/react","branch":"main"}'

# Test bad URL (should return 422)
curl -X POST http://localhost:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"repo_url":"invalid"}'

# Poll status
curl http://localhost:8000/api/ingest/status/<job_id>

# CORS test
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS http://localhost:8000/api/ingest -v
```

## Project Structure

```
apps/api/
├── main.py              # FastAPI app entry point
├── config.py            # Environment configuration (Pydantic Settings)
├── requirements.txt     # Pinned Python dependencies
├── routers/
│   ├── health.py        # GET /api/health
│   ├── ingest.py        # POST /api/ingest, GET /api/ingest/status/{id}
│   ├── search.py        # POST /api/search, GET /api/search/repos
│   └── query.py         # POST /api/query
├── services/            # repo_cloner, file_filter, ingestion, chunking,
│                        # embeddings, vector_db, hybrid_search, RAG helpers, ...
├── models/
│   └── schemas.py       # Pydantic v2 request/response models
└── utils/
    └── logger.py        # structlog setup
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_TOKEN` | — | GitHub PAT for private repos / higher rate limits |
| `MAX_REPO_SIZE` | `500` | Max repo size in MB |
| `MAX_FILES` | `5000` | Max number of code files to index |
| `TEMP_DIR` | `./temp` | Directory for cloned repos |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `BACKEND_URL` | `http://localhost:8000` | Public API base URL |

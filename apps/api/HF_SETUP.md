# HuggingFace Inference API Setup

## Overview

CodeMind RAG uses `sentence-transformers/all-MiniLM-L6-v2` to generate 384-dim
semantic embeddings for code chunks.

**Without an API key**, the system falls back to a **local mock** embedding
mode that generates deterministic (but not semantically meaningful) vectors.
The full ingestion pipeline still runs — you just won't get semantic search
until a real key is provided.

**With an API key**, every chunk gets a real embedding via HuggingFace's free
Inference API, enabling genuine semantic similarity search in Phase 6+.

---

## Step 1 — Create a HuggingFace Account

1. Go to [huggingface.co](https://huggingface.co)
2. Click **Sign Up** → use GitHub, Google, or email (free)

---

## Step 2 — Create an Access Token

1. Go to [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
2. Click **New token**
3. Name it `codemind-backend`
4. Role: **Read** (sufficient for Inference API)
5. Click **Generate a token**
6. Copy the token — it starts with `hf_`

---

## Step 3 — Set the secret locally

In `apps/api/.env` (or your process environment), add:

```
HUGGINGFACE_API_KEY = hf_your_token_here
```

Restart the backend after saving. The health endpoint will show:

```json
"huggingface": "connected"
```

---

## Step 4 — Verify

```bash
curl -s http://localhost:8000/api/health | python3 -m json.tool
```

Expected:
```json
{
  "services": {
    "huggingface": "connected",
    "qdrant": "in-memory"
  }
}
```

---

## Free Tier Limits

| Resource | Limit |
|----------|-------|
| API requests | ~1,000 requests/day |
| Model | all-MiniLM-L6-v2 (384-dim, fast) |
| Batch size | 16 texts per request |
| Timeout | 30s per request (auto-retry ×3) |

For repos with >1,000 chunks, Phase 5 uses in-memory caching so repeated
ingestion of the same repo incurs far fewer API calls.

---

## Current Behaviour Without API Key

| Feature | Local Mock Mode |
|---------|----------------|
| Ingestion pipeline | ✅ Fully works |
| Vector storage | ✅ In-memory Qdrant |
| Embedding dimensions | ✅ 384-dim |
| Semantic search | ❌ Not semantically meaningful |
| Deterministic vectors | ✅ Same text → same vector |
| API quota usage | ✅ Zero |

The mock uses SHA-256 hashing to create unit-normalised 384-dim vectors.
Everything in the pipeline runs normally — just swap in the real key for
genuine semantic similarity.

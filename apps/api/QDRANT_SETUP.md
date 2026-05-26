# Qdrant Cloud Setup Guide

## Step 1 — Create a Free Qdrant Cloud Account

1. Go to [cloud.qdrant.io](https://cloud.qdrant.io)
2. Sign up with GitHub or email (no credit card required)
3. Click **"Create Cluster"** → choose the **Free** tier (1GB storage)
4. Select region: `us-east` or closest to your backend deployment
5. Name your cluster: `codemind-rag`
6. Wait ~2 minutes for the cluster to provision

## Step 2 — Get Your Credentials

1. On the cluster dashboard, click your cluster name
2. Copy the **Cluster URL** — looks like:
   `https://xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx.us-east4-0.gcp.cloud.qdrant.io`
3. Click **API Keys** → **Create API Key**
4. Name it `codemind-backend`, copy the key (you won't see it again)

## Step 3 — Set environment variables

In `apps/api/.env` (or your deployment secrets), set:

```
QDRANT_URL    = https://your-cluster-url.cloud.qdrant.io
QDRANT_API_KEY = your-api-key-here
```

## Step 4 — Collection Setup (Automatic)

The backend automatically creates the `codemind-codebase` collection on first
ingestion. No manual setup needed. Collection config:
- **Dimension**: 384 (matching all-MiniLM-L6-v2 embeddings)
- **Distance**: Cosine similarity
- **Metadata fields**: file_path, start_line, end_line, language, function_name, repo_name

## Step 5 — Verify Connection

Check the health endpoint after setting secrets:

```bash
curl http://localhost:8000/api/health
```

You should see `"qdrant": "connected"` in the response.

## Notes

- **Free tier**: 1GB storage ≈ ~15,000 code chunks
- Configure `HUGGINGFACE_API_KEY` for production-style dense embeddings when you are ready.
- Hybrid retrieval in this service combines dense vectors in Qdrant with an in-process keyword layer (see repository root `README.md` for the current design).

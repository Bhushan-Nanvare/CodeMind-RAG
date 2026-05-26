import axios from "axios";
import { BACKEND_URL, API_TIMEOUT } from "./constants";
import type {
  IngestRequest,
  IngestResponse,
  IngestionStatus,
  QueryRequest,
  QueryResponse,
  HealthResponse,
  SearchReposResponse,
} from "@/types";

const client = axios.create({
  baseURL: BACKEND_URL,
  timeout: API_TIMEOUT,
  headers: {
    "Content-Type": "application/json",
  },
});

export const api = {
  async health(): Promise<HealthResponse> {
    const res = await client.get<HealthResponse>("/api/health");
    return res.data;
  },

  async listRepos(): Promise<SearchReposResponse> {
    const res = await client.get<SearchReposResponse>("/api/search/repos");
    return res.data;
  },

  async ingestRepo(request: IngestRequest): Promise<IngestResponse> {
    const res = await client.post<IngestResponse>("/api/ingest", request);
    return res.data;
  },

  async getIngestionStatus(jobId: string): Promise<IngestionStatus> {
    const res = await client.get<IngestionStatus>(
      `/api/ingest/status/${jobId}`
    );
    return res.data;
  },

  async query(request: QueryRequest): Promise<QueryResponse> {
    const res = await client.post<QueryResponse>("/api/query", request, {
      timeout: 120000,
    });
    return res.data;
  },

  async contextChat(repo_url: string, question: string, branch = "main", force_repack = false) {
    const res = await client.post(
      "/api/v2/context-chat",
      { repo_url, question, branch, force_repack },
      { timeout: 180000 },
    );
    return res.data;
  },
};

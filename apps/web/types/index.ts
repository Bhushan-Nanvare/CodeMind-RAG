export interface IngestRequest {
  repo_url: string;
  branch: string;
}

export interface IngestResponse {
  status: string;
  job_id: string;
  message: string;
}

export interface IngestionStatus {
  job_id: string;
  status: string;
  files_indexed: number;
  chunks_created: number;
  error?: string;
  progress_percent: number;
}

export interface CodeChunk {
  file_path: string;
  start_line: number;
  end_line: number;
  language: string;
  function_name?: string;
  snippet: string;
  rrf_score: number;
}

export interface QueryRequest {
  question: string;
  repo_name: string;
  top_k?: number;
}

export interface QueryResponse {
  question: string;
  answer: string;
  sources: CodeChunk[];
  confidence_score: number;
  query_time_ms: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: CodeChunk[];
  confidence_score?: number;
  timestamp: Date;
}

export interface HealthResponse {
  status: string;
  timestamp: string;
  services: Record<string, string>;
}

export interface IndexedRepo {
  repo_name: string;
  repo_url: string;
  languages: string[];
  file_count: number;
  chunk_count: number;
  indexed_at: string;
}

export interface SearchReposResponse {
  repos: IndexedRepo[];
}

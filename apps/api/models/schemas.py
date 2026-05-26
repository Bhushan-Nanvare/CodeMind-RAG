import re

from pydantic import BaseModel, field_validator


class IngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"

    @field_validator("repo_url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        pattern = r"^https://github\.com/[\w\-\.]+/[\w\-\.]+(?:\.git)?$"
        if not re.match(pattern, v.strip()):
            raise ValueError("repo_url must be a valid GitHub URL: https://github.com/owner/repo")
        return v.strip().removesuffix(".git")

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, v: str) -> str:
        if not re.match(r"^[\w\-\./]+$", v):
            raise ValueError("branch name contains invalid characters")
        return v


class IngestResponse(BaseModel):
    status: str
    job_id: str
    message: str


class CodeChunk(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    language: str
    content: str
    function_name: str | None = None
    dependencies: list[str] = []
    char_count: int
    token_count: int


class IngestionStatus(BaseModel):
    job_id: str
    status: str
    files_indexed: int
    chunks_created: int
    total_chunks: int = 0
    chunks_indexed_in_db: int = 0
    vector_db_status: str = "pending"
    embeddings_generated: int = 0
    embedding_cache_hits: int = 0
    total_embedding_api_calls: int = 0
    embedding_mode: str = "local_mock"
    error: str | None = None
    progress_percent: int
    chunks: list[CodeChunk] = []


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: dict[str, str]
    uptime_seconds: float

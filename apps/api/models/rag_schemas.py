from pydantic import BaseModel, Field, field_validator


class SourceChunk(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    language: str
    snippet: str
    rrf_score: float = Field(..., description="Hybrid RRF score from retrieval")
    function_name: str | None = None


class QueryRequestBody(BaseModel):
    question: str
    repo_name: str
    top_k: int = 10

    @field_validator("question")
    @classmethod
    def question_not_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("question cannot be empty")
        return s

    @field_validator("repo_name")
    @classmethod
    def repo_not_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("repo_name cannot be empty")
        return s


class QueryResponseBody(BaseModel):
    question: str
    answer: str
    sources: list[SourceChunk]
    confidence_score: float
    query_time_ms: int

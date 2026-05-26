from pydantic import BaseModel


class ChunkMetadata(BaseModel):
    file_path: str
    start_line: int
    end_line: int
    language: str
    function_name: str | None = None
    dependencies: list[str] = []
    repo_name: str
    code_snippet: str
    timestamp: str


class VectorChunk(BaseModel):
    id: str
    vector: list[float]
    metadata: ChunkMetadata

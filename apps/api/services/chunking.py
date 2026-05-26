import ast
import re
from pathlib import Path

from langchain.text_splitter import RecursiveCharacterTextSplitter
from models.schemas import CodeChunk
from utils.logger import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50
MIN_CHUNK_TOKENS = 100

EXT_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}

LANGUAGE_SEPARATORS = {
    "python": ["\nclass ", "\ndef ", "\nasync def ", "\n\n", "\n", ". ", " "],
    "javascript": ["\nfunction ", "\nconst ", "\nlet ", "\nvar ", "\nclass ", "\n\n", "\n", ". ", " "],
    "typescript": ["\nfunction ", "\nconst ", "\nlet ", "\nvar ", "\nclass ", "\ninterface ", "\ntype ", "\n\n", "\n", ". ", " "],
    "java": ["\npublic class ", "\nprivate class ", "\nprotected class ", "\npublic static ", "\npublic ", "\n\n", "\n"],
    "default": ["\n\n", "\n", ". ", " "],
}


def _approx_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return max(1, len(text) // 4)


class ChunkingService:
    def detect_language(self, file_path: str) -> str:
        return EXT_TO_LANGUAGE.get(Path(file_path).suffix.lower(), "unknown")

    def get_language_separators(self, language: str) -> list[str]:
        return LANGUAGE_SEPARATORS.get(language, LANGUAGE_SEPARATORS["default"])

    def _extract_function_name(self, content: str, language: str) -> str | None:
        if language == "python":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        return node.name
            except SyntaxError:
                pass
            m = re.search(r"(?:def|async def|class)\s+(\w+)", content)
            return m.group(1) if m else None

        if language in ("javascript", "typescript"):
            m = re.search(
                r"(?:function|class)\s+(\w+)"
                r"|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:function|\(|[\w]+\s*=>)",
                content,
            )
            return (m.group(1) or m.group(2)) if m else None

        if language == "java":
            m = re.search(
                r"(?:public|private|protected)?\s*(?:static)?\s*(?:class|interface|enum)\s+(\w+)"
                r"|(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>\[\]]+)\s+(\w+)\s*\(",
                content,
            )
            return (m.group(1) or m.group(2)) if m else None

        return None

    def _get_line_numbers(
        self, original_lines: list[str], chunk_content: str, cursor_line: int
    ) -> tuple[int, int, int]:
        chunk_lines = chunk_content.splitlines()
        if not chunk_lines:
            return cursor_line, cursor_line, cursor_line

        first = chunk_lines[0].strip()
        for i in range(cursor_line - 1, len(original_lines)):
            if original_lines[i].strip() == first:
                end = min(i + 1 + len(chunk_lines) - 1, len(original_lines))
                return i + 1, end, end

        end = min(cursor_line + len(chunk_lines) - 1, len(original_lines))
        return cursor_line, end, end

    def chunk_code(
        self,
        code: str,
        language: str,
        file_path: str,
        start_line: int = 1,
    ) -> list[CodeChunk]:
        if not code.strip():
            return []

        splitter = RecursiveCharacterTextSplitter(
            separators=self.get_language_separators(language),
            chunk_size=CHUNK_SIZE * 4,
            chunk_overlap=CHUNK_OVERLAP * 4,
            length_function=len,
            is_separator_regex=False,
        )

        original_lines = code.splitlines()
        cursor = start_line
        chunks = []

        for raw in splitter.split_text(code):
            if not raw.strip():
                continue
            tokens = _approx_tokens(raw)
            if tokens < MIN_CHUNK_TOKENS:
                continue

            s, e, cursor = self._get_line_numbers(original_lines, raw, cursor)
            chunks.append(CodeChunk(
                file_path=file_path,
                start_line=s,
                end_line=e,
                language=language,
                content=raw,
                function_name=self._extract_function_name(raw, language),
                dependencies=[],
                char_count=len(raw),
                token_count=tokens,
            ))

        logger.debug("file_chunked", file=file_path, chunks=len(chunks))
        return chunks


chunking_service = ChunkingService()

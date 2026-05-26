from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

import tiktoken

from services.file_filter import FileFilter
from utils.logger import get_logger

logger = get_logger(__name__)

# llama-3.1-70b has 131k context; reserve ~8k for prompt + question + answer.
MAX_PACK_TOKENS = 100_000
_CACHE_TTL_SECONDS = 3600

_ENTRY_POINT_NAMES = {
    "main.py", "app.py", "server.py", "index.py", "cli.py",
    "main.ts", "index.ts", "app.ts", "server.ts",
    "main.js", "index.js", "app.js", "server.js",
    "main.go", "main.java",
}

_TEST_INDICATORS = {"test_", "_test", ".test.", ".spec.", "tests/", "__tests__/"}


@dataclass
class PackedFile:
    rel_path: str
    language: str
    content: str
    token_count: int
    size_bytes: int
    is_entry_point: bool
    is_test: bool


@dataclass
class PackResult:
    content: str
    format: str
    total_tokens: int
    total_files: int
    truncated: bool
    dropped_files: int
    repo_name: str
    packed_at: float = field(default_factory=time.time)


_pack_cache: dict[str, PackResult] = {}


def get_cached_pack(repo_name: str) -> PackResult | None:
    entry = _pack_cache.get(repo_name)
    if entry and (time.time() - entry.packed_at) < _CACHE_TTL_SECONDS:
        return entry
    return None


def set_cached_pack(repo_name: str, result: PackResult) -> None:
    _pack_cache[repo_name] = result


def invalidate_cache(repo_name: str) -> None:
    _pack_cache.pop(repo_name, None)


_enc = tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_enc.encode(text, disallowed_special=()))


class CodePacker:
    def __init__(self):
        self._file_filter = FileFilter()

    def _is_test(self, rel_path: str) -> bool:
        lower = rel_path.lower()
        return any(ind in lower for ind in _TEST_INDICATORS)

    def _is_entry_point(self, rel_path: str) -> bool:
        name = Path(rel_path).name.lower()
        return name in _ENTRY_POINT_NAMES

    def _read_file(self, abs_path: str, root: Path) -> PackedFile | None:
        path = Path(abs_path)
        rel = str(path.relative_to(root))
        lang = self._file_filter.detect_language(abs_path)
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        tokens = count_tokens(content)
        return PackedFile(
            rel_path=rel,
            language=lang,
            content=content,
            token_count=tokens,
            size_bytes=path.stat().st_size,
            is_entry_point=self._is_entry_point(rel),
            is_test=self._is_test(rel),
        )

    def _prioritize(self, files: list[PackedFile]) -> list[PackedFile]:
        entry = sorted([f for f in files if f.is_entry_point], key=lambda f: f.token_count)
        source = sorted([f for f in files if not f.is_entry_point and not f.is_test], key=lambda f: f.token_count)
        tests = sorted([f for f in files if f.is_test], key=lambda f: f.token_count)
        return entry + source + tests

    def _select_files(
        self, files: list[PackedFile], max_tokens: int
    ) -> tuple[list[PackedFile], int, int]:
        selected: list[PackedFile] = []
        used = dropped = 0
        for f in files:
            if used + f.token_count <= max_tokens:
                selected.append(f)
                used += f.token_count
            else:
                dropped += 1
        return selected, used, dropped

    def _format_xml(self, files: list[PackedFile], repo_name: str) -> str:
        parts = [
            f'<repository name="{repo_name}" files="{len(files)}">',
            "",
        ]
        for f in files:
            parts.append(f'<file path="{f.rel_path}" language="{f.language}">')
            parts.append(f.content)
            parts.append("</file>")
            parts.append("")
        parts.append("</repository>")
        return "\n".join(parts)

    def _format_markdown(self, files: list[PackedFile], repo_name: str) -> str:
        parts = [f"# Repository: {repo_name}\n"]
        for f in files:
            fence = "```" + f.language
            parts.append(f"## `{f.rel_path}`\n")
            parts.append(fence)
            parts.append(f.content)
            parts.append("```\n")
        return "\n".join(parts)

    def _format_plain(self, files: list[PackedFile], repo_name: str) -> str:
        parts = [f"=== REPOSITORY: {repo_name} ===\n"]
        for f in files:
            sep = "=" * 60
            parts.append(f"{sep}")
            parts.append(f"FILE: {f.rel_path}")
            parts.append(f"{sep}")
            parts.append(f.content)
            parts.append("")
        return "\n".join(parts)

    def pack(
        self,
        repo_path: str,
        repo_name: str,
        fmt: str = "xml",
        max_tokens: int = MAX_PACK_TOKENS,
    ) -> PackResult:
        root = Path(repo_path)
        abs_paths = self._file_filter.get_code_files(repo_path)

        if not abs_paths:
            raise ValueError(f"No supported source files found in {repo_path}")

        packed_files = [pf for ap in abs_paths if (pf := self._read_file(ap, root))]
        ordered = self._prioritize(packed_files)
        selected, used_tokens, dropped = self._select_files(ordered, max_tokens)

        if not selected:
            raise ValueError("All files exceed the token budget individually.")

        if fmt == "markdown":
            content = self._format_markdown(selected, repo_name)
        elif fmt == "plain":
            content = self._format_plain(selected, repo_name)
        else:
            content = self._format_xml(selected, repo_name)

        result = PackResult(
            content=content,
            format=fmt,
            total_tokens=used_tokens,
            total_files=len(selected),
            truncated=dropped > 0,
            dropped_files=dropped,
            repo_name=repo_name,
        )

        logger.info(
            "packer_complete",
            repo=repo_name,
            files=len(selected),
            dropped=dropped,
            tokens=used_tokens,
            truncated=dropped > 0,
            format=fmt,
        )
        return result

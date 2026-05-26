import os
from pathlib import Path

from utils.logger import get_logger

logger = get_logger(__name__)

SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java"}

EXCLUDED_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    "venv",
    ".venv",
    "vendor",
    ".next",
    ".nuxt",
}

MAX_FILE_SIZE_BYTES = 100 * 1024


class FileFilter:
    def get_code_files(self, repo_path: str) -> list[str]:
        root = Path(repo_path)
        code_files: list[str] = []
        skipped_size = skipped_ext = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]
            current_dir = Path(dirpath)

            if set(current_dir.relative_to(root).parts) & EXCLUDED_DIRS:
                dirnames.clear()
                continue

            for filename in filenames:
                filepath = current_dir / filename
                if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    skipped_ext += 1
                    continue
                try:
                    size = filepath.stat().st_size
                except OSError:
                    continue
                if size > MAX_FILE_SIZE_BYTES:
                    skipped_size += 1
                    continue
                code_files.append(str(filepath))

        logger.info(
            "file_filter_complete",
            total_code_files=len(code_files),
            skipped_wrong_ext=skipped_ext,
            skipped_too_large=skipped_size,
        )
        return code_files

    def detect_language(self, filepath: str) -> str:
        ext = Path(filepath).suffix.lower()
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".java": "java",
        }
        return ext_to_lang.get(ext, "unknown")

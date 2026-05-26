import re
import os
import shutil
import threading
from pathlib import Path

import git
from git.exc import GitCommandError

# Fix GitPython on Render
git.refresh()

from utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

GITHUB_URL_PATTERN = re.compile(
    r"^https://github\.com/[\w\-\.]+/[\w\-\.]+$"
)

CLONE_TIMEOUT_SECONDS = 300


class RepoCloner:
    def __init__(self):
        self.github_token: str | None = settings.GITHUB_TOKEN

    def validate_github_url(self, repo_url: str) -> bool:
        return bool(GITHUB_URL_PATTERN.match(repo_url))

    def _build_auth_url(self, repo_url: str) -> str:
        if self.github_token:
            parts = repo_url.replace("https://", "")
            return f"https://{self.github_token}@{parts}"
        return repo_url

    def clone_repo(self, repo_url: str, branch: str, dest_dir: str) -> str:
        if not self.validate_github_url(repo_url):
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        dest_path = Path(dest_dir)
        if dest_path.exists():
            shutil.rmtree(dest_path)
        dest_path.mkdir(parents=True, exist_ok=True)

        auth_url = self._build_auth_url(repo_url)
        result: dict = {"repo": None, "error": None}
        completed = threading.Event()

        # Block any interactive credential prompt — a private repo without a token
        # would otherwise hang the clone thread until the timeout.
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env.pop("GIT_ASKPASS", None)
        env.pop("SSH_ASKPASS", None)

        def _do_clone():
            try:
                result["repo"] = git.Repo.clone_from(
                    auth_url, str(dest_path), branch=branch, depth=1, env=env
                )
            except Exception as exc:
                result["error"] = exc
            finally:
                completed.set()

        thread = threading.Thread(target=_do_clone, daemon=True)
        thread.start()
        finished = completed.wait(timeout=CLONE_TIMEOUT_SECONDS)

        if not finished:
            if dest_path.exists():
                shutil.rmtree(dest_path, ignore_errors=True)
            raise TimeoutError(
                f"Repository clone timed out after {CLONE_TIMEOUT_SECONDS}s: {repo_url}"
            )

        if result["error"] is not None:
            if dest_path.exists():
                shutil.rmtree(dest_path, ignore_errors=True)
            err = result["error"]
            if isinstance(err, GitCommandError):
                msg = str(err)
                if "Repository not found" in msg or "not found" in msg.lower():
                    raise ValueError(f"Repository not found: {repo_url}")
                if "Permission denied" in msg or "Authentication failed" in msg:
                    raise PermissionError(
                        f"Access denied to repository: {repo_url}. "
                        "Set GITHUB_TOKEN for private repos."
                    )
                if "Could not resolve" in msg or "Failed to connect" in msg:
                    raise ConnectionError(f"Network error cloning {repo_url}: {msg}")
            raise RuntimeError(f"Clone failed for {repo_url}: {err}")

        logger.info(
            "repo_cloned_successfully",
            repo_url=repo_url,
            branch=branch,
            dest=str(dest_path),
        )
        return str(dest_path)

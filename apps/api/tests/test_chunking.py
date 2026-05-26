import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from services.chunking import ChunkingService, MIN_CHUNK_TOKENS
from services.language_parser import LanguageParser

service = ChunkingService()
parser = LanguageParser()

PYTHON_CODE = '''\
import os
import sys
from pathlib import Path


def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user with username and password."""
    if not username or not password:
        return False
    hashed = hash_password(password)
    stored = get_stored_hash(username)
    return hashed == stored


def hash_password(password: str) -> str:
    """Hash a password using SHA-256."""
    import hashlib
    return hashlib.sha256(password.encode()).hexdigest()


def get_stored_hash(username: str) -> str:
    """Retrieve the stored password hash for a user."""
    db = {"admin": "abc123hash", "user": "def456hash"}
    return db.get(username, "")


class AuthManager:
    """Manages authentication state."""

    def __init__(self):
        self.sessions = {}

    def create_session(self, user_id: str) -> str:
        import uuid
        token = str(uuid.uuid4())
        self.sessions[token] = user_id
        return token

    def validate_session(self, token: str) -> bool:
        return token in self.sessions

    def revoke_session(self, token: str) -> None:
        self.sessions.pop(token, None)
'''

JS_CODE = '''\
const express = require('express');
import { Router } from 'express';
import axios from 'axios';

function handleRequest(req, res) {
    const { userId } = req.params;
    if (!userId) {
        return res.status(400).json({ error: 'userId required' });
    }
    res.json({ userId, status: 'ok' });
}

const validateToken = (token) => {
    if (!token || token.length < 10) return false;
    return true;
};

class RequestHandler {
    constructor(router) {
        this.router = router;
    }

    register() {
        this.router.get('/users/:userId', handleRequest);
    }
}

module.exports = { handleRequest, validateToken, RequestHandler };
'''

SMALL_CODE = "x = 1"


def test_detect_language_python():
    assert service.detect_language("src/auth/login.py") == "python"
    assert service.detect_language("module.py") == "python"


def test_detect_language_javascript():
    assert service.detect_language("app.js") == "javascript"
    assert service.detect_language("component.jsx") == "javascript"


def test_detect_language_typescript():
    assert service.detect_language("types.ts") == "typescript"
    assert service.detect_language("App.tsx") == "typescript"


def test_detect_language_java():
    assert service.detect_language("Main.java") == "java"


def test_detect_language_unknown():
    assert service.detect_language("config.yaml") == "unknown"


def test_chunk_python_produces_chunks():
    chunks = service.chunk_code(PYTHON_CODE, "python", "auth/login.py")
    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.file_path == "auth/login.py"
        assert chunk.language == "python"
        assert chunk.content.strip()
        assert chunk.char_count > 0
        assert chunk.token_count >= MIN_CHUNK_TOKENS


def test_chunk_line_numbers_accurate():
    lines = PYTHON_CODE.splitlines()
    chunks = service.chunk_code(PYTHON_CODE, "python", "auth/login.py")
    total_lines = len(lines)
    for chunk in chunks:
        assert chunk.start_line >= 1, f"start_line={chunk.start_line} must be >= 1"
        assert chunk.end_line >= chunk.start_line, (
            f"end_line={chunk.end_line} < start_line={chunk.start_line}"
        )
        assert chunk.end_line <= total_lines, (
            f"end_line={chunk.end_line} > total lines={total_lines}"
        )


def test_chunk_min_size_enforced():
    chunks = service.chunk_code(SMALL_CODE, "python", "tiny.py")
    assert chunks == [], f"Expected no chunks for tiny code, got {len(chunks)}"


def test_function_name_extraction_python():
    chunks = service.chunk_code(PYTHON_CODE, "python", "auth/login.py")
    names = [c.function_name for c in chunks if c.function_name is not None]
    assert len(names) >= 1, "Expected at least one function name extracted"
    assert any(n in ("authenticate_user", "hash_password", "get_stored_hash", "AuthManager") for n in names)


def test_function_name_extraction_javascript():
    chunks = service.chunk_code(JS_CODE, "javascript", "handler.js")
    names = [c.function_name for c in chunks if c.function_name is not None]
    assert len(names) >= 1, "Expected at least one JS function name"


def test_dependency_extraction_python():
    deps = parser.extract_dependencies(PYTHON_CODE, "python", "auth/login.py")
    assert "os" in deps
    assert "sys" in deps
    assert "pathlib" in deps


def test_dependency_extraction_javascript():
    deps = parser.extract_dependencies(JS_CODE, "javascript", "handler.js")
    assert "express" in deps
    assert "axios" in deps

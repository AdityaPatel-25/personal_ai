import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend import db, rag
from backend.main import app


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Provides a clean temporary SQLite database for each test."""
    test_db_path = str(tmp_path / "test_personal_ai.db")
    monkeypatch.setattr(db, "DB_PATH", test_db_path)
    monkeypatch.setenv("SQLITE_DB_PATH", test_db_path)
    db.init_db()
    yield test_db_path


@pytest.fixture
def temp_chroma(tmp_path, monkeypatch):
    """Provides a clean temporary ChromaDB directory for each test."""
    test_chroma_path = str(tmp_path / "test_chroma")
    monkeypatch.setattr(rag, "CHROMA_DB_PATH", test_chroma_path)
    monkeypatch.setenv("CHROMA_DB_PATH", test_chroma_path)
    # Reset cached client so it initializes with new path
    monkeypatch.setattr(rag, "_chroma_client", None)
    yield test_chroma_path
    monkeypatch.setattr(rag, "_chroma_client", None)


@pytest.fixture
def mock_groq(monkeypatch):
    """Mocks Groq AsyncGroq client to prevent network calls."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_mock_test_key_1234567890")

    mock_client = MagicMock()
    # Mock chat completion create
    mock_chat_completion = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_chat_completion)
    # Mock audio transcription create
    mock_client.audio.transcriptions.create = AsyncMock(
        return_value=MagicMock(text="Mock transcribed audio text")
    )

    with patch("backend.chat.get_groq_client", return_value=mock_client):
        yield mock_client


@pytest.fixture
def client(temp_db, temp_chroma, mock_groq):
    """Provides a TestClient with temporary DB, temporary Chroma, and mocked Groq."""
    return TestClient(app)

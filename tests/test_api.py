import pytest
from fastapi.testclient import TestClient


def test_chat_rejects_empty_message_with_4xx(client: TestClient):
    """Verify that POST /chat returns a 4xx client error when given empty or whitespace messages."""
    # Empty string
    response_empty = client.post("/chat", json={"message": ""})
    assert 400 <= response_empty.status_code < 500, f"Expected 4xx, got {response_empty.status_code}"

    # Whitespace only
    response_whitespace = client.post("/chat", json={"message": "   \n\t  "})
    assert 400 <= response_whitespace.status_code < 500, f"Expected 4xx, got {response_whitespace.status_code}"

    # Missing message field
    response_missing = client.post("/chat", json={})
    assert 400 <= response_missing.status_code < 500, f"Expected 4xx, got {response_missing.status_code}"


def test_get_conversations_returns_list(client: TestClient):
    """Verify that GET /conversations returns a list of conversation objects."""
    # Initially should return empty list on clean temporary DB
    response = client.get("/conversations")
    assert response.status_code == 200
    conversations = response.json()
    assert isinstance(conversations, list)

    # Create a conversation and verify it appears in GET /conversations
    create_resp = client.post("/conversations", json={"title": "Binary Search Practice"})
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert "id" in created

    # Fetch list again
    list_resp = client.get("/conversations")
    assert list_resp.status_code == 200
    updated_list = list_resp.json()
    assert isinstance(updated_list, list)
    assert len(updated_list) == 1
    assert updated_list[0]["id"] == created["id"]
    assert updated_list[0]["title"] == "Binary Search Practice"


def test_rag_status_returns_expected_keys(client: TestClient):
    """Verify that GET /rag/status returns a 200 and all expected diagnostic keys."""
    response = client.get("/rag/status")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)

    expected_keys = {
        "status",
        "collection_name",
        "total_chunks",
        "chroma_db_path",
        "embedding_model",
    }
    for key in expected_keys:
        assert key in data, f"Key '{key}' missing from /rag/status response: {data}"

    assert data["status"] in ("online", "success")
    assert isinstance(data["total_chunks"], int)

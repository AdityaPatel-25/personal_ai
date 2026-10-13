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


def test_rag_status_not_rate_limited(client: TestClient):
    """Verify that GET /rag/status is NOT rate-limited so keep-alive health checks are unaffected."""
    # Execute 15 rapid health checks (more than the 10/min chat limit)
    for _ in range(15):
        resp = client.get("/rag/status")
        assert resp.status_code == 200


def test_chat_rate_limiting_per_ip(client: TestClient):
    """Verify that POST /chat enforces per-IP rate limiting and returns a clear 429 JSON response."""
    from backend.chat import limiter

    # Reset limiter storage for clean test state
    limiter.reset()

    # The default limit is 10 requests per minute
    statuses = []
    for i in range(11):
        resp = client.post("/chat", json={"message": f"Question number {i}"})
        statuses.append(resp.status_code)

    # First 10 requests succeed (200 OK)
    for code in statuses[:10]:
        assert code == 200, f"Expected 200 for first 10 requests, got {code}"

    # The 11th request must be rejected with 429 Rate Limit Exceeded
    assert statuses[10] == 429, f"Expected 429 for 11th request, got {statuses[10]}"

    # Verify 429 response structure and clear error detail
    final_resp = client.post("/chat", json={"message": "Exceeded request"})
    assert final_resp.status_code == 429
    body = final_resp.json()
    assert "too quickly" in body.get("detail", "").lower()


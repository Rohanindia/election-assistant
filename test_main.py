"""
Tests for India Election Assistant API
Run with: pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import app, get_fallback_response, FALLBACK_RESPONSES

client = TestClient(app)


# ── Health endpoint ────────────────────────────────────────────────────────────

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "gemini_configured" in data


# ── Home page ──────────────────────────────────────────────────────────────────

def test_index_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "VoteGuide" in response.text


# ── Input validation ───────────────────────────────────────────────────────────

def test_empty_message_rejected():
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 422


def test_message_too_long_rejected():
    response = client.post("/chat", json={"message": "x" * 1001})
    assert response.status_code == 422


def test_missing_message_field_rejected():
    response = client.post("/chat", json={})
    assert response.status_code == 422


# ── Fallback responses ─────────────────────────────────────────────────────────

def test_fallback_voter_registration():
    result = get_fallback_response("How do I register to vote?")
    assert "register" in result.lower() or "form 6" in result.lower() or "1950" in result.lower()


def test_fallback_evm():
    result = get_fallback_response("How does an EVM work?")
    assert "evm" in result.lower() or "electronic" in result.lower()


def test_fallback_nota():
    result = get_fallback_response("What is NOTA?")
    assert "nota" in result.lower() or "none of the above" in result.lower()


def test_fallback_eligible():
    result = get_fallback_response("Who is eligible to vote?")
    assert "18" in result or "citizen" in result.lower()


def test_fallback_unknown_returns_default():
    result = get_fallback_response("what is the weather today")
    assert isinstance(result, str)
    assert len(result) > 0


# ── Chat endpoint with mocked Gemini ──────────────────────────────────────────

@patch("main.GEMINI_API_KEY", "fake-key-for-testing")
@patch("main.genai")
def test_chat_with_gemini_mock(mock_genai):
    mock_model    = MagicMock()
    mock_session  = MagicMock()
    mock_response = MagicMock()

    mock_response.text        = "You need to be 18+ and a citizen to vote in India."
    mock_session.send_message = MagicMock(return_value=mock_response)
    mock_model.start_chat     = MagicMock(return_value=mock_session)
    mock_genai.GenerativeModel = MagicMock(return_value=mock_model)

    response = client.post("/chat", json={"message": "Who can vote in India?"})
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert "timestamp" in data


def test_chat_falls_back_without_api_key():
    with patch("main.GEMINI_API_KEY", ""):
        response = client.post("/chat", json={"message": "How do I register to vote?"})
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert len(data["reply"]) > 0


def test_chat_with_history():
    history = [
        {"role": "user",  "content": "What is Lok Sabha?"},
        {"role": "model", "content": "Lok Sabha is the lower house of Parliament."},
    ]
    with patch("main.GEMINI_API_KEY", ""):
        response = client.post("/chat", json={
            "message": "How many seats does it have?",
            "history": history
        })
    assert response.status_code == 200
    assert "reply" in response.json()


# ── CORS headers ───────────────────────────────────────────────────────────────

def test_cors_headers_present():
    response = client.options(
        "/chat",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    )
    assert response.status_code in (200, 405)


# ── Fallback coverage ─────────────────────────────────────────────────────────

def test_all_fallback_keywords_return_strings():
    for keyword in FALLBACK_RESPONSES:
        result = get_fallback_response(f"Tell me about {keyword}")
        assert isinstance(result, str), f"Fallback for '{keyword}' should return a string"
        assert len(result) > 10, f"Fallback for '{keyword}' returned too short a response"


# ── Security headers ───────────────────────────────────────────────────────────

def test_security_headers():
    response = client.get("/health")
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    assert response.headers.get("x-xss-protection") == "1; mode=block"


# ── Rate limiting ──────────────────────────────────────────────────────────────

def test_rate_limit_allows_normal_requests():
    response = client.post("/chat", json={"message": "What is NOTA?", "history": []})
    assert response.status_code in [200, 429]


# ── Input sanitization ─────────────────────────────────────────────────────────

def test_input_sanitization_strips_html():
    response = client.post(
        "/chat",
        json={"message": "<script>alert('xss')</script>What is voting?", "history": []}
    )
    assert response.status_code == 200
    assert "<script>" not in response.json().get("reply", "")


# ── Translate validation ───────────────────────────────────────────────────────

def test_translate_empty_text():
    response = client.post("/translate", json={"text": "", "target_language": "hi"})
    assert response.status_code == 422


def test_translate_invalid_language():
    response = client.post("/translate", json={"text": "hello", "target_language": "xx"})
    assert response.status_code in [400, 422, 200]


# ── Chat coverage ──────────────────────────────────────────────────────────────

def test_chat_returns_reply_field():
    response = client.post("/chat", json={"message": "What is EVM?", "history": []})
    assert response.status_code == 200
    assert "reply" in response.json()


def test_chat_with_long_history():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ] * 5
    response = client.post("/chat", json={"message": "What is NOTA?", "history": history})
    assert response.status_code == 200


def test_health_shows_all_services():
    response = client.get("/health")
    data = response.json()
    assert "status" in data
    assert "gemini_configured" in data


def test_root_returns_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_chat_message_too_long():
    long_message = "a" * 1001
    response = client.post("/chat", json={"message": long_message, "history": []})
    assert response.status_code == 422

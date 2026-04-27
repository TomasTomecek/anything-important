from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from anything_important.llm import assess_importance


def _llm_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"choices": [{"message": {"content": text}}]})
    return resp


def _make_mock_client(response: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    mock.post = AsyncMock(return_value=response)
    return mock


async def test_assess_importance_returns_true_for_yes():
    mock_client = _make_mock_client(_llm_response("ANSWER: YES\nREASON: Requires immediate action."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:8080",
            model="llama3",
            sender="boss@example.com",
            subject="Urgent: action needed",
            body="Please review this today.",
        )

    assert result is True


async def test_assess_importance_returns_false_for_no():
    mock_client = _make_mock_client(_llm_response("ANSWER: NO\nREASON: This is a marketing newsletter."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:8080",
            model="llama3",
            sender="newsletter@example.com",
            subject="Weekly digest",
            body="Here's what happened this week.",
        )

    assert result is False


async def test_assess_importance_logs_reason(caplog):
    import logging
    mock_client = _make_mock_client(_llm_response("ANSWER: NO\nREASON: Promotional email, no action required."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="anything_important.llm"):
            await assess_importance(
                ollama_url="http://localhost:8080",
                model="llama3",
                sender="promo@shop.com",
                subject="Sale!",
                body="50% off everything.",
            )

    assert "Promotional email, no action required." in caplog.text


async def test_assess_importance_defaults_to_no_on_malformed_response():
    mock_client = _make_mock_client(_llm_response("I cannot determine the importance."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:8080",
            model="llama3",
            sender="a@b.com",
            subject="hi",
            body="body",
        )

    assert result is False


async def test_assess_importance_includes_email_content_in_prompt():
    mock_client = _make_mock_client(_llm_response("ANSWER: NO\nREASON: Not actionable."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        await assess_importance(
            ollama_url="http://localhost:8080",
            model="llama3",
            sender="sender@test.com",
            subject="Test subject",
            body="Test body content",
        )

    payload = mock_client.post.call_args.kwargs["json"]
    prompt_text = payload["messages"][0]["content"]
    assert "sender@test.com" in prompt_text
    assert "Test subject" in prompt_text
    assert "Test body content" in prompt_text


_REALISTIC_LLAMA_CPP_RESPONSE = {
    "choices": [
        {
            "finish_reason": "stop",
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "ANSWER: NO\nREASON: This is a promotional newsletter with no required action.",
                "reasoning_content": "1. Analyze the email...\n2. It's a newsletter.\n3. Not important.",
            },
        }
    ],
    "created": 1777300741,
    "model": "Qwen3.5-9B-Q4_K_M.gguf",
    "system_fingerprint": "b8746-0893f50f2",
    "object": "chat.completion",
    "usage": {
        "completion_tokens": 42,
        "prompt_tokens": 11,
        "total_tokens": 53,
        "prompt_tokens_details": {"cached_tokens": 0},
    },
    "id": "chatcmpl-sHRegVdh8d6rFyYdpNFmKpMe6xvzqccP",
    "timings": {
        "prompt_n": 11,
        "predicted_n": 42,
    },
}


async def test_assess_importance_parses_realistic_llama_cpp_response():
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=_REALISTIC_LLAMA_CPP_RESPONSE)
    mock_client = _make_mock_client(resp)

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:8080",
            model="Qwen3.5-9B-Q4_K_M.gguf",
            sender="newsletter@example.com",
            subject="Weekly digest",
            body="Check out our latest offers.",
        )

    assert result is False


async def test_assess_importance_truncates_long_body():
    long_body = "x" * 5000
    mock_client = _make_mock_client(_llm_response("ANSWER: NO\nREASON: Not actionable."))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        await assess_importance(
            ollama_url="http://localhost:8080",
            model="llama3",
            sender="a@b.com",
            subject="hi",
            body=long_body,
        )

    payload = mock_client.post.call_args.kwargs["json"]
    prompt_text = payload["messages"][0]["content"]
    assert len(prompt_text) < 5000

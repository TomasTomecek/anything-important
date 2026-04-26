from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from anything_important.llm import assess_importance


def _ollama_response(answer: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value={"message": {"content": answer}})
    return resp


def _make_mock_client(response: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    mock.post = AsyncMock(return_value=response)
    return mock


async def test_assess_importance_returns_true_for_yes():
    mock_client = _make_mock_client(_ollama_response("YES"))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:11434",
            model="llama3.2",
            sender="boss@example.com",
            subject="Urgent: action needed",
            body="Please review this today.",
        )

    assert result is True


async def test_assess_importance_returns_false_for_no():
    mock_client = _make_mock_client(_ollama_response("NO"))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:11434",
            model="llama3.2",
            sender="newsletter@example.com",
            subject="Weekly digest",
            body="Here's what happened this week.",
        )

    assert result is False


async def test_assess_importance_is_case_insensitive():
    mock_client = _make_mock_client(_ollama_response("yes, this is important"))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        result = await assess_importance(
            ollama_url="http://localhost:11434",
            model="llama3.2",
            sender="a@b.com",
            subject="hi",
            body="body",
        )

    assert result is True


async def test_assess_importance_includes_email_content_in_prompt():
    mock_client = _make_mock_client(_ollama_response("NO"))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        await assess_importance(
            ollama_url="http://localhost:11434",
            model="llama3.2",
            sender="sender@test.com",
            subject="Test subject",
            body="Test body content",
        )

    payload = mock_client.post.call_args.kwargs["json"]
    prompt_text = payload["messages"][0]["content"]
    assert "sender@test.com" in prompt_text
    assert "Test subject" in prompt_text
    assert "Test body content" in prompt_text


async def test_assess_importance_truncates_long_body():
    long_body = "x" * 5000
    mock_client = _make_mock_client(_ollama_response("NO"))

    with patch("anything_important.llm.httpx.AsyncClient", return_value=mock_client):
        await assess_importance(
            ollama_url="http://localhost:11434",
            model="llama3.2",
            sender="a@b.com",
            subject="hi",
            body=long_body,
        )

    payload = mock_client.post.call_args.kwargs["json"]
    prompt_text = payload["messages"][0]["content"]
    assert len(prompt_text) < 5000

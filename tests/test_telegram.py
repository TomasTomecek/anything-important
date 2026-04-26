import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from anything_important.telegram import send_message


def _make_mock_client(response: MagicMock) -> MagicMock:
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    mock.post = AsyncMock(return_value=response)
    return mock


async def test_send_message_posts_to_correct_url():
    response = MagicMock()
    response.raise_for_status = MagicMock()
    mock_client = _make_mock_client(response)

    with patch("anything_important.telegram.httpx.AsyncClient", return_value=mock_client):
        await send_message(token="tok123", chat_id="456", text="Important email!")

    mock_client.post.assert_called_once_with(
        "https://api.telegram.org/bottok123/sendMessage",
        json={"chat_id": "456", "text": "Important email!"},
    )


async def test_send_message_raises_on_http_error():
    response = MagicMock()
    response.raise_for_status = MagicMock(side_effect=Exception("HTTP 400"))
    mock_client = _make_mock_client(response)

    with patch("anything_important.telegram.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception, match="HTTP 400"):
            await send_message(token="bad", chat_id="1", text="hi")

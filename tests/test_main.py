from unittest.mock import AsyncMock, patch
import pytest
from anything_important.config import Config
from anything_important.gmail import Thread
from anything_important.main import run_once


def _cfg() -> Config:
    return Config(
        telegram_token="tok",
        telegram_chat_id="123",
        ollama_url="http://localhost:11434",
        ollama_model="llama3.2",
        check_interval=300,
        gmail_credentials_file="/creds.json",
    )


async def test_run_once_notifies_for_important_thread():
    thread = Thread(id="t1", message_id="m1", sender="boss@example.com", subject="Urgent", body="Meet now")

    with (
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=True)),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.mark_thread_read", AsyncMock()) as mock_mark,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once_with(
        token="tok",
        chat_id="123",
        text="📧 Important email from boss@example.com\nSubject: Urgent",
    )
    mock_mark.assert_called_once()
    assert mock_mark.call_args.kwargs == {"message_id": "m1"}


async def test_run_once_skips_unimportant_thread():
    thread = Thread(id="t2", message_id="m2", sender="news@example.com", subject="Digest", body="content")

    with (
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=False)),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.mark_thread_read", AsyncMock()) as mock_mark,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_not_called()
    mock_mark.assert_not_called()


async def test_run_once_handles_multiple_threads():
    threads = [
        Thread(id="t1", message_id="m1", sender="a@b.com", subject="Important", body="urgent"),
        Thread(id="t2", message_id="m2", sender="c@d.com", subject="Newsletter", body="content"),
        Thread(id="t3", message_id="m3", sender="e@f.com", subject="Also important", body="urgent"),
    ]

    with (
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=threads)),
        patch("anything_important.main.assess_importance", AsyncMock(side_effect=[True, False, True])),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.mark_thread_read", AsyncMock()) as mock_mark,
    ):
        await run_once(_cfg(), AsyncMock())

    assert mock_send.call_count == 2
    assert mock_mark.call_count == 2


async def test_run_once_handles_empty_inbox():
    with (
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[])),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_not_called()

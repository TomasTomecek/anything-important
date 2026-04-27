import argparse
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from anything_important.config import Config
from anything_important.gmail import Thread
from anything_important.main import _cmd_auth, run_once


def _cfg() -> Config:
    return Config(
        telegram_token="tok",
        telegram_chat_id="123",
        ollama_url="http://localhost:8080",
        ollama_model="llama3",
        check_interval=300,
        gmail_credentials_file="/creds.json",
        gmail_query="is:unread",
    )


async def test_run_once_notifies_and_labels_important_thread():
    thread = Thread(id="t1", message_id="m1", sender="boss@example.com", subject="Urgent", body="Meet now")

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=True)),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()) as mock_label,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once_with(
        token="tok",
        chat_id="123",
        text="📧 Important email from boss@example.com\nSubject: Urgent",
    )
    assert mock_label.call_args.kwargs == {"thread_id": "t1", "label_id": "Label_2"}


async def test_run_once_skips_unimportant_thread():
    thread = Thread(id="t2", message_id="m2", sender="news@example.com", subject="Digest", body="content")

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=False)),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()) as mock_label,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_not_called()
    mock_label.assert_not_called()


async def test_run_once_handles_multiple_threads():
    threads = [
        Thread(id="t1", message_id="m1", sender="a@b.com", subject="Important", body="urgent"),
        Thread(id="t2", message_id="m2", sender="c@d.com", subject="Newsletter", body="content"),
        Thread(id="t3", message_id="m3", sender="e@f.com", subject="Also important", body="urgent"),
    ]

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=threads)),
        patch("anything_important.main.assess_importance", AsyncMock(side_effect=[True, False, True])),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()) as mock_label,
    ):
        await run_once(_cfg(), AsyncMock())

    assert mock_send.call_count == 2
    assert mock_label.call_count == 2


async def test_run_once_handles_empty_inbox():
    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[])),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_not_called()


def test_cmd_auth_saves_credentials(tmp_path):
    output = tmp_path / "creds.json"
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = '{"token": "test_token"}'
    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = ("https://accounts.google.com/o/oauth2/auth?...", None)
    mock_flow.credentials = mock_creds

    with (
        patch("anything_important.main.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
        patch("builtins.input", return_value="http://localhost:8080/?code=abc&state=xyz"),
    ):
        _cmd_auth(argparse.Namespace(client_secret="client_secret.json", output=str(output), port=8080))

    mock_flow.fetch_token.assert_called_once_with(authorization_response="http://localhost:8080/?code=abc&state=xyz")
    assert output.read_text() == '{"token": "test_token"}'


def test_cmd_auth_sets_redirect_uri_with_port(tmp_path):
    output = tmp_path / "creds.json"
    mock_creds = MagicMock()
    mock_creds.to_json.return_value = "{}"
    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = ("https://auth.url/", None)
    mock_flow.credentials = mock_creds

    with (
        patch("anything_important.main.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
        patch("builtins.input", return_value="http://localhost:9090/?code=xyz"),
    ):
        _cmd_auth(argparse.Namespace(client_secret="client_secret.json", output=str(output), port=9090))

    assert mock_flow.redirect_uri == "http://localhost:9090"

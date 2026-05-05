import argparse
import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from anything_important.config import Config
from anything_important.gmail import Thread
from anything_important.main import _cmd_auth, run_once


def _cfg() -> Config:
    return Config(
        telegram_token="tok",
        telegram_chat_id="123",
        llm_url="http://localhost:8080",
        llm_model="llama3",
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
        patch("anything_important.main.summarize_email", AsyncMock(return_value="Meet now.")),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()) as mock_label,
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once()
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
    mock_label.assert_called_once_with(mock_label.call_args[0][0], thread_id="t2", label_id="Label_2")


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
        patch("anything_important.main.summarize_email", AsyncMock(return_value="Summary.")),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()) as mock_label,
    ):
        await run_once(_cfg(), AsyncMock())

    assert mock_send.call_count == 1
    assert mock_label.call_count == 3


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
        patch.dict(os.environ, {}, clear=False),
    ):
        _cmd_auth(argparse.Namespace(client_secret="client_secret.json", output=str(output), port=8080, local=False))

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
        patch.dict(os.environ, {}, clear=False),
    ):
        _cmd_auth(argparse.Namespace(client_secret="client_secret.json", output=str(output), port=9090, local=False))

    assert mock_flow.redirect_uri == "http://localhost:9090"


def test_cmd_auth_headless_sets_insecure_transport_before_fetch(tmp_path):
    output = tmp_path / "creds.json"
    mock_flow = MagicMock()
    mock_flow.authorization_url.return_value = ("https://auth.url/", None)
    mock_flow.credentials.to_json.return_value = "{}"

    captured_env: dict = {}
    mock_flow.fetch_token.side_effect = lambda **kw: captured_env.update(os.environ)

    with (
        patch("anything_important.main.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow),
        patch("builtins.input", return_value="http://localhost:8080/?code=abc"),
        patch.dict(os.environ, {}, clear=False),
    ):
        os.environ.pop("OAUTHLIB_INSECURE_TRANSPORT", None)
        _cmd_auth(argparse.Namespace(client_secret="cs.json", output=str(output), port=8080, local=False))

    assert captured_env.get("OAUTHLIB_INSECURE_TRANSPORT") == "1"


def test_cmd_auth_local_uses_run_local_server(tmp_path):
    output = tmp_path / "creds.json"
    mock_flow = MagicMock()
    mock_flow.credentials.to_json.return_value = "{}"

    with patch("anything_important.main.InstalledAppFlow.from_client_secrets_file", return_value=mock_flow):
        _cmd_auth(argparse.Namespace(client_secret="cs.json", output=str(output), port=8080, local=True))

    mock_flow.run_local_server.assert_called_once_with(port=8080, open_browser=False)
    mock_flow.fetch_token.assert_not_called()
    assert output.read_text() == "{}"


async def test_run_once_sends_batch_message_for_important_thread():
    thread = Thread(id="t1", message_id="m1", sender="boss@example.com", subject="Urgent", body="Meet now")

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=True)),
        patch("anything_important.main.summarize_email", AsyncMock(return_value="Please meet now.")),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()),
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once()
    text = mock_send.call_args.kwargs["text"]
    assert "📧 1 important email:" in text
    assert "boss@example.com" in text
    assert "Urgent" in text
    assert "Please meet now." in text


async def test_run_once_sends_single_batch_for_multiple_important_threads():
    threads = [
        Thread(id="t1", message_id="m1", sender="a@b.com", subject="Critical", body="urgent"),
        Thread(id="t2", message_id="m2", sender="c@d.com", subject="Newsletter", body="content"),
        Thread(id="t3", message_id="m3", sender="e@f.com", subject="Also critical", body="also urgent"),
    ]

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=threads)),
        patch("anything_important.main.assess_importance", AsyncMock(side_effect=[True, False, True])),
        patch("anything_important.main.summarize_email", AsyncMock(return_value="Summary.")),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()),
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once()
    text = mock_send.call_args.kwargs["text"]
    assert "📧 2 important emails:" in text
    assert "a@b.com" in text
    assert "e@f.com" in text
    assert "c@d.com" not in text


async def test_run_once_falls_back_to_body_excerpt_on_summarize_failure():
    thread = Thread(id="t1", message_id="m1", sender="a@b.com", subject="Urgent", body="x" * 300)

    with (
        patch("anything_important.main.get_or_create_label", AsyncMock(return_value="Label_2")),
        patch("anything_important.main.list_unread_threads", AsyncMock(return_value=[thread])),
        patch("anything_important.main.assess_importance", AsyncMock(return_value=True)),
        patch("anything_important.main.summarize_email", AsyncMock(side_effect=RuntimeError("LLM down"))),
        patch("anything_important.main.send_message", AsyncMock()) as mock_send,
        patch("anything_important.main.apply_label", AsyncMock()),
    ):
        await run_once(_cfg(), AsyncMock())

    mock_send.assert_called_once()
    text = mock_send.call_args.kwargs["text"]
    assert "x" * 250 in text
    assert "x" * 251 not in text

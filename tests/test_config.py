import pytest
from anything_important.config import Config


def test_config_loads_required_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")

    cfg = Config.from_env()

    assert cfg.telegram_token == "tok123"
    assert cfg.telegram_chat_id == "456"


def test_config_optional_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("CHECK_INTERVAL", raising=False)
    monkeypatch.delenv("GMAIL_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("GMAIL_QUERY", raising=False)

    cfg = Config.from_env()

    assert cfg.ollama_url == "http://localhost:11434"
    assert cfg.ollama_model == "llama3.2"
    assert cfg.check_interval == 300
    assert cfg.gmail_credentials_file == "/credentials/oauth_credentials.json"
    assert cfg.gmail_query == "is:unread newer_than:5d -label:llm-says-important"


def test_config_overrides_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    monkeypatch.setenv("CHECK_INTERVAL", "60")
    monkeypatch.setenv("GMAIL_CREDENTIALS_FILE", "/creds.json")
    monkeypatch.setenv("GMAIL_QUERY", "is:unread label:inbox")

    cfg = Config.from_env()

    assert cfg.ollama_url == "http://ollama:11434"
    assert cfg.ollama_model == "mistral"
    assert cfg.check_interval == 60
    assert cfg.gmail_credentials_file == "/creds.json"
    assert cfg.gmail_query == "is:unread label:inbox"


def test_config_missing_telegram_token_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")

    with pytest.raises(KeyError):
        Config.from_env()


def test_config_missing_chat_id_raises(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    with pytest.raises(KeyError):
        Config.from_env()

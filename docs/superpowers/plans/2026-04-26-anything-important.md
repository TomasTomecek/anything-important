# anything-important Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python asyncio daemon that periodically checks Gmail via the official Google Gmail MCP server for important emails and sends Telegram notifications using a local Ollama LLM for importance classification.

**Architecture:** A main loop obtains a fresh OAuth2 access token, connects to the remote Gmail MCP server at `https://gmailmcp.googleapis.com/mcp/v1` via the MCP streamable-HTTP transport, fetches unread threads, passes each to a local Ollama instance for importance assessment, sends Telegram notifications for important ones, then marks them as read to avoid re-alerting. All I/O is async; Ollama and Telegram use plain HTTP via `httpx`.

**Tech Stack:** Python 3.12+, `mcp` (MCP client, streamable-HTTP transport), `google-auth` (OAuth2 token refresh), `httpx` (Ollama + Telegram HTTP), `pytest` + `pytest-asyncio` + `pytest-mock`, Fedora 43 container (Python only — no Node.js required).

**Assumptions:**
- Local LLM is served by Ollama at a configurable URL
- Gmail MCP server is the hosted Google service at `https://gmailmcp.googleapis.com/mcp/v1`
- OAuth2 credentials JSON (with refresh token) is mounted into the container at runtime
- Threads are marked read after a Telegram alert is sent (prevents duplicate notifications)
- Tool names and argument schemas are discovered at Task 5 step 1 — the names below (`search_threads`, `get_thread`, `unlabel_message`) are based on the Google docs tool list and must be verified

---

## File Map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, dependencies, pytest config |
| `anything_important/config.py` | Load env vars into a typed `Config` dataclass |
| `anything_important/telegram.py` | POST a message to a Telegram chat via Bot API |
| `anything_important/llm.py` | Ask Ollama whether an email is important (returns `bool`) |
| `anything_important/auth.py` | Load OAuth2 credentials file and return a fresh access token |
| `anything_important/gmail.py` | MCP client: list unread threads, extract content, mark read |
| `anything_important/main.py` | Orchestration loop: glue all modules together |
| `Containerfile` | Fedora 43 + Python 3.12, no Node.js needed |
| `tests/test_config.py` | Unit tests for `Config` |
| `tests/test_telegram.py` | Unit tests for Telegram notifier |
| `tests/test_llm.py` | Unit tests for LLM client |
| `tests/test_auth.py` | Unit tests for OAuth2 token loading |
| `tests/test_gmail.py` | Unit tests for Gmail MCP client |
| `tests/test_main.py` | Unit tests for orchestration |

---

### Task 1: Project scaffold

**Files:**
- Modify: `pyproject.toml`
- Create: `anything_important/__init__.py`
- Create: `tests/__init__.py`
- Create: `.env.example`

- [ ] **Step 1: Replace the stub pyproject.toml**

```toml
[project]
name = "anything-important"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "mcp>=1.9.0",
    "google-auth>=2.30.0",
    "httpx>=0.27.0",
]

[project.scripts]
anything-important = "anything_important.main:main"

[tool.pytest.ini_options]
asyncio_mode = "auto"

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-mock>=3.14.0",
]
```

- [ ] **Step 2: Create package and test directories**

```bash
mkdir -p anything_important tests
touch anything_important/__init__.py tests/__init__.py
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync --dev
# or: pip install -e ".[dev]"
```

- [ ] **Step 4: Create .env.example**

```ini
TELEGRAM_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
CHECK_INTERVAL=300
GMAIL_CREDENTIALS_FILE=/credentials/oauth_credentials.json
```

- [ ] **Step 5: Verify pytest runs**

```bash
pytest
```

Expected: `no tests ran` — 0 collected, 0 errors

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml anything_important/__init__.py tests/__init__.py .env.example
git commit -m "feat: project scaffold"
```

---

### Task 2: Configuration module

**Files:**
- Create: `anything_important/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
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

    cfg = Config.from_env()

    assert cfg.ollama_url == "http://localhost:11434"
    assert cfg.ollama_model == "llama3.2"
    assert cfg.check_interval == 300
    assert cfg.gmail_credentials_file == "/credentials/oauth_credentials.json"


def test_config_overrides_defaults(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "mistral")
    monkeypatch.setenv("CHECK_INTERVAL", "60")
    monkeypatch.setenv("GMAIL_CREDENTIALS_FILE", "/creds.json")

    cfg = Config.from_env()

    assert cfg.ollama_url == "http://ollama:11434"
    assert cfg.ollama_model == "mistral"
    assert cfg.check_interval == 60
    assert cfg.gmail_credentials_file == "/creds.json"


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.config'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/config.py
import os
from dataclasses import dataclass


@dataclass
class Config:
    telegram_token: str
    telegram_chat_id: str
    ollama_url: str
    ollama_model: str
    check_interval: int
    gmail_credentials_file: str

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            telegram_token=os.environ["TELEGRAM_TOKEN"],
            telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
            ollama_url=os.getenv("OLLAMA_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.2"),
            check_interval=int(os.getenv("CHECK_INTERVAL", "300")),
            gmail_credentials_file=os.getenv(
                "GMAIL_CREDENTIALS_FILE", "/credentials/oauth_credentials.json"
            ),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add anything_important/config.py tests/test_config.py
git commit -m "feat: config module with env var loading"
```

---

### Task 3: Telegram notifier

**Files:**
- Create: `anything_important/telegram.py`
- Create: `tests/test_telegram.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_telegram.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_telegram.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.telegram'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/telegram.py
import httpx


async def send_message(token: str, chat_id: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_telegram.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add anything_important/telegram.py tests/test_telegram.py
git commit -m "feat: telegram notifier"
```

---

### Task 4: Ollama LLM importance classifier

**Files:**
- Create: `anything_important/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_llm.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.llm'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/llm.py
import httpx

_PROMPT = """\
You are an email triage assistant. Determine if the following email requires \
immediate human attention.
Respond with only YES or NO.

From: {sender}
Subject: {subject}
Body:
{body}"""

_MAX_BODY = 2000


async def assess_importance(
    ollama_url: str,
    model: str,
    sender: str,
    subject: str,
    body: str,
) -> bool:
    prompt = _PROMPT.format(sender=sender, subject=subject, body=body[:_MAX_BODY])
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{ollama_url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
        )
        response.raise_for_status()
        answer = response.json()["message"]["content"].strip().upper()
        return answer.startswith("YES")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add anything_important/llm.py tests/test_llm.py
git commit -m "feat: ollama LLM importance classifier"
```

---

### Task 5: OAuth2 token module

**Files:**
- Create: `anything_important/auth.py`
- Create: `tests/test_auth.py`

The Gmail MCP server requires an OAuth2 Bearer token on every request. `google-auth` handles loading the credentials file and refreshing the token when it expires.

The credentials file is the JSON you download from Google Cloud Console after completing the OAuth consent flow (it contains `client_id`, `client_secret`, and `refresh_token`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_auth.py
import json
import pytest
from unittest.mock import MagicMock, patch
from anything_important.auth import get_access_token


def test_get_access_token_returns_token_from_valid_credentials(tmp_path):
    creds_file = tmp_path / "creds.json"
    creds_file.write_text(json.dumps({
        "client_id": "client123",
        "client_secret": "secret456",
        "refresh_token": "refresh789",
        "token_uri": "https://oauth2.googleapis.com/token",
        "token": "existing_token",
        "expiry": "2099-01-01T00:00:00Z",
    }))

    mock_creds = MagicMock()
    mock_creds.expired = False
    mock_creds.token = "existing_token"

    with patch("anything_important.auth.Credentials.from_authorized_user_file", return_value=mock_creds):
        token = get_access_token(str(creds_file))

    assert token == "existing_token"


def test_get_access_token_refreshes_expired_credentials(tmp_path):
    creds_file = tmp_path / "creds.json"
    creds_file.write_text("{}")

    mock_creds = MagicMock()
    mock_creds.expired = True
    mock_creds.refresh_token = "refresh789"
    mock_creds.token = "new_token"

    with (
        patch("anything_important.auth.Credentials.from_authorized_user_file", return_value=mock_creds),
        patch("anything_important.auth.Request") as mock_request,
    ):
        token = get_access_token(str(creds_file))

    mock_creds.refresh.assert_called_once()
    assert token == "new_token"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_auth.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.auth'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/auth.py
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials


def get_access_token(credentials_file: str) -> str:
    creds = Credentials.from_authorized_user_file(credentials_file)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds.token
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_auth.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add anything_important/auth.py tests/test_auth.py
git commit -m "feat: oauth2 token loading with auto-refresh"
```

---

### Task 6: Gmail MCP client

**Files:**
- Create: `anything_important/gmail.py`
- Create: `tests/test_gmail.py`

**Before writing code — discover the server's exact tool schemas.**

The tool names listed in Google's docs are `search_threads`, `get_thread`, and `unlabel_message`. Their exact argument names and response shapes must be verified before implementing the parsing logic. Connect once with a real token:

```bash
python3 - <<'EOF'
import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TOKEN = "your_access_token_here"  # from `get_access_token(credentials_file)`

async def main():
    async with streamablehttp_client(
        "https://gmailmcp.googleapis.com/mcp/v1",
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            for t in tools.tools:
                print(t.name, json.dumps(t.inputSchema, indent=2))

asyncio.run(main())
EOF
```

Then call `search_threads` with a real query to see the actual response shape:

```bash
python3 - <<'EOF'
import asyncio, json
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

TOKEN = "your_access_token_here"

async def main():
    async with streamablehttp_client(
        "https://gmailmcp.googleapis.com/mcp/v1",
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("search_threads", {"query": "is:unread", "max_results": 1})
            print(result.content[0].text)

asyncio.run(main())
EOF
```

Update the argument names in the implementation below if the actual schema differs from what's shown.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gmail.py
import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from anything_important.gmail import Thread, list_unread_threads, mark_thread_read


def _tool_result(data: object) -> MagicMock:
    content = MagicMock()
    content.text = json.dumps(data)
    result = MagicMock()
    result.content = [content]
    return result


def _make_session(**tool_responses) -> AsyncMock:
    session = AsyncMock()

    async def call_tool(name, args=None):
        return tool_responses[name]

    session.call_tool = AsyncMock(side_effect=call_tool)
    return session


async def test_list_unread_threads_returns_thread_objects():
    search_result = _tool_result([{"id": "t1"}])
    thread_result = _tool_result({
        "id": "t1",
        "messages": [{
            "id": "m1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "boss@example.com"},
                    {"name": "Subject", "value": "Urgent meeting"},
                ],
                "body": {"data": "UGxlYXNlIGpvaW4gdGhlIG1lZXRpbmcu"},
            },
        }],
    })
    session = _make_session(search_threads=search_result, get_thread=thread_result)

    threads = await list_unread_threads(session)

    assert len(threads) == 1
    assert threads[0].id == "t1"
    assert threads[0].message_id == "m1"
    assert threads[0].sender == "boss@example.com"
    assert threads[0].subject == "Urgent meeting"
    assert threads[0].body == "Please join the meeting."


async def test_list_unread_threads_returns_empty_when_no_threads():
    session = _make_session(search_threads=_tool_result([]))

    threads = await list_unread_threads(session)

    assert threads == []


async def test_mark_thread_read_removes_unread_label():
    session = _make_session(unlabel_message=_tool_result({}))

    await mark_thread_read(session, message_id="m1")

    session.call_tool.assert_called_once_with(
        "unlabel_message",
        {"message_id": "m1", "label_name": "UNREAD"},
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_gmail.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.gmail'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/gmail.py
import base64
import json
from dataclasses import dataclass

from mcp import ClientSession


@dataclass
class Thread:
    id: str
    message_id: str
    sender: str
    subject: str
    body: str


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


async def list_unread_threads(session: ClientSession) -> list[Thread]:
    result = await session.call_tool(
        "search_threads",
        {"query": "is:unread", "max_results": 20},
    )
    thread_stubs = json.loads(result.content[0].text)
    threads = []
    for stub in thread_stubs:
        detail_result = await session.call_tool("get_thread", {"thread_id": stub["id"]})
        detail = json.loads(detail_result.content[0].text)
        messages = detail.get("messages", [])
        if not messages:
            continue
        first = messages[0]
        headers = first.get("payload", {}).get("headers", [])
        body_data = first.get("payload", {}).get("body", {}).get("data", "")
        threads.append(
            Thread(
                id=detail["id"],
                message_id=first["id"],
                sender=_header(headers, "From"),
                subject=_header(headers, "Subject"),
                body=_decode_body(body_data),
            )
        )
    return threads


async def mark_thread_read(session: ClientSession, message_id: str) -> None:
    await session.call_tool(
        "unlabel_message",
        {"message_id": message_id, "label_name": "UNREAD"},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_gmail.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add anything_important/gmail.py tests/test_gmail.py
git commit -m "feat: gmail MCP client using remote google server"
```

---

### Task 7: Main orchestration loop

**Files:**
- Create: `anything_important/main.py`
- Create: `tests/test_main.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_main.py
from unittest.mock import AsyncMock, MagicMock, patch
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
    mock_mark.assert_called_once_with(AsyncMock(), message_id="m1")


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ModuleNotFoundError: No module named 'anything_important.main'`

- [ ] **Step 3: Write minimal implementation**

```python
# anything_important/main.py
import asyncio
import logging
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from anything_important.auth import get_access_token
from anything_important.config import Config
from anything_important.gmail import list_unread_threads, mark_thread_read
from anything_important.llm import assess_importance
from anything_important.telegram import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_GMAIL_MCP_URL = "https://gmailmcp.googleapis.com/mcp/v1"


async def run_once(config: Config, session: ClientSession) -> None:
    threads = await list_unread_threads(session)
    log.info("Found %d unread threads", len(threads))
    for thread in threads:
        important = await assess_importance(
            ollama_url=config.ollama_url,
            model=config.ollama_model,
            sender=thread.sender,
            subject=thread.subject,
            body=thread.body,
        )
        if important:
            log.info("Important: %s — %s", thread.sender, thread.subject)
            await send_message(
                token=config.telegram_token,
                chat_id=config.telegram_chat_id,
                text=f"📧 Important email from {thread.sender}\nSubject: {thread.subject}",
            )
            await mark_thread_read(session, message_id=thread.message_id)
        else:
            log.info("Skipping unimportant thread from %s", thread.sender)


@asynccontextmanager
async def _gmail_session(config: Config):
    token = get_access_token(config.gmail_credentials_file)
    async with streamablehttp_client(
        _GMAIL_MCP_URL,
        headers={"Authorization": f"Bearer {token}"},
    ) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def _run_loop(config: Config) -> None:
    while True:
        try:
            async with _gmail_session(config) as session:
                await run_once(config, session)
        except Exception:
            log.exception("Error during check cycle")
        log.info("Sleeping %ds until next check", config.check_interval)
        await asyncio.sleep(config.check_interval)


def main() -> None:
    config = Config.from_env()
    asyncio.run(_run_loop(config))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_main.py -v
```

Expected: 4 passed

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: 21 tests passed (5 + 2 + 5 + 2 + 3 + 4)

- [ ] **Step 6: Commit**

```bash
git add anything_important/main.py tests/test_main.py
git commit -m "feat: main orchestration loop"
```

---

### Task 8: Containerfile

**Files:**
- Modify: `Containerfile`

Pure Python — no Node.js required because the Gmail MCP server is a remote HTTP service.

- [ ] **Step 1: Replace the stub Containerfile**

```dockerfile
FROM fedora:43

RUN dnf install -y python3 python3-pip && dnf clean all

WORKDIR /app

COPY pyproject.toml .
RUN pip3 install --no-cache-dir -e .

COPY anything_important/ anything_important/

CMD ["anything-important"]
```

- [ ] **Step 2: Build the image**

```bash
podman build -t anything-important .
```

Expected: Build completes without errors

- [ ] **Step 3: Verify the container starts and reads config**

```bash
podman run --rm anything-important 2>&1 | head -5
```

Expected: `KeyError: 'TELEGRAM_TOKEN'` — confirms the app starts and `Config.from_env()` runs

- [ ] **Step 4: Verify a full run with credentials mounted**

```bash
podman run --rm \
  -e TELEGRAM_TOKEN=test \
  -e TELEGRAM_CHAT_ID=123 \
  -e OLLAMA_URL=http://host.containers.internal:11434 \
  -v /path/to/oauth_credentials.json:/credentials/oauth_credentials.json:ro \
  anything-important 2>&1 | head -20
```

Expected: Logs show the app connecting to the Gmail MCP server and listing unread threads

- [ ] **Step 5: Commit**

```bash
git add Containerfile
git commit -m "feat: Containerfile, python-only no nodejs needed"
```

---

### Task 9: README update

**Files:**
- Modify: `README.md`

Replace the current stub README with full usage documentation.

- [ ] **Step 1: Write the updated README**

```markdown
# Anything important?

Is there an email that requires my attention?

A tool that periodically checks your Gmail inbox for important emails and notifies you via Telegram. Importance is assessed by a locally deployed LLM — your emails never leave your machine.

## Security model

1. Minimal dependencies — fewer packages, smaller attack surface
2. Runs in a container
3. Uses the official hosted Gmail MCP server — no Gmail credentials stored locally
4. LLM runs locally via Ollama

## Prerequisites

- [Ollama](https://ollama.com/) running locally with a model pulled (e.g. `ollama pull llama3.2`)
- A [Telegram bot token](https://core.telegram.org/bots#how-do-i-create-a-bot) and your chat ID
- Google OAuth2 credentials JSON (see setup below)

## Google OAuth2 setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable **Gmail API** and **Gmail MCP API**
3. Create OAuth 2.0 credentials (Desktop app), download the JSON
4. Run the one-time authorization flow to obtain a credentials file with a refresh token:

```bash
pip install google-auth-oauthlib
python3 -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
])
creds = flow.run_local_server()
import json, pathlib
pathlib.Path('oauth_credentials.json').write_text(creds.to_json())
print('Saved oauth_credentials.json')
"
```

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_TOKEN` | **required** | Telegram bot token |
| `TELEGRAM_CHAT_ID` | **required** | Telegram chat ID to send alerts to |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama base URL |
| `OLLAMA_MODEL` | `llama3.2` | Ollama model name |
| `CHECK_INTERVAL` | `300` | Seconds between inbox checks |
| `GMAIL_CREDENTIALS_FILE` | `/credentials/oauth_credentials.json` | Path to OAuth2 credentials JSON |

## Run

```bash
podman run --rm \
  -e TELEGRAM_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  -e OLLAMA_URL=http://host.containers.internal:11434 \
  -v /path/to/oauth_credentials.json:/credentials/oauth_credentials.json:ro \
  anything-important
```

## How it works

`anything-important` connects to the [Gmail MCP server](https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server) to read your inbox. Each unread thread is sent to the local LLM for importance assessment. Important threads trigger a Telegram notification and are marked as read.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with setup and usage instructions"
```

---

### Task 10: GitHub Actions CI

**Files:**
- Create: `.github/workflows/tests.yml`

Run the test suite on every push and pull request.

- [ ] **Step 1: Create the workflow file**

```bash
mkdir -p .github/workflows
```

```yaml
# .github/workflows/tests.yml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --dev
      - run: uv run pytest -v
```

- [ ] **Step 2: Verify the YAML is valid**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/tests.yml'))" && echo "YAML valid"
```

Expected: `YAML valid`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/tests.yml
git commit -m "ci: add github actions workflow to run tests"
```

---

## Self-Review

**Spec coverage:**
- ✅ Checks Gmail inbox periodically — `run_once` inside `_run_loop` with `CHECK_INTERVAL`
- ✅ Uses Gmail MCP server — connects to `https://gmailmcp.googleapis.com/mcp/v1` via `streamablehttp_client`
- ✅ Sends Telegram notifications — `telegram.py`
- ✅ Uses locally deployed LLM — `llm.py` calls Ollama at configurable URL
- ✅ Least dependencies — only `mcp`, `google-auth`, and `httpx`
- ✅ Runs in a container — Containerfile (Python only, no Node.js)
- ✅ By default only accesses the Gmail MCP server — the MCP session is the only external connection besides Ollama and Telegram

**Placeholder scan:** No TBDs. The discovery scripts in Task 6 are runnable commands, not placeholders. All code blocks are complete.

**Type consistency:** `Thread` dataclass defined once in `gmail.py`, imported in `main.py` and `tests/test_main.py`. `Config` defined once in `config.py`, used in `main.py` and all tests. `ClientSession` imported from `mcp` in `gmail.py` and `main.py`. No mismatches.

**Note on tool argument names:** The `search_threads`, `get_thread`, and `unlabel_message` argument names (`query`, `max_results`, `thread_id`, `message_id`, `label_name`) are inferred from the Google docs tool descriptions. The discovery step in Task 6 must be run against a live server to confirm the exact names before trusting the implementation.

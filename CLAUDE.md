# anything-important

Monitors Gmail for important emails and sends Telegram notifications using a local LLM for triage.

## Architecture

- `anything_important/config.py` — env-var config (`Config.from_env()`)
- `anything_important/auth.py` — Google OAuth2 token loading with auto-refresh
- `anything_important/gmail.py` — Gmail REST API: list threads, labels, apply labels
- `anything_important/llm.py` — LLM triage via OpenAI-compatible API (`/api/chat`)
- `anything_important/telegram.py` — Telegram bot message sender
- `anything_important/main.py` — orchestration loop + `auth` subcommand

## LLM integration

The app talks to a llama-cpp server (not Ollama) using the OpenAI-compatible response format:
`response["choices"][0]["message"]["content"]`

The LLM is prompted to respond in `ANSWER: YES/NO\nREASON: ...` format. Retries up to 3 times
with a 5-second delay on network/transport errors.

## Gmail labeling

Important threads are labeled `llm-says-important` via the Gmail API. The default query excludes
threads already carrying this label so they are never re-processed.

Default query: `is:unread newer_than:5d -label:llm-says-important`

## Running tests

```
.venv/bin/python -m pytest tests/ -q
```

Tests use `pytest-asyncio` in `auto` mode (no `@pytest.mark.asyncio` needed).

## Build & run

```
make build          # podman build -t anything-important .
make run            # requires TELEGRAM_TOKEN and TELEGRAM_CHAT_ID env vars
```

The container uses `--network host` so it can reach a llama-cpp server on the host.

## Auth (headless OAuth2)

```
python anything_important/main.py auth [--client-secret FILE] [--output FILE] [--port PORT]
```

Prints an auth URL, waits for you to paste the redirect URL back (no browser required).
After Google approval, copy the full `http://localhost:<port>/?code=...` URL from the browser
address bar and paste it at the prompt. The `--port` must match an authorized redirect URI
in the Google Cloud Console.

## Key env vars

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_TOKEN` | required | Telegram bot token |
| `TELEGRAM_CHAT_ID` | required | Telegram chat ID |
| `LLM_URL` | `http://localhost:11434` | LLM server base URL |
| `LLM_MODEL` | `llama3.2` | Model name |
| `CHECK_INTERVAL` | `300` | Seconds between checks |
| `GMAIL_CREDENTIALS_FILE` | `/credentials/oauth_credentials.json` | OAuth2 credentials path |
| `GMAIL_QUERY` | `is:unread newer_than:5d -label:llm-says-important` | Gmail search query |

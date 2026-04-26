# Anything Important?

Is there an email that requires my attention?

A tool that periodically checks your Gmail inbox for important emails and
notifies you via Telegram. Importance is assessed by a locally deployed LLM —
your emails never leave your machine.

## Security model

1. Minimal dependencies — fewer packages, smaller attack surface
2. Runs in a container
3. Uses the Gmail REST API — no third-party email access
4. LLM runs locally (using OpenAI-compatible API)

## Prerequisites

- [Ollama](https://ollama.com/) running locally with a model pulled (e.g. `ollama pull llama3.2`)
- A [Telegram bot token](https://core.telegram.org/bots#how-do-i-create-a-bot) and your chat ID
- Google OAuth2 credentials JSON (see setup below)

## Google OAuth2 setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app), download the JSON
4. Run the one-time authorization flow to obtain a credentials file with a refresh token:

```bash
pip install google-auth-oauthlib
python3 -c "
from google_auth_oauthlib.flow import InstalledAppFlow
flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.modify',
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
| `GMAIL_QUERY` | `is:unread` | Gmail search query to filter threads |

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

`anything-important` uses the Gmail REST API to read your inbox. Each unread thread is sent to the local LLM for importance assessment. Important threads trigger a Telegram notification and are marked as read.

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

- A local LLM server exposing an OpenAI-compatible API (e.g. [llama-cpp](https://github.com/ggerganov/llama.cpp))
- A [Telegram bot token](https://core.telegram.org/bots#how-do-i-create-a-bot) and your chat ID
- Google OAuth2 credentials JSON (see setup below)

## Google OAuth2 setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project and enable the **Gmail API**
3. Create OAuth 2.0 credentials (Desktop app), download the JSON
4. Add `http://localhost:8080` (or your chosen `--port`) as an authorized redirect URI
5. Run the one-time authorization flow to obtain a credentials file with a refresh token:

```bash
anything-important auth --client-secret client_secret.json
```

This prints an authorization URL. Open it in any browser, approve access, then copy the
full redirect URL from the browser's address bar (e.g. `http://localhost:8080/?code=...`)
and paste it at the prompt. The credentials are saved to `oauth_credentials.json`.

Use `--port PORT` if port 8080 is in use (update the authorized redirect URI to match).

## Configuration

All configuration is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_TOKEN` | **required** | Telegram bot token |
| `TELEGRAM_CHAT_ID` | **required** | Telegram chat ID to send alerts to |
| `LLM_URL` | `http://localhost:11434` | LLM server base URL |
| `LLM_MODEL` | `llama3.2` | Model name |
| `CHECK_INTERVAL` | `300` | Seconds between inbox checks |
| `GMAIL_CREDENTIALS_FILE` | `/credentials/oauth_credentials.json` | Path to OAuth2 credentials JSON |
| `GMAIL_QUERY` | `is:unread newer_than:5d -label:llm-says-important -label:llm-says-meh` | Gmail search query to filter threads |

## Run

```bash
make build
```

Create a `.env` file with the required variables:

```
TELEGRAM_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

Then run:

```bash
make run
```

Or directly with podman:

```bash
podman run --rm \
  --network host \
  -e TELEGRAM_TOKEN=your_token \
  -e TELEGRAM_CHAT_ID=your_chat_id \
  -e LLM_URL=http://localhost:8080 \
  -v /path/to/oauth_credentials.json:/credentials/oauth_credentials.json:ro,Z \
  anything-important
```

`--network host` is needed so the container can reach a LLM server running on the host.

## How it works

`anything-important` uses the Gmail REST API to read your inbox. On startup it fetches up to
100 of your starred, important, or previously labeled threads and uses their sender and subject
lines as calibration examples for the LLM — so importance judgement is personalised to you.

Each unread thread is then sent to the local LLM for importance assessment:
- **Important** — triggers a Telegram notification and is labeled `llm-says-important` so it is not re-processed.
- **Not important** — labeled `llm-says-meh` and excluded from future queries.

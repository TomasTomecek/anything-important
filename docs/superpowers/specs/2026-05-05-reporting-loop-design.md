# Reporting Loop Design

**Date:** 2026-05-05
**Status:** Approved

## Overview

Replace per-email immediate Telegram notifications with a batched digest sent once per triage cycle. Each important email is summarized by the LLM; if summarization fails, the first 250 characters of the email body are used as a fallback.

## Data Flow

Within each `run_once` call:

1. Triage all unread threads as before.
2. Important threads: apply `llm-says-important` label, append to `important_threads` list — **no immediate Telegram send**.
3. Non-important threads: apply `llm-says-meh` label (unchanged).
4. After all threads are processed:
   - If `important_threads` is empty: do nothing.
   - Otherwise: summarize each thread, compose one Telegram message, send it.

## LLM Changes (`llm.py`)

### Refactor: `_call_llm` helper

Extract the shared retry/transport-error logic from `assess_importance` into a private `_call_llm(llm_url, model, prompt) -> str` coroutine. Both `assess_importance` and the new `summarize_email` use it.

### New: `summarize_email`

```python
async def summarize_email(llm_url: str, model: str, sender: str, subject: str, body: str) -> str
```

Prompt instructs the LLM to write 2–3 sentences focusing on action items, deadlines, and key decisions. Returns plain text. Uses `_call_llm` internally. Body is truncated to `_MAX_BODY` (2000 chars) before being sent to the LLM, same as `assess_importance`.

## `run_once` Changes (`main.py`)

- Collect important `Thread` objects in a list during the triage loop instead of calling `send_message` immediately.
- After the loop, if the list is non-empty:
  - For each thread, call `summarize_email`. On failure (exception after retries), fall back to `thread.body[:250]`.
  - Compose one message and call `send_message` once.

## Telegram Message Format

```
📧 2 important emails:

1. From: boss@example.com
   Subject: Q3 planning
   Let's align on Q3 priorities before the board meeting. I need your input on...

2. From: hr@example.com
   Subject: Benefits enrollment
   Open enrollment closes Friday. Please log in to the portal and confirm your...
```

## Config

No new environment variables. The reporting loop reuses `CHECK_INTERVAL`, `LLM_URL`, `LLM_MODEL`, `TELEGRAM_TOKEN`, and `TELEGRAM_CHAT_ID`.

## Error Handling

| Failure | Behaviour |
|---|---|
| `summarize_email` raises after retries | Log warning; use `thread.body[:250]` as fallback |
| `send_message` fails | Log error (same as existing behaviour) |

## Testing

- `test_llm.py`: add tests for `summarize_email` and `_call_llm`.
- `test_main.py`:
  - Multiple important threads produce exactly one `send_message` call containing all entries.
  - Non-important threads are absent from the batch message.
  - Zero important threads → `send_message` not called.
  - Summarization failure for one thread falls back to truncated body in the message.

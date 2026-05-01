# LLM Triage: Example Subjects from Important Emails

## Problem

The LLM triage uses generic importance criteria. It has no knowledge of what the specific user considers important, leading to false negatives (missing emails the user cares about) and false positives (flagging emails the user doesn't care about).

## Solution

At application startup, fetch the newest 100 emails that the user has marked as starred, important, or previously labeled `llm-says-important`. Include their sender and subject lines in the LLM prompt as few-shot calibration examples. This gives the LLM personalized context about the user's importance preferences.

## Design

### Gmail: `list_important_subjects`

New async function in `anything_important/gmail.py`:

```python
async def list_important_subjects(
    client: httpx.AsyncClient, max_results: int = 100
) -> list[tuple[str, str]]:
```

- Query: `is:starred OR is:important OR label:llm-says-important`
- `maxResults` capped at 100
- Returns `(sender, subject)` tuples from the first message of each thread
- Only reads headers (no body decoding)

### LLM: extended prompt

`assess_importance` in `anything_important/llm.py` gains an optional parameter:

```python
async def assess_importance(
    llm_url: str,
    model: str,
    sender: str,
    subject: str,
    body: str,
    known_important: list[tuple[str, str]] | None = None,
) -> bool:
```

When `known_important` is provided and non-empty, the prompt is extended with a section between the importance criteria and the email-to-triage:

```
Here are examples of emails the recipient has previously considered important:
- From: boss@example.com — Subject: Q2 budget review
- From: wife@gmail.com — Subject: Pick up kids today
...

Use these examples to calibrate your judgment about what this recipient considers important.
```

When `known_important` is `None` or empty, the prompt is unchanged from today.

### Main: orchestration

In `anything_important/main.py`:

1. `_run_loop` fetches examples once before the loop using a one-shot `_gmail_client` context, then passes them to `run_once` on each iteration.
2. `run_once` gains `known_important` parameter, passes it through to `assess_importance`.
3. If the initial fetch fails, the app crashes (fail-fast — can't triage well without examples).

No config changes needed. The example query is hardcoded.

### Testing

- `test_llm.py`: Test that `known_important` examples appear in the prompt. Test that `None`/empty omits the section.
- `test_gmail.py`: Test `list_important_subjects` returns `(sender, subject)` tuples from thread details.
- `test_main.py`: Test that `run_once` passes `known_important` through to `assess_importance`.

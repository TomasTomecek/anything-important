import asyncio
import logging

import httpx

log = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_DELAY = 5.0

_PROMPT = """\
You are an email triage assistant. Decide if the following email is important.

Important emails are ones that:
- Require a decision or action from the recipient
- Involve money, payments, invoices, or financial matters
- Involve scheduling, meetings, or the recipient's time
- Are from family, friends, or close colleagues
- Contain urgent or time-sensitive information

Not important emails are ones that:
- Are marketing, promotions, newsletters, or advertisements
- Are automated notifications that require no action
- Are spam or bulk mail

Respond in exactly this format:
ANSWER: YES or NO
REASON: one sentence explanation

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
    last_exc: Exception = RuntimeError("no attempts made")
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                response = await client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"].strip()
                break
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < _RETRY_ATTEMPTS:
                    log.warning("LLM request failed (attempt %d/%d): %s — retrying in %gs",
                                attempt, _RETRY_ATTEMPTS, exc, _RETRY_DELAY)
                    await asyncio.sleep(_RETRY_DELAY)
                else:
                    log.error("LLM request failed after %d attempts: %s", _RETRY_ATTEMPTS, exc)
                    raise

    answer = "NO"
    reason = ""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("ANSWER:"):
            answer = line.split(":", 1)[1].strip().upper()
        elif line.upper().startswith("REASON:"):
            reason = line.split(":", 1)[1].strip()

    important = answer.startswith("YES")
    log.info("Decision: %s — %s", answer, reason)
    return important

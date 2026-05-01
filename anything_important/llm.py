import asyncio
import logging

import httpx

log = logging.getLogger(__name__)

_RETRY_ATTEMPTS = 3
_RETRY_DELAY = 5.0

_PROMPT = """\
You are an email triage assistant. Decide if the following email is important.

{examples_section}Respond in exactly this format:
ANSWER: YES or NO
REASON: one sentence explanation

From: {sender}
Subject: {subject}
Body:
{body}"""

_EXAMPLES_SECTION = """\
Here are examples of emails the recipient has previously considered important:
{examples}

Use these examples to calibrate your judgment about what this recipient considers important.

"""

_MAX_BODY = 2000


async def assess_importance(
    llm_url: str,
    model: str,
    sender: str,
    subject: str,
    body: str,
    known_important: list[tuple[str, str]] | None = None,
) -> bool:
    if known_important:
        lines = "\n".join(f"- From: {s} — Subject: {sub}" for s, sub in known_important)
        examples_section = _EXAMPLES_SECTION.format(examples=lines)
    else:
        examples_section = ""
    prompt = _PROMPT.format(
        examples_section=examples_section,
        sender=sender,
        subject=subject,
        body=body[:_MAX_BODY],
    )
    last_exc: Exception = RuntimeError("no attempts made")
    async with httpx.AsyncClient(timeout=180.0) as client:
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                response = await client.post(
                    f"{llm_url}/api/chat",
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                        "reasoning_effort": "medium",
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

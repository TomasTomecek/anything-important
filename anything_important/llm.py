import httpx

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

Respond with only YES (important) or NO (not important).

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
        answer = response.json()["choices"][0]["message"]["content"].strip().upper()
        return answer.startswith("YES")

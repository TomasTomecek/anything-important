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
        answer = response.json()["choices"][0]["message"]["content"].strip().upper()
        return answer.startswith("YES")

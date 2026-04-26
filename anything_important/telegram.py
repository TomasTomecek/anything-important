import httpx


async def send_message(token: str, chat_id: str, text: str) -> None:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()

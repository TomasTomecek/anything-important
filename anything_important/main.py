import asyncio
import logging
from contextlib import asynccontextmanager

import httpx

from anything_important.auth import get_access_token
from anything_important.config import Config
from anything_important.gmail import list_unread_threads, mark_thread_read
from anything_important.llm import assess_importance
from anything_important.telegram import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_GMAIL_BASE_URL = "https://gmail.googleapis.com"


async def run_once(config: Config, client: httpx.AsyncClient) -> None:
    threads = await list_unread_threads(client, query=config.gmail_query)
    log.info("Found %d unread threads", len(threads))
    for thread in threads:
        important = await assess_importance(
            ollama_url=config.ollama_url,
            model=config.ollama_model,
            sender=thread.sender,
            subject=thread.subject,
            body=thread.body,
        )
        if important:
            log.info("Important: %s — %s", thread.sender, thread.subject)
            await send_message(
                token=config.telegram_token,
                chat_id=config.telegram_chat_id,
                text=f"📧 Important email from {thread.sender}\nSubject: {thread.subject}",
            )
            await mark_thread_read(client, thread_id=thread.id)
        else:
            log.info("Skipping unimportant thread from %s", thread.sender)


@asynccontextmanager
async def _gmail_client(config: Config):
    token = get_access_token(config.gmail_credentials_file)
    async with httpx.AsyncClient(
        base_url=_GMAIL_BASE_URL,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        yield client


async def _run_loop(config: Config) -> None:
    while True:
        try:
            async with _gmail_client(config) as client:
                await run_once(config, client)
        except Exception:
            log.exception("Error during check cycle")
        log.info("Sleeping %ds until next check", config.check_interval)
        await asyncio.sleep(config.check_interval)


def main() -> None:
    config = Config.from_env()
    asyncio.run(_run_loop(config))


if __name__ == "__main__":
    main()

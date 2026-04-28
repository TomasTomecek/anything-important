import argparse
import asyncio
import logging
import pathlib
from contextlib import asynccontextmanager

import httpx
from google_auth_oauthlib.flow import InstalledAppFlow

from anything_important.auth import get_access_token
from anything_important.config import Config
from anything_important.gmail import apply_label, get_or_create_label, list_unread_threads, mark_thread_read
from anything_important.llm import assess_importance
from anything_important.telegram import send_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

_GMAIL_BASE_URL = "https://gmail.googleapis.com"
_GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]


_IMPORTANT_LABEL = "llm-says-important"


async def run_once(config: Config, client: httpx.AsyncClient) -> None:
    label_id = await get_or_create_label(client, _IMPORTANT_LABEL)
    threads = await list_unread_threads(client, query=config.gmail_query)
    log.info("Found %d unread threads", len(threads))
    for thread in threads:
        important = await assess_importance(
            llm_url=config.llm_url,
            model=config.llm_model,
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
            await apply_label(client, thread_id=thread.id, label_id=label_id)
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


def _cmd_auth(args: argparse.Namespace) -> None:
    flow = InstalledAppFlow.from_client_secrets_file(args.client_secret, _GMAIL_SCOPES)
    flow.redirect_uri = f"http://localhost:{args.port}"
    auth_url, _ = flow.authorization_url(prompt="consent")
    print(f"Open this URL in a browser:\n\n  {auth_url}\n")
    redirect_response = input("After approving, paste the full redirect URL here: ").strip()
    flow.fetch_token(authorization_response=redirect_response)
    pathlib.Path(args.output).write_text(flow.credentials.to_json())
    print(f"Saved {args.output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Notify via Telegram when important Gmail arrives")
    subparsers = parser.add_subparsers(dest="command")

    auth_parser = subparsers.add_parser("auth", help="Set up Gmail OAuth2 credentials")
    auth_parser.add_argument("--client-secret", default="client_secret.json", metavar="FILE",
                             help="OAuth2 client secrets JSON from Google Cloud Console (default: client_secret.json)")
    auth_parser.add_argument("--output", default="oauth_credentials.json", metavar="FILE",
                             help="Where to save the credentials (default: oauth_credentials.json)")
    auth_parser.add_argument("--port", type=int, default=8080, metavar="PORT",
                             help="Local port for the OAuth2 redirect (default: 8080)")

    args = parser.parse_args()

    if args.command == "auth":
        _cmd_auth(args)
    else:
        config = Config.from_env()
        asyncio.run(_run_loop(config))


if __name__ == "__main__":
    main()

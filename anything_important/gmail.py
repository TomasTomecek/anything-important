import base64
import logging
import html as html_module
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

log = logging.getLogger(__name__)


@dataclass
class Thread:
    id: str
    message_id: str
    sender: str
    subject: str
    body: str


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(text: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(text)
    return html_module.unescape(parser.get_text())


def _extract_body(payload: dict) -> str:
    mime_type = payload.get("mimeType", "")
    if mime_type.startswith("multipart/"):
        parts = payload.get("parts", [])
        for part in parts:
            if part.get("mimeType") == "text/plain":
                data = part.get("body", {}).get("data", "")
                if data:
                    return _decode_body(data)
        for part in parts:
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    return _strip_html(_decode_body(data))
        for part in parts:
            if part.get("mimeType", "").startswith("multipart/"):
                text = _extract_body(part)
                if text:
                    return text
        return ""
    data = payload.get("body", {}).get("data", "")
    if not data:
        return ""
    text = _decode_body(data)
    return _strip_html(text) if mime_type == "text/html" else text


async def list_unread_threads(client: httpx.AsyncClient, query: str = "is:unread") -> list[Thread]:
    response = await client.get(
        "/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": 20},
    )
    response.raise_for_status()
    thread_stubs = response.json().get("threads", [])
    # TODO: fetch thread details concurrently with asyncio.gather instead of sequentially
    threads = []
    for stub in thread_stubs:
        detail_response = await client.get(
            f"/gmail/v1/users/me/threads/{stub['id']}",
            params={"format": "full"},
        )
        detail_response.raise_for_status()
        detail = detail_response.json()
        messages = detail.get("messages", [])
        if not messages:
            continue
        first = messages[0]
        payload = first.get("payload", {})
        headers = payload.get("headers", [])
        threads.append(
            Thread(
                id=detail["id"],
                message_id=first["id"],
                sender=_header(headers, "From"),
                subject=_header(headers, "Subject"),
                body=_extract_body(payload),
            )
        )
    return threads


async def mark_thread_read(client: httpx.AsyncClient, thread_id: str) -> None:
    response = await client.post(
        f"/gmail/v1/users/me/threads/{thread_id}/modify",
        json={"removeLabelIds": ["UNREAD"]},
    )
    response.raise_for_status()


async def get_or_create_label(client: httpx.AsyncClient, name: str) -> str:
    response = await client.get("/gmail/v1/users/me/labels")
    response.raise_for_status()
    for label in response.json().get("labels", []):
        if label["name"] == name:
            return label["id"]
    response = await client.post("/gmail/v1/users/me/labels", json={"name": name})
    response.raise_for_status()
    return response.json()["id"]


async def list_important_subjects(
    client: httpx.AsyncClient, max_results: int = 50
) -> list[tuple[str, str]]:
    query = "is:starred OR is:important OR label:llm-says-important"
    response = await client.get(
        "/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": max_results},
    )
    response.raise_for_status()
    thread_stubs = response.json().get("threads", [])
    log.info("Found %d important threads", len(thread_stubs))
    results = []
    for stub in thread_stubs:
        detail_response = await client.get(
            f"/gmail/v1/users/me/threads/{stub['id']}",
            params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
        )
        detail_response.raise_for_status()
        messages = detail_response.json().get("messages", [])
        if not messages:
            continue
        headers = messages[0].get("payload", {}).get("headers", [])
        sender = _header(headers, "From")
        subject = _header(headers, "Subject")
        if sender or subject:
            results.append((sender, subject))
    return results


async def list_unimportant_subjects(
    client: httpx.AsyncClient, max_results: int = 50
) -> list[tuple[str, str]]:
    query = "label:llm-says-meh OR (-is:important -is:starred -label:llm-says-important)"
    response = await client.get(
        "/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": max_results},
    )
    response.raise_for_status()
    thread_stubs = response.json().get("threads", [])
    log.info("Found %d important threads", len(thread_stubs))
    results = []
    for stub in thread_stubs:
        detail_response = await client.get(
            f"/gmail/v1/users/me/threads/{stub['id']}",
            params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
        )
        detail_response.raise_for_status()
        messages = detail_response.json().get("messages", [])
        if not messages:
            continue
        headers = messages[0].get("payload", {}).get("headers", [])
        sender = _header(headers, "From")
        subject = _header(headers, "Subject")
        if sender or subject:
            results.append((sender, subject))
    return results


async def apply_label(client: httpx.AsyncClient, thread_id: str, label_id: str) -> None:
    response = await client.post(
        f"/gmail/v1/users/me/threads/{thread_id}/modify",
        json={"addLabelIds": [label_id]},
    )
    response.raise_for_status()

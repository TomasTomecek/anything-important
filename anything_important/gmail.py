import base64
from dataclasses import dataclass

import httpx


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


async def list_unread_threads(client: httpx.AsyncClient, query: str = "is:unread") -> list[Thread]:
    response = await client.get(
        "/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": 20},
    )
    response.raise_for_status()
    thread_stubs = response.json().get("threads", [])
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
        headers = first.get("payload", {}).get("headers", [])
        body_data = first.get("payload", {}).get("body", {}).get("data", "")
        threads.append(
            Thread(
                id=detail["id"],
                message_id=first["id"],
                sender=_header(headers, "From"),
                subject=_header(headers, "Subject"),
                body=_decode_body(body_data),
            )
        )
    return threads


async def mark_thread_read(client: httpx.AsyncClient, thread_id: str) -> None:
    response = await client.post(
        f"/gmail/v1/users/me/threads/{thread_id}/modify",
        json={"removeLabelIds": ["UNREAD"]},
    )
    response.raise_for_status()

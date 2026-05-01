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
    client: httpx.AsyncClient, max_results: int = 100
) -> list[tuple[str, str]]:
    query = "is:starred OR is:important OR label:llm-says-important"
    response = await client.get(
        "/gmail/v1/users/me/threads",
        params={"q": query, "maxResults": max_results},
    )
    response.raise_for_status()
    thread_stubs = response.json().get("threads", [])
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

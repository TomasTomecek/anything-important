import base64
import json
from dataclasses import dataclass

from mcp import ClientSession


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


async def list_unread_threads(session: ClientSession, query: str = "is:unread") -> list[Thread]:
    result = await session.call_tool(
        "search_threads",
        {"query": query, "max_results": 20},
    )
    thread_stubs = json.loads(result.content[0].text)
    threads = []
    for stub in thread_stubs:
        detail_result = await session.call_tool("get_thread", {"thread_id": stub["id"]})
        detail = json.loads(detail_result.content[0].text)
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


async def mark_thread_read(session: ClientSession, message_id: str) -> None:
    await session.call_tool(
        "unlabel_message",
        {"message_id": message_id, "label_name": "UNREAD"},
    )

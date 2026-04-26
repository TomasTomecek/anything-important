import json
from unittest.mock import AsyncMock, MagicMock
import pytest
from anything_important.gmail import Thread, list_unread_threads, mark_thread_read


def _tool_result(data: object) -> MagicMock:
    content = MagicMock()
    content.text = json.dumps(data)
    result = MagicMock()
    result.content = [content]
    return result


def _make_session(**tool_responses) -> AsyncMock:
    session = AsyncMock()

    async def call_tool(name, args=None):
        return tool_responses[name]

    session.call_tool = AsyncMock(side_effect=call_tool)
    return session


async def test_list_unread_threads_returns_thread_objects():
    search_result = _tool_result([{"id": "t1"}])
    thread_result = _tool_result({
        "id": "t1",
        "messages": [{
            "id": "m1",
            "payload": {
                "headers": [
                    {"name": "From", "value": "boss@example.com"},
                    {"name": "Subject", "value": "Urgent meeting"},
                ],
                "body": {"data": "UGxlYXNlIGpvaW4gdGhlIG1lZXRpbmcu"},
            },
        }],
    })
    session = _make_session(search_threads=search_result, get_thread=thread_result)

    threads = await list_unread_threads(session, query="is:unread")

    assert len(threads) == 1
    assert threads[0].id == "t1"
    assert threads[0].message_id == "m1"
    assert threads[0].sender == "boss@example.com"
    assert threads[0].subject == "Urgent meeting"
    assert threads[0].body == "Please join the meeting."


async def test_list_unread_threads_returns_empty_when_no_threads():
    session = _make_session(search_threads=_tool_result([]))

    threads = await list_unread_threads(session, query="is:unread")

    assert threads == []


async def test_mark_thread_read_removes_unread_label():
    session = _make_session(unlabel_message=_tool_result({}))

    await mark_thread_read(session, message_id="m1")

    session.call_tool.assert_called_once_with(
        "unlabel_message",
        {"message_id": "m1", "label_name": "UNREAD"},
    )

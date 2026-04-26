from unittest.mock import AsyncMock, MagicMock
import pytest
from anything_important.gmail import Thread, list_unread_threads, mark_thread_read


def _response(data: object) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=data)
    return resp


async def test_list_unread_threads_returns_thread_objects():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[
        _response({"threads": [{"id": "t1"}]}),
        _response({
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
        }),
    ])

    threads = await list_unread_threads(client, query="is:unread")

    assert len(threads) == 1
    assert threads[0].id == "t1"
    assert threads[0].message_id == "m1"
    assert threads[0].sender == "boss@example.com"
    assert threads[0].subject == "Urgent meeting"
    assert threads[0].body == "Please join the meeting."


async def test_list_unread_threads_returns_empty_when_no_threads():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response({}))

    threads = await list_unread_threads(client, query="is:unread")

    assert threads == []


async def test_mark_thread_read_removes_unread_label():
    client = AsyncMock()
    client.post = AsyncMock(return_value=_response({}))

    await mark_thread_read(client, thread_id="t1")

    client.post.assert_called_once_with(
        "/gmail/v1/users/me/threads/t1/modify",
        json={"removeLabelIds": ["UNREAD"]},
    )

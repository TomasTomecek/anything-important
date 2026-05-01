from unittest.mock import AsyncMock, MagicMock
import pytest
from anything_important.gmail import Thread, apply_label, get_or_create_label, list_important_subjects, list_unread_threads, mark_thread_read


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


async def test_get_or_create_label_returns_existing_id():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response({
        "labels": [
            {"id": "Label_1", "name": "other"},
            {"id": "Label_2", "name": "llm-says-important"},
        ]
    }))

    label_id = await get_or_create_label(client, "llm-says-important")

    assert label_id == "Label_2"
    client.post.assert_not_called()


async def test_get_or_create_label_creates_when_missing():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response({"labels": [{"id": "Label_1", "name": "other"}]}))
    client.post = AsyncMock(return_value=_response({"id": "Label_99", "name": "llm-says-important"}))

    label_id = await get_or_create_label(client, "llm-says-important")

    assert label_id == "Label_99"
    client.post.assert_called_once_with(
        "/gmail/v1/users/me/labels",
        json={"name": "llm-says-important"},
    )


async def test_list_important_subjects_returns_sender_subject_tuples():
    client = AsyncMock()
    client.get = AsyncMock(side_effect=[
        _response({"threads": [{"id": "t1"}, {"id": "t2"}]}),
        _response({
            "messages": [{
                "payload": {
                    "headers": [
                        {"name": "From", "value": "boss@example.com"},
                        {"name": "Subject", "value": "Q2 budget review"},
                    ],
                },
            }],
        }),
        _response({
            "messages": [{
                "payload": {
                    "headers": [
                        {"name": "From", "value": "wife@gmail.com"},
                        {"name": "Subject", "value": "Pick up kids today"},
                    ],
                },
            }],
        }),
    ])

    results = await list_important_subjects(client)

    assert results == [
        ("boss@example.com", "Q2 budget review"),
        ("wife@gmail.com", "Pick up kids today"),
    ]
    call_args = client.get.call_args_list[0]
    assert "is:starred OR is:important OR label:llm-says-important" in str(call_args)


async def test_list_important_subjects_returns_empty_when_no_threads():
    client = AsyncMock()
    client.get = AsyncMock(return_value=_response({}))

    results = await list_important_subjects(client)

    assert results == []


async def test_apply_label_adds_label_to_thread():
    client = AsyncMock()
    client.post = AsyncMock(return_value=_response({}))

    await apply_label(client, thread_id="t1", label_id="Label_2")

    client.post.assert_called_once_with(
        "/gmail/v1/users/me/threads/t1/modify",
        json={"addLabelIds": ["Label_2"]},
    )

"""The gmail system: projection, Gmail-shaped reads, seat scoping, leakage."""

import json
import sqlite3
from pathlib import Path

import pytest
from projection_fixtures import coherent_events

from core.events import Event
from core.events.email import Attachment, EmailMessagePayload
from tools.framework import build_server, project_system
from tools.gmail import SYSTEM

OFFSTAGE_MARKERS = ("sim.", "seed_root", "config_hash", "share_policy")

MESSAGE_KEYS = [
    "id",
    "snippet",
    "subject",
    "sender",
    "toRecipients",
    "ccRecipients",
    "date",
    "plaintextBody",
    # The official Message carries both bodies; ours derives the HTML
    # alternative from the plaintext the record stores.
    "htmlBody",
    "attachmentIds",
    "attachments",
    "labelIds",
]

BUDGET_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
BUDGET_BODY = (
    "Numbers   attached under ref:Q2-BUDGET.\nPlease review the Q2 budget "
    "before Friday; flag anything that looks off and reply to me directly."
)


def gmail_events() -> list[Event]:
    """The shared fixture plus a second thread carrying an attachment."""
    events = coherent_events()
    payload = EmailMessagePayload(
        kind="email.message",
        message_id="msg-000003",
        thread_id="thr-000002",
        in_reply_to=None,
        sender="per-meredith-chao",
        to=("per-daniel-reyes",),
        cc=(),
        subject="Budget planning",
        body=BUDGET_BODY,
        attachments=(
            Attachment(
                filename="budget.xlsx",
                media_type=BUDGET_MIME,
                document_id="doc-000001",
            ),
        ),
    )
    events.append(
        Event(
            seq=len(events),
            time=90000,
            tag=payload.kind,
            source="meredith",
            payload=payload,
        )
    )
    return events


@pytest.fixture(autouse=True)
def org_wide(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WORKBENCH_SEAT", raising=False)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "gmail.db"
    project_system(SYSTEM, gmail_events(), path)
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> list:
    """Returns the parsed content items; list returns arrive one item each."""
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    return [json.loads(c.text) for c in result.content if hasattr(c, "text")]


async def search(server, **arguments) -> dict:
    [page] = await call(server, "search_threads", arguments)
    return page


async def thread_ids(server, query: str) -> list[str]:
    page = await search(server, query=query)
    return [thread["id"] for thread in page["threads"]]


def test_projection_populates_tables_and_snippet(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        messages = connection.execute(
            "SELECT message_id, thread_id, sender, snippet FROM messages ORDER BY time"
        ).fetchall()
        recipients = connection.execute(
            "SELECT person_id, kind FROM recipients WHERE message_id='msg-000001'"
        ).fetchall()
        attachments = connection.execute(
            "SELECT message_id, filename, media_type, document_id FROM attachments"
        ).fetchall()
        people = connection.execute("SELECT person_id FROM people").fetchall()
    assert [m[0] for m in messages] == ["msg-000001", "msg-000002", "msg-000003"]
    assert messages[0] == (
        "msg-000001",
        "thr-000001",
        "per-jess-alvarez",
        "Please review.",
    )
    snippet = messages[2][3]
    assert snippet == " ".join(BUDGET_BODY.split())[:100]
    assert len(snippet) == 100
    assert "\n" not in snippet and "  " not in snippet
    assert ("per-tom-okafor", "to") in recipients
    assert ("per-meredith-chao", "cc") in recipients
    assert attachments == [("msg-000003", "budget.xlsx", BUDGET_MIME, "doc-000001")]
    assert len(people) == 4


async def test_search_threads_default_returns_all(server) -> None:
    page = await search(server)
    assert [t["id"] for t in page["threads"]] == ["thr-000001", "thr-000002"]
    assert page["nextPageToken"] is None
    assert page["resultCountEstimate"] == "2"
    first = page["threads"][0]
    assert [m["id"] for m in first["messages"]] == ["msg-000001", "msg-000002"]


async def test_search_threads_bare_terms_and_conjunction(server) -> None:
    assert await thread_ids(server, "nda review") == ["thr-000001"]
    assert await thread_ids(server, "budget friday") == ["thr-000002"]
    assert await thread_ids(server, "nda budget") == []
    assert await thread_ids(server, "review") == ["thr-000001", "thr-000002"]


async def test_search_threads_person_operators(server) -> None:
    assert await thread_ids(server, "from:jess") == ["thr-000001"]
    assert await thread_ids(server, "from:per-meredith-chao") == ["thr-000002"]
    assert await thread_ids(server, "from:meredith@example.com") == ["thr-000002"]
    assert await thread_ids(server, 'to:"Daniel Reyes"') == ["thr-000002"]
    assert await thread_ids(server, "cc:meredith") == ["thr-000001"]
    assert await thread_ids(server, "cc:daniel") == []


async def test_search_threads_subject_phrase_and_negation(server) -> None:
    assert await thread_ids(server, "subject:BUDGET") == ["thr-000002"]
    assert await thread_ids(server, '"Filed as MTR-1"') == ["thr-000001"]
    assert await thread_ids(server, '"budget planning review"') == []
    assert await thread_ids(server, "-budget") == ["thr-000001"]
    assert await thread_ids(server, "review -from:jess") == [
        "thr-000001",
        "thr-000002",
    ]


async def test_search_threads_attachment_and_date_operators(server) -> None:
    assert await thread_ids(server, "has:attachment") == ["thr-000002"]
    assert await thread_ids(server, "-has:attachment") == ["thr-000001"]
    assert await thread_ids(server, "after:2026/03/13") == ["thr-000002"]
    assert await thread_ids(server, "before:2026/03/13") == ["thr-000001"]
    assert await thread_ids(server, "after:2026/03/12") == [
        "thr-000001",
        "thr-000002",
    ]
    assert await thread_ids(server, "before:2026/03/12") == []


async def test_search_threads_unknown_operator_is_bare_term(server) -> None:
    assert await thread_ids(server, "ref:Q2-BUDGET") == ["thr-000002"]
    assert await thread_ids(server, "ref:nowhere") == []


async def test_search_threads_pagination(server) -> None:
    first = await search(server, pageSize=1)
    assert [t["id"] for t in first["threads"]] == ["thr-000001"]
    assert first["nextPageToken"] == "1"
    assert first["resultCountEstimate"] == "2"
    second = await search(server, pageSize=1, pageToken=first["nextPageToken"])
    assert [t["id"] for t in second["threads"]] == ["thr-000002"]
    assert second["nextPageToken"] is None
    assert second["resultCountEstimate"] == "2"
    clamped = await search(server, pageSize=500)
    assert len(clamped["threads"]) == 2


async def test_get_thread_shape(server) -> None:
    [thread] = await call(server, "get_thread", {"threadId": "thr-000001"})
    assert thread["id"] == "thr-000001"
    assert [m["id"] for m in thread["messages"]] == ["msg-000001", "msg-000002"]
    first = thread["messages"][0]
    assert list(first) == MESSAGE_KEYS
    assert first["sender"] == "Jess Alvarez <jess@example.com>"
    assert first["toRecipients"] == ["Tom Okafor <tom@example.com>"]
    assert first["ccRecipients"] == ["Meredith Chao <meredith@example.com>"]
    assert first["date"] == "2026-03-12T00:03:20-07:00"
    assert first["plaintextBody"] == "Please review."
    assert first["labelIds"] == []


async def test_get_message_shape_and_attachments(server) -> None:
    [message] = await call(server, "get_message", {"messageId": "msg-000003"})
    assert list(message) == MESSAGE_KEYS
    assert message["snippet"] == " ".join(BUDGET_BODY.split())[:100]
    assert message["date"] == "2026-03-13T01:00:00-07:00"
    assert message["attachmentIds"] == ["doc-000001"]
    assert message["attachments"] == [
        {"id": "doc-000001", "mimeType": BUDGET_MIME, "filename": "budget.xlsx"}
    ]


async def test_unknown_ids_raise(server) -> None:
    with pytest.raises(Exception, match="thr-999999"):
        await server.call_tool("get_thread", {"threadId": "thr-999999"})
    with pytest.raises(Exception, match="msg-999999"):
        await server.call_tool("get_message", {"messageId": "msg-999999"})


async def test_list_labels_empty(server) -> None:
    [labels] = await call(server, "list_labels")
    assert labels == {"labels": [], "nextPageToken": None}


async def test_seat_scoping_hides_nonparticipant_mail(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKBENCH_SEAT", "per-daniel-reyes")
    page = await search(server)
    assert [t["id"] for t in page["threads"]] == ["thr-000002"]
    assert page["resultCountEstimate"] == "1"
    with pytest.raises(Exception, match="thr-000001"):
        await server.call_tool("get_thread", {"threadId": "thr-000001"})
    with pytest.raises(Exception, match="msg-000001"):
        await server.call_tool("get_message", {"messageId": "msg-000001"})


async def test_seat_scoping_trims_threads_to_participation(
    server, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKBENCH_SEAT", "per-meredith-chao")
    [thread] = await call(server, "get_thread", {"threadId": "thr-000001"})
    assert [m["id"] for m in thread["messages"]] == ["msg-000001"]


async def test_seat_labels(server, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_SEAT", "per-meredith-chao")
    [received] = await call(server, "get_message", {"messageId": "msg-000001"})
    assert received["labelIds"] == ["INBOX"]
    [sent] = await call(server, "get_message", {"messageId": "msg-000003"})
    assert sent["labelIds"] == ["SENT"]
    assert await thread_ids(server, "label:SENT") == ["thr-000002"]
    assert await thread_ids(server, "label:INBOX") == ["thr-000001"]
    assert await thread_ids(server, "label:UNREAD") == []


async def test_leakage_audit_no_offstage_markers(server) -> None:
    arguments = {
        "search_threads": {"query": ""},
        "get_thread": {"threadId": "thr-000001"},
        "get_message": {"messageId": "msg-000001"},
        "create_draft": {"subject": "Draft", "body": "Body"},
        "create_label": {"displayName": "Audit"},
        "label_message": {"messageId": "msg-000001", "labelIds": ["Label_000001"]},
        "unlabel_message": {"messageId": "msg-000001", "labelIds": ["Label_000001"]},
        "label_thread": {"threadId": "thr-000001", "labelIds": ["Label_000001"]},
        "unlabel_thread": {"threadId": "thr-000001", "labelIds": ["Label_000001"]},
        "trash_message": {"messageId": "msg-000001"},
        "untrash_message": {"messageId": "msg-000001"},
        "trash_thread": {"threadId": "thr-000001"},
        "untrash_thread": {"threadId": "thr-000001"},
        "mark_message_spam": {"messageId": "msg-000001"},
        "unmark_message_spam": {"messageId": "msg-000001"},
        "mark_thread_spam": {"threadId": "thr-000001"},
        "unmark_thread_spam": {"threadId": "thr-000001"},
    }
    for tool in await server.list_tools():
        result = await server.call_tool(tool.name, arguments.get(tool.name, {}))
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        for marker in OFFSTAGE_MARKERS:
            assert marker not in text, f"gmail.{tool.name} leaked {marker!r}"


async def test_write_surface_matches_the_official_server(server) -> None:
    """Gmail gained a write surface in v2 — drafts, labels, trash, spam.

    The one thing the official server cannot do is *send* (ADR-0005): a
    person opens the draft and sends it. That boundary is the invariant,
    not the absence of writes.
    """

    tools = await server.list_tools()
    names = {tool.name for tool in tools}
    assert {"search_threads", "get_thread", "get_message", "list_labels"} <= names
    assert {"create_draft", "create_label", "trash_message"} <= names
    for tool in tools:
        assert not any(
            verb in tool.name for verb in ("send", "update", "delete", "post")
        ), f"gmail exposes a verb the official server does not: {tool.name}"

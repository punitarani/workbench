"""Gmail surface parity: the official tool set, formats, and write semantics."""

import json
from pathlib import Path

import pytest

from workbench.core.events import Event
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.tools.framework import build_server, project_system
from workbench.tools.gmail import SYSTEM

# The official Gmail MCP server as captured 2026-08-14: 11 documented tools
# plus the 8 trash/spam tools the live server serves. No send tool exists
# (ADR-0005) — a person opens the draft and sends it.
OFFICIAL_TOOLS = frozenset(
    {
        "search_threads",
        "get_thread",
        "get_message",
        "list_drafts",
        "create_draft",
        "list_labels",
        "create_label",
        "label_message",
        "unlabel_message",
        "label_thread",
        "unlabel_thread",
        "trash_message",
        "untrash_message",
        "trash_thread",
        "untrash_thread",
        "mark_message_spam",
        "unmark_message_spam",
        "mark_thread_spam",
        "unmark_thread_spam",
    }
)


def _events() -> list[Event]:
    people = [
        ("per-ana", "Ana Reyes", "ana@calder.example", "internal"),
        ("per-ben", "Ben Ito", "ben@calder.example", "internal"),
        ("per-cli", "Cleo Vance", "cleo@kestrel.example", "external"),
    ]
    events: list[Event] = [
        Event(
            seq=0,
            event_id="evt-000000",
            time=0,
            tag="sim.run.started",
            source="gm",
            payload=SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-gmail-parity",
                seed_root=11,
                workplace_id="calder",
                config_hash="0" * 64,
                schema_version=1,
                epoch="2026-01-05T00:00:00-08:00",
                timezone="America/Los_Angeles",
            ),
        )
    ]
    seq = 0
    for person_id, name, email, affiliation in people:
        seq += 1
        events.append(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=0,
                tag="person.record",
                source="gm",
                payload=PersonRecordPayload(
                    kind="person.record",
                    person_id=person_id,
                    name=name,
                    email_address=email,
                    title="Accountant",
                    department="Tax",
                    affiliation=affiliation,
                    manager=None,
                    timezone="America/Los_Angeles",
                ),
            )
        )
    mails = [
        (
            "msg-000001",
            "thr-000001",
            None,
            "per-ana",
            ["per-ben"],
            "Close status",
            3600,
        ),
        (
            "msg-000002",
            "thr-000001",
            "msg-000001",
            "per-ben",
            ["per-ana"],
            "Re: Close status",
            7200,
        ),
        ("msg-000003", "thr-000002", None, "per-cli", ["per-ana"], "K-1 timing", 10800),
    ]
    for message_id, thread_id, reply_to, sender, to, subject, time in mails:
        seq += 1
        events.append(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=time,
                tag="email.message",
                source=sender,
                payload=EmailMessagePayload(
                    kind="email.message",
                    message_id=message_id,
                    thread_id=thread_id,
                    in_reply_to=reply_to,
                    sender=sender,
                    to=to,
                    cc=[],
                    subject=subject,
                    body=f"Body of {subject}.\n\nSecond paragraph.",
                    attachments=[],
                ),
            )
        )
    return events


@pytest.fixture
def server(tmp_path: Path):
    db_path = tmp_path / "gmail.db"
    project_system(SYSTEM, _events(), db_path)
    return build_server(SYSTEM, db_path)


async def call(server, name: str, **arguments) -> dict:
    result = await server.call_tool(name, arguments)
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


async def test_tool_inventory_matches_the_official_surface(server) -> None:
    listed = {tool.name for tool in await server.list_tools()}
    assert listed == OFFICIAL_TOOLS


async def test_no_send_tool_exists(server) -> None:
    listed = {tool.name for tool in await server.list_tools()}
    assert not any("send" in name for name in listed), (
        "the official Gmail MCP server cannot send mail; neither may we"
    )


class TestMessageFormats:
    async def test_full_content_carries_both_bodies(self, server) -> None:
        thread = await call(server, "get_thread", threadId="thr-000001")
        message = thread["messages"][0]
        assert message["plaintextBody"].startswith("Body of")
        assert message["htmlBody"] == (
            "<p>Body of Close status.</p><p>Second paragraph.</p>"
        )

    async def test_minimal_drops_the_body_but_keeps_headers(self, server) -> None:
        thread = await call(
            server, "get_thread", threadId="thr-000001", messageFormat="MINIMAL"
        )
        message = thread["messages"][0]
        assert "plaintextBody" not in message
        assert message["subject"] == "Close status"
        assert message["snippet"]

    async def test_metadata_only_drops_subject_snippet_and_filenames(
        self, server
    ) -> None:
        message = await call(
            server,
            "get_message",
            messageId="msg-000001",
            messageFormat="METADATA_ONLY",
        )
        assert "subject" not in message and "snippet" not in message
        assert "plaintextBody" not in message
        assert message["sender"].startswith("Ana Reyes <")

    async def test_search_view_selects_the_message_shape(self, server) -> None:
        minimal = await call(
            server, "search_threads", query="Close", view="THREAD_VIEW_MINIMAL"
        )
        assert "plaintextBody" not in minimal["threads"][0]["messages"][0]
        metadata = await call(
            server,
            "search_threads",
            query="Close",
            view="THREAD_VIEW_METADATA_ONLY",
        )
        assert "subject" not in metadata["threads"][0]["messages"][0]

    async def test_unnamed_view_returns_bodies_a_documented_divergence(
        self, server
    ) -> None:
        """Google's search never returns bodies; ours does by default.

        The frozen Hartwell floor scripts read bodies straight from search
        results, so tightening the default is its own change rather than a
        side effect of this one. The waiver lives in the pinned snapshot,
        and every named view behaves exactly as documented.
        """

        default = await call(server, "search_threads", query="Close")
        assert "plaintextBody" in default["threads"][0]["messages"][0]


class TestLabels:
    async def test_create_apply_and_list(self, server) -> None:
        label = await call(server, "create_label", displayName="Review")
        assert label["labelId"].startswith("Label_")
        await call(
            server, "label_message", messageId="msg-000001", labelIds=[label["labelId"]]
        )
        message = await call(server, "get_message", messageId="msg-000001")
        assert label["labelId"] in message["labelIds"]
        listing = await call(server, "list_labels")
        assert listing["labels"][0]["threadsTotal"] == 1
        assert listing["labels"][0]["color"] == {
            "textColor": "#000000",
            "backgroundColor": "#ffffff",
        }

    async def test_labelling_is_idempotent(self, server) -> None:
        label = await call(server, "create_label", displayName="Review")
        for _ in range(3):
            await call(
                server,
                "label_message",
                messageId="msg-000001",
                labelIds=[label["labelId"]],
            )
        message = await call(server, "get_message", messageId="msg-000001")
        assert message["labelIds"].count(label["labelId"]) == 1

    async def test_thread_labels_fan_out_and_unlabel_removes(self, server) -> None:
        label = await call(server, "create_label", displayName="Review")
        await call(
            server, "label_thread", threadId="thr-000001", labelIds=[label["labelId"]]
        )
        thread = await call(server, "get_thread", threadId="thr-000001")
        assert all(label["labelId"] in m["labelIds"] for m in thread["messages"])
        await call(
            server, "unlabel_thread", threadId="thr-000001", labelIds=[label["labelId"]]
        )
        thread = await call(server, "get_thread", threadId="thr-000001")
        assert all(label["labelId"] not in m["labelIds"] for m in thread["messages"])

    async def test_unknown_message_is_rejected(self, server) -> None:
        with pytest.raises(Exception):  # noqa: B017 - MCP wraps as ToolError
            await server.call_tool(
                "label_message", {"messageId": "msg-999999", "labelIds": ["X"]}
            )


class TestTrashAndSpam:
    async def test_trash_hides_from_search_until_include_trash(self, server) -> None:
        await call(server, "trash_thread", threadId="thr-000001")
        plain = await call(server, "search_threads", query="Close")
        assert plain["threads"] == []
        included = await call(
            server, "search_threads", query="Close", includeTrash=True
        )
        assert [t["id"] for t in included["threads"]] == ["thr-000001"]
        assert "TRASH" in included["threads"][0]["messages"][0]["labelIds"]

    async def test_untrash_restores(self, server) -> None:
        await call(server, "trash_message", messageId="msg-000003")
        assert (await call(server, "search_threads", query="K-1"))["threads"] == []
        await call(server, "untrash_message", messageId="msg-000003")
        assert (await call(server, "search_threads", query="K-1"))["threads"]

    async def test_spam_marks_and_unmarks(self, server) -> None:
        await call(server, "mark_thread_spam", threadId="thr-000002")
        message = await call(server, "get_message", messageId="msg-000003")
        assert "SPAM" in message["labelIds"]
        await call(server, "unmark_thread_spam", threadId="thr-000002")
        message = await call(server, "get_message", messageId="msg-000003")
        assert "SPAM" not in message["labelIds"]


class TestDrafts:
    async def test_create_and_list(self, server) -> None:
        draft = await call(
            server,
            "create_draft",
            to=["cleo@kestrel.example"],
            cc=["ben@calder.example"],
            subject="Re: K-1 timing",
            body="Drafts do not send.",
        )
        assert draft["toRecipients"] == ["cleo@kestrel.example"]
        assert draft["ccRecipients"] == ["ben@calder.example"]
        assert draft["htmlBody"] == "<p>Drafts do not send.</p>"
        listing = await call(server, "list_drafts")
        assert [d["id"] for d in listing["drafts"]] == [draft["id"]]

    async def test_reply_draft_inherits_the_thread(self, server) -> None:
        draft = await call(
            server,
            "create_draft",
            subject="Re",
            body="x",
            replyToMessageId="msg-000001",
        )
        assert draft["threadId"] == "thr-000001"

    async def test_reply_to_unknown_message_is_rejected(self, server) -> None:
        with pytest.raises(Exception):  # noqa: B017 - MCP wraps as ToolError
            await server.call_tool(
                "create_draft", {"body": "x", "replyToMessageId": "msg-999999"}
            )


async def test_label_pagination(server) -> None:
    for index in range(5):
        await call(server, "create_label", displayName=f"L{index}")
    first = await call(server, "list_labels", pageSize=2)
    assert len(first["labels"]) == 2
    assert first["nextPageToken"] == "2"
    last = await call(server, "list_labels", pageSize=2, pageToken="4")
    assert last["nextPageToken"] is None

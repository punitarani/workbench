"""Slack surface parity: the official nineteen tools, formats, and writes."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from mcp.server import MCPServer

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.tools.framework import build_server, project_system
from workbench.tools.slack import SYSTEM

# The official Slack MCP server (GA February 2026, mcp.slack.com) as
# captured 2026-08-14: twelve reads and seven writes.
OFFICIAL_TOOLS = frozenset(
    {
        "slack_search_channels",
        "slack_read_channel",
        "slack_read_thread",
        "slack_search_public",
        "slack_search_public_and_private",
        "slack_search_users",
        "slack_read_user_profile",
        "slack_list_channel_members",
        "slack_get_reactions",
        "slack_search_emojis",
        "slack_read_file",
        "slack_read_canvas",
        "slack_send_message",
        "slack_send_message_draft",
        "slack_schedule_message",
        "slack_create_conversation",
        "slack_add_reaction",
        "slack_create_canvas",
        "slack_update_canvas",
    }
)

EPOCH = datetime(2026, 1, 5, tzinfo=ZoneInfo("America/Los_Angeles"))
CLOSE, DM = "cnv-000001", "cnv-000002"
C_CLOSE, C_DM, C_NEW = "C00000001", "C00000002", "C00000003"
U_ANA, U_BEN, U_CLEO = "U00000001", "U00000002", "U00000003"


def _ts(seconds: int) -> str:
    """The ts the projector derives for a message at this simulated second."""

    return f"{int(EPOCH.timestamp()) + seconds}.000000"


TS_PARENT, TS_REPLY, TS_DM = _ts(3600), _ts(7200), _ts(10800)


def _events() -> list[Event]:
    events: list[Event] = [
        Event(
            seq=0,
            event_id="evt-000000",
            time=0,
            tag="sim.run.started",
            source="gm",
            payload=SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-slack-parity",
                seed_root=7,
                workplace_id="calder",
                config_hash="0" * 64,
                schema_version=1,
                epoch=EPOCH.isoformat(),
                timezone="America/Los_Angeles",
            ),
        )
    ]
    people = [
        ("per-ana", "Ana Reyes", "ana@calder.example", "internal"),
        ("per-ben", "Ben Ito", "ben@calder.example", "internal"),
        ("per-cleo", "Cleo Vance", "cleo@kestrel.example", "external"),
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
    conversations = [
        (CLOSE, "channel", "#close-2026", ("per-ana", "per-ben"), "January close"),
        (DM, "dm", None, ("per-ana", "per-cleo"), ""),
    ]
    for conversation_id, kind, name, members, topic in conversations:
        seq += 1
        events.append(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=0,
                tag="chat.conversation.created",
                source="gm",
                payload=ChatConversationCreatedPayload(
                    kind="chat.conversation.created",
                    conversation_id=conversation_id,
                    conversation_type=kind,
                    name=name,
                    members=members,
                    topic=topic,
                    purpose="Close the books" if topic else "",
                ),
            )
        )
    messages = [
        (
            "chm-000001",
            CLOSE,
            None,
            "per-ana",
            "Kestrel trial balance is posted.",
            3600,
        ),
        (
            "chm-000002",
            CLOSE,
            "chm-000001",
            "per-ben",
            "Reviewing the Kestrel tie-out now.",
            7200,
        ),
        ("chm-000003", DM, None, "per-cleo", "Kestrel K-1 timing question.", 10800),
    ]
    for message_id, conversation_id, reply_to, sender, body, time in messages:
        seq += 1
        events.append(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=time,
                tag="chat.message",
                source=sender,
                payload=ChatMessagePayload(
                    kind="chat.message",
                    chat_message_id=message_id,
                    conversation_id=conversation_id,
                    reply_to=reply_to,
                    sender=sender,
                    body=body,
                ),
            )
        )
    seq += 1
    events.append(
        Event(
            seq=seq,
            event_id=f"evt-{seq:06d}",
            time=7300,
            tag="chat.reaction.added",
            source="per-ben",
            payload=ChatReactionAddedPayload(
                kind="chat.reaction.added",
                conversation_id=CLOSE,
                chat_message_id="chm-000001",
                person_id="per-ben",
                emoji="thumbsup",
            ),
        )
    )
    return events


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "slack.db"
    project_system(SYSTEM, _events(), path)
    return path


@pytest.fixture
def server(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> MCPServer:
    # Writing needs a seat; Ana belongs to both conversations.
    monkeypatch.setenv("WORKBENCH_SEAT", "per-ana")
    return build_server(SYSTEM, db_path)


async def call(server: MCPServer, name: str, **arguments) -> dict:
    result = await server.call_tool(name, arguments)
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def _rows(db_path: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(sql).fetchall()


async def test_tool_inventory_matches_the_official_surface(server: MCPServer) -> None:
    listed = {tool.name for tool in await server.list_tools()}
    assert listed == OFFICIAL_TOOLS


class TestResponseFormat:
    async def test_channels_detail_concise_and_ids(self, server: MCPServer) -> None:
        detailed = await call(server, "slack_search_channels", query="")
        assert set(detailed["channels"][0]) > {"topic", "purpose", "is_archived"}
        concise = await call(
            server, "slack_search_channels", query="", response_format="concise"
        )
        assert set(concise["channels"][0]) == {"id", "name", "num_members"}
        ids = await call(
            server, "slack_search_channels", query="", response_format="ids_only"
        )
        assert ids["channels"] == [C_CLOSE, C_DM]

    async def test_messages_concise_keeps_what_a_reader_skims(
        self, server: MCPServer
    ) -> None:
        detailed = await call(server, "slack_read_channel", channel_id=C_CLOSE)
        assert {"reply_count", "reactions"} < set(detailed["messages"][1])
        concise = await call(
            server,
            "slack_read_channel",
            channel_id=C_CLOSE,
            response_format="concise",
        )
        assert set(concise["messages"][1]) == {"user", "text", "ts", "thread_ts"}
        ids = await call(
            server,
            "slack_read_channel",
            channel_id=C_CLOSE,
            response_format="ids_only",
        )
        assert ids["messages"] == [TS_REPLY, TS_PARENT]

    async def test_search_and_thread_take_the_same_enum(
        self, server: MCPServer
    ) -> None:
        search = await call(
            server, "slack_search_public", query="Kestrel", response_format="ids_only"
        )
        assert search["messages"]["matches"] == [TS_REPLY, TS_PARENT]
        thread = await call(
            server,
            "slack_read_thread",
            channel_id=C_CLOSE,
            message_ts=TS_PARENT,
            response_format="concise",
        )
        assert [set(m) for m in thread["messages"]] == [
            {"user", "text", "ts", "thread_ts"},
            {"user", "text", "ts", "thread_ts"},
        ]

    async def test_users_and_members_share_the_shape(self, server: MCPServer) -> None:
        users = await call(
            server, "slack_search_users", query="", response_format="concise"
        )
        assert set(users["members"][0]) == {"id", "name", "real_name"}
        members = await call(
            server,
            "slack_list_channel_members",
            channel_id=C_CLOSE,
            response_format="ids_only",
        )
        assert members["members"] == [U_ANA, U_BEN]


class TestUserProfile:
    async def test_user_id_defaults_to_the_seat(self, server: MCPServer) -> None:
        mine = await call(server, "slack_read_user_profile")
        assert mine["profile"]["email"] == "ana@calder.example"
        theirs = await call(server, "slack_read_user_profile", user_id=U_CLEO)
        assert theirs["profile"]["real_name"] == "Cleo Vance"

    async def test_include_locale_adds_the_workspace_locale(
        self, server: MCPServer
    ) -> None:
        plain = await call(server, "slack_read_user_profile", user_id=U_BEN)
        assert "locale" not in plain["profile"]
        located = await call(
            server, "slack_read_user_profile", user_id=U_BEN, include_locale=True
        )
        assert located["profile"]["locale"] == "en-US"

    async def test_unseated_default_says_what_is_missing(
        self, server: MCPServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WORKBENCH_SEAT")
        with pytest.raises(Exception, match="WORKBENCH_SEAT"):
            await server.call_tool("slack_read_user_profile", {})


class TestSearchFilters:
    async def test_date_bounds_narrow_the_match_set(self, server: MCPServer) -> None:
        everything = await call(server, "slack_search_public_and_private", query="")
        assert everything["messages"]["total"] == 3
        after = await call(
            server, "slack_search_public_and_private", query="", after="2026-01-05"
        )
        assert after["messages"]["total"] == 0, "every message is on the epoch day"
        before = await call(
            server, "slack_search_public_and_private", query="", before="2026-01-06"
        )
        assert before["messages"]["total"] == 3

    async def test_content_types_without_messages_matches_nothing(
        self, server: MCPServer
    ) -> None:
        files = await call(
            server, "slack_search_public", query="Kestrel", content_types=["files"]
        )
        assert files["messages"]["total"] == 0
        messages = await call(
            server, "slack_search_public", query="Kestrel", content_types=["messages"]
        )
        assert messages["messages"]["total"] == 2

    async def test_context_channel_ranks_first_under_score(
        self, server: MCPServer
    ) -> None:
        plain = await call(server, "slack_search_public_and_private", query="Kestrel")
        assert [m["ts"] for m in plain["messages"]["matches"]] == [
            TS_DM,
            TS_REPLY,
            TS_PARENT,
        ]
        scoped = await call(
            server,
            "slack_search_public_and_private",
            query="Kestrel",
            context_channel_id=C_CLOSE,
        )
        assert [m["channel"]["id"] for m in scoped["messages"]["matches"]] == [
            C_CLOSE,
            C_CLOSE,
            C_DM,
        ]

    async def test_sort_dir_flips_the_order(self, server: MCPServer) -> None:
        ascending = await call(
            server, "slack_search_public", query="Kestrel", sort_dir="asc"
        )
        assert [m["ts"] for m in ascending["messages"]["matches"]] == [
            TS_PARENT,
            TS_REPLY,
        ]

    async def test_include_context_carries_the_neighbours(
        self, server: MCPServer
    ) -> None:
        bare = await call(server, "slack_search_public", query="tie-out")
        assert "previous" not in bare["messages"]["matches"][0]
        with_context = await call(
            server,
            "slack_search_public",
            query="tie-out",
            include_context=True,
            max_context_length=8,
        )
        match = with_context["messages"]["matches"][0]
        assert match["previous"]["ts"] == TS_PARENT
        assert match["previous"]["text"] == "Kestrel "
        assert "next" not in match

    async def test_channel_types_filter_the_listing(self, server: MCPServer) -> None:
        channels = await call(
            server,
            "slack_search_channels",
            query="",
            channel_types=["public_channel"],
            response_format="ids_only",
        )
        assert channels["channels"] == [C_CLOSE]
        dms = await call(
            server,
            "slack_search_channels",
            query="",
            channel_types=["im"],
            response_format="ids_only",
        )
        assert dms["channels"] == [C_DM]


class TestEmojisAndFiles:
    async def test_search_emojis_reports_what_the_workspace_uses(
        self, server: MCPServer
    ) -> None:
        everything = await call(server, "slack_search_emojis", query="")
        assert everything["emojis"] == [{"name": "thumbsup", "count": 1}]
        await call(
            server,
            "slack_add_reaction",
            channel_id=C_CLOSE,
            message_ts=TS_REPLY,
            emoji="eyes",
        )
        both = await call(server, "slack_search_emojis", query="eye")
        assert both["emojis"] == [{"name": "eyes", "count": 1}]

    async def test_read_file_serves_a_canvas(self, server: MCPServer) -> None:
        canvas = await call(
            server, "slack_create_canvas", title="Close checklist", content="Tie out."
        )
        served = await call(server, "slack_read_file", file_id=canvas["canvas"]["id"])
        assert served["file"]["filetype"] == "canvas"
        assert served["file"]["content"] == "Tie out."

    async def test_unknown_file_is_rejected(self, server: MCPServer) -> None:
        with pytest.raises(Exception, match="F99999999"):
            await server.call_tool("slack_read_file", {"file_id": "F99999999"})


class TestSendMessage:
    async def test_a_post_reads_back_in_the_channel(
        self, server: MCPServer, db_path: Path
    ) -> None:
        posted = await call(
            server, "slack_send_message", channel_id=C_CLOSE, message="Tie-out is done."
        )
        assert posted["channel"] == C_CLOSE
        history = await call(server, "slack_read_channel", channel_id=C_CLOSE)
        newest = history["messages"][0]
        assert newest["ts"] == posted["ts"]
        assert newest["text"] == "Tie-out is done."
        assert newest["user"] == U_ANA

    async def test_the_world_record_stays_the_world_record(
        self, server: MCPServer, db_path: Path
    ) -> None:
        await call(server, "slack_send_message", channel_id=C_CLOSE, message="Mine.")
        assert _rows(db_path, "SELECT COUNT(*) FROM messages") == [(3,)]
        assert _rows(db_path, "SELECT body, sender FROM sent_messages") == [
            ("Mine.", "per-ana")
        ]

    async def test_a_thread_reply_joins_the_thread(self, server: MCPServer) -> None:
        posted = await call(
            server,
            "slack_send_message",
            channel_id=C_CLOSE,
            message="Numbers agree.",
            thread_ts=TS_REPLY,
            reply_broadcast=True,
        )
        thread = await call(
            server, "slack_read_thread", channel_id=C_CLOSE, message_ts=TS_PARENT
        )
        assert [m["ts"] for m in thread["messages"]] == [
            TS_PARENT,
            TS_REPLY,
            posted["ts"],
        ]
        assert thread["messages"][-1]["thread_ts"] == TS_PARENT

    async def test_posts_are_searchable_and_ordered_by_sending(
        self, server: MCPServer
    ) -> None:
        first = await call(
            server, "slack_send_message", channel_id=C_CLOSE, message="Kestrel one."
        )
        second = await call(
            server, "slack_send_message", channel_id=C_CLOSE, message="Kestrel two."
        )
        found = await call(
            server, "slack_search_public", query="Kestrel", response_format="ids_only"
        )
        assert found["messages"]["matches"][:2] == [second["ts"], first["ts"]]

    async def test_posting_needs_a_seat(
        self, server: MCPServer, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("WORKBENCH_SEAT")
        with pytest.raises(Exception, match="WORKBENCH_SEAT"):
            await server.call_tool(
                "slack_send_message", {"channel_id": C_CLOSE, "message": "x"}
            )

    async def test_unknown_channel_and_thread_are_rejected(
        self, server: MCPServer
    ) -> None:
        with pytest.raises(Exception, match="C99999999"):
            await server.call_tool(
                "slack_send_message", {"channel_id": "C99999999", "message": "x"}
            )
        with pytest.raises(Exception, match="404.000000"):
            await server.call_tool(
                "slack_send_message",
                {"channel_id": C_CLOSE, "message": "x", "thread_ts": "404.000000"},
            )


class TestDrafts:
    async def test_a_draft_waits_until_it_is_sent(
        self, server: MCPServer, db_path: Path
    ) -> None:
        draft = await call(
            server,
            "slack_send_message_draft",
            channel_id=C_CLOSE,
            message="Proposed wording.",
        )
        assert draft["draft_id"] == "D00000001"
        history = await call(server, "slack_read_channel", channel_id=C_CLOSE)
        assert all(m["text"] != "Proposed wording." for m in history["messages"])
        assert _rows(db_path, "SELECT body, sent FROM message_drafts") == [
            ("Proposed wording.", 0)
        ]

    async def test_sending_by_draft_id_posts_the_draft(
        self, server: MCPServer, db_path: Path
    ) -> None:
        draft = await call(
            server,
            "slack_send_message_draft",
            channel_id=C_CLOSE,
            message="Proposed wording.",
            thread_ts=TS_PARENT,
        )
        posted = await call(
            server,
            "slack_send_message",
            channel_id=C_CLOSE,
            message="",
            draft_id=draft["draft_id"],
        )
        assert posted["message"]["text"] == "Proposed wording."
        thread = await call(
            server, "slack_read_thread", channel_id=C_CLOSE, message_ts=TS_PARENT
        )
        assert thread["messages"][-1]["ts"] == posted["ts"]
        assert _rows(db_path, "SELECT sent FROM message_drafts") == [(1,)]

    async def test_a_draft_cannot_be_sent_twice(self, server: MCPServer) -> None:
        draft = await call(
            server, "slack_send_message_draft", channel_id=C_CLOSE, message="Once."
        )
        await call(
            server,
            "slack_send_message",
            channel_id=C_CLOSE,
            message="",
            draft_id=draft["draft_id"],
        )
        with pytest.raises(Exception, match=draft["draft_id"]):
            await server.call_tool(
                "slack_send_message",
                {
                    "channel_id": C_CLOSE,
                    "message": "",
                    "draft_id": draft["draft_id"],
                },
            )


class TestScheduleMessage:
    async def test_a_scheduled_message_is_queued_not_posted(
        self, server: MCPServer, db_path: Path
    ) -> None:
        scheduled = await call(
            server,
            "slack_schedule_message",
            channel_id=C_CLOSE,
            message="Monday recap.",
            post_at=1800000000,
        )
        assert scheduled["scheduled_message_id"] == "Q00000001"
        history = await call(server, "slack_read_channel", channel_id=C_CLOSE)
        assert all(m["text"] != "Monday recap." for m in history["messages"])
        assert _rows(
            db_path, "SELECT body, post_at, sender FROM scheduled_messages"
        ) == [("Monday recap.", 1800000000, "per-ana")]


class TestCreateConversation:
    async def test_a_new_channel_lists_and_accepts_posts(
        self, server: MCPServer
    ) -> None:
        created = await call(
            server,
            "slack_create_conversation",
            channel_name="kestrel-close",
            user_ids=[U_BEN],
        )
        assert created["channel"]["id"] == C_NEW
        assert created["channel"]["name"] == "kestrel-close"
        assert created["channel"]["num_members"] == 2
        listed = await call(
            server, "slack_search_channels", query="", response_format="ids_only"
        )
        assert listed["channels"] == [C_CLOSE, C_DM, C_NEW], (
            "opening a channel never renumbers the workspace"
        )
        posted = await call(
            server, "slack_send_message", channel_id=C_NEW, message="Kickoff."
        )
        history = await call(server, "slack_read_channel", channel_id=C_NEW)
        assert [m["ts"] for m in history["messages"]] == [posted["ts"]]
        members = await call(
            server,
            "slack_list_channel_members",
            channel_id=C_NEW,
            response_format="ids_only",
        )
        assert members["members"] == [U_ANA, U_BEN]

    async def test_a_private_channel_reports_itself_private(
        self, server: MCPServer
    ) -> None:
        created = await call(
            server,
            "slack_create_conversation",
            channel_name="partners-only",
            is_private=True,
        )
        assert created["channel"]["is_private"] is True
        private = await call(
            server,
            "slack_search_channels",
            query="",
            channel_types=["private_channel"],
            response_format="ids_only",
        )
        assert private["channels"] == [created["channel"]["id"]]

    async def test_a_dm_needs_people_and_a_channel_needs_a_name(
        self, server: MCPServer
    ) -> None:
        dm = await call(server, "slack_create_conversation", user_ids=[U_CLEO])
        assert dm["channel"]["is_im"] is True and dm["channel"]["name"] is None
        with pytest.raises(Exception, match="channel_name"):
            await server.call_tool("slack_create_conversation", {})

    async def test_a_taken_name_is_refused(self, server: MCPServer) -> None:
        await call(server, "slack_create_conversation", channel_name="kestrel-close")
        with pytest.raises(Exception, match="kestrel-close"):
            await server.call_tool(
                "slack_create_conversation", {"channel_name": "kestrel-close"}
            )
        with pytest.raises(Exception, match="close-2026"):
            await server.call_tool(
                "slack_create_conversation", {"channel_name": "close-2026"}
            )


class TestAddReaction:
    async def test_a_reaction_reads_back_on_the_message(
        self, server: MCPServer
    ) -> None:
        await call(
            server,
            "slack_add_reaction",
            channel_id=C_CLOSE,
            message_ts=TS_PARENT,
            emoji=":white_check_mark:",
        )
        payload = await call(
            server, "slack_get_reactions", channel_id=C_CLOSE, message_ts=TS_PARENT
        )
        assert payload["message"]["reactions"] == [
            {"name": "thumbsup", "users": [U_BEN], "count": 1},
            {"name": "white_check_mark", "users": [U_ANA], "count": 1},
        ]

    async def test_reacting_twice_is_a_no_op(
        self, server: MCPServer, db_path: Path
    ) -> None:
        for _ in range(3):
            await call(
                server,
                "slack_add_reaction",
                channel_id=C_CLOSE,
                message_ts=TS_PARENT,
                emoji="eyes",
            )
        assert _rows(db_path, "SELECT COUNT(*) FROM added_reactions") == [(1,)]
        payload = await call(
            server, "slack_get_reactions", channel_id=C_CLOSE, message_ts=TS_PARENT
        )
        assert [r["count"] for r in payload["message"]["reactions"]] == [1, 1]

    async def test_an_agent_post_can_be_reacted_to(self, server: MCPServer) -> None:
        posted = await call(
            server, "slack_send_message", channel_id=C_CLOSE, message="Filed."
        )
        await call(
            server,
            "slack_add_reaction",
            channel_id=C_CLOSE,
            message_ts=posted["ts"],
            emoji="tada",
        )
        payload = await call(
            server, "slack_get_reactions", channel_id=C_CLOSE, message_ts=posted["ts"]
        )
        assert payload["message"]["reactions"] == [
            {"name": "tada", "users": [U_ANA], "count": 1}
        ]

    async def test_an_unknown_message_is_rejected(self, server: MCPServer) -> None:
        with pytest.raises(Exception, match="404.000000"):
            await server.call_tool(
                "slack_add_reaction",
                {
                    "channel_id": C_CLOSE,
                    "message_ts": "404.000000",
                    "emoji": "eyes",
                },
            )


class TestCanvas:
    async def test_create_and_read_back_by_section(self, server: MCPServer) -> None:
        canvas = await call(
            server,
            "slack_create_canvas",
            title="Close checklist",
            content="Tie out cash.\n\nRoll forward fixed assets.",
        )
        assert canvas["canvas"]["id"] == "F00000001"
        read = await call(server, "slack_read_canvas", canvas_id="F00000001")
        assert read["canvas"]["title"] == "Close checklist"
        assert read["canvas"]["sections"] == [
            {"id": "S00000001", "content": "Tie out cash."},
            {"id": "S00000002", "content": "Roll forward fixed assets."},
        ]

    async def test_append_prepend_and_replace(self, server: MCPServer) -> None:
        canvas = await call(
            server, "slack_create_canvas", title="Notes", content="Middle."
        )
        canvas_id = canvas["canvas"]["id"]
        await call(server, "slack_update_canvas", canvas_id=canvas_id, content="Last.")
        await call(
            server,
            "slack_update_canvas",
            canvas_id=canvas_id,
            content="First.",
            action="prepend",
        )
        read = await call(server, "slack_read_canvas", canvas_id=canvas_id)
        assert [s["content"] for s in read["canvas"]["sections"]] == [
            "First.",
            "Middle.",
            "Last.",
        ]
        replaced = await call(
            server,
            "slack_update_canvas",
            canvas_id=canvas_id,
            content="Only.",
            action="replace",
        )
        assert [s["content"] for s in replaced["canvas"]["sections"]] == ["Only."]

    async def test_a_section_id_scopes_the_edit(self, server: MCPServer) -> None:
        canvas = await call(
            server, "slack_create_canvas", title="Notes", content="One.\n\nTwo."
        )
        canvas_id = canvas["canvas"]["id"]
        await call(
            server,
            "slack_update_canvas",
            canvas_id=canvas_id,
            content="Two, revised.",
            action="replace",
            section_id="S00000002",
        )
        await call(
            server,
            "slack_update_canvas",
            canvas_id=canvas_id,
            content="One and a half.",
            action="append",
            section_id="S00000001",
        )
        read = await call(server, "slack_read_canvas", canvas_id=canvas_id)
        assert [s["content"] for s in read["canvas"]["sections"]] == [
            "One.",
            "One and a half.",
            "Two, revised.",
        ]

    async def test_unknown_canvas_and_section_are_rejected(
        self, server: MCPServer
    ) -> None:
        with pytest.raises(Exception, match="F99999999"):
            await server.call_tool(
                "slack_update_canvas", {"canvas_id": "F99999999", "content": "x"}
            )
        canvas = await call(
            server, "slack_create_canvas", title="Notes", content="One."
        )
        with pytest.raises(Exception, match="S00000009"):
            await server.call_tool(
                "slack_update_canvas",
                {
                    "canvas_id": canvas["canvas"]["id"],
                    "content": "x",
                    "section_id": "S00000009",
                },
            )


async def test_writes_are_invisible_to_a_colleague(
    server: MCPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A seat writes as itself: what Ana posts is Ana's, and the dm she opens
    with an outside contact is not Ben's to read."""
    await call(
        server, "slack_send_message", channel_id=C_DM, message="Sending the K-1."
    )
    opened = await call(server, "slack_create_conversation", user_ids=[U_CLEO])
    monkeypatch.setenv("WORKBENCH_SEAT", "per-ben")
    listed = await call(
        server, "slack_search_channels", query="", response_format="ids_only"
    )
    assert listed["channels"] == [C_CLOSE]
    with pytest.raises(Exception, match=opened["channel"]["id"]):
        await server.call_tool(
            "slack_read_channel", {"channel_id": opened["channel"]["id"]}
        )

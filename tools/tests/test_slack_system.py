"""The slack system: Slack's official tool names over projected chat events."""

import json
import re
import sqlite3
from pathlib import Path

import pytest
from mcp.server import MCPServer
from projection_fixtures import coherent_events

from workbench.core.events import Event, EventPayload
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
    ChatReactionAddedPayload,
)
from workbench.tools.framework import build_server, project_system
from workbench.tools.slack import SYSTEM

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")

LEGAL, DEALS, DM = "cnv-000001", "cnv-000002", "cnv-000003"
C_LEGAL, C_DEALS, C_DM = "C00000001", "C00000002", "C00000003"
U_DANIEL, U_JESS, U_MEREDITH, U_TOM = (
    "U00000001",
    "U00000002",
    "U00000003",
    "U00000004",
)


def slack_events() -> list[Event]:
    """The shared fixture plus reactions, a topical channel, and a dm."""
    events = coherent_events()
    extra: list[tuple[int, str, EventPayload]] = [
        (
            800,
            "gm",
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=DEALS,
                conversation_type="channel",
                name="#deal-desk",
                members=("per-meredith-chao", "per-daniel-reyes"),
                topic="Live deal coordination",
                purpose="Coordinate active deal work",
            ),
        ),
        (
            800,
            "gm",
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id=DM,
                conversation_type="dm",
                name=None,
                members=("per-jess-alvarez", "per-tom-okafor"),
            ),
        ),
        (
            900,
            "tom",
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000002",
                conversation_id=LEGAL,
                reply_to="chm-000001",
                sender="per-tom-okafor",
                body="Ack, pulling the file history now.",
            ),
        ),
        (
            900,
            "meredith",
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000003",
                conversation_id=DEALS,
                reply_to=None,
                sender="per-meredith-chao",
                body="Acme kickoff notes for the deal desk.",
            ),
        ),
        (
            1000,
            "jess",
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000004",
                conversation_id=DM,
                reply_to=None,
                sender="per-jess-alvarez",
                body="Acme NDA status?",
            ),
        ),
        (
            90000,
            "daniel",
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000005",
                conversation_id=DEALS,
                reply_to=None,
                sender="per-daniel-reyes",
                body="Acme redlines went out.",
            ),
        ),
        (
            90001,
            "tom",
            ChatReactionAddedPayload(
                kind="chat.reaction.added",
                conversation_id=LEGAL,
                chat_message_id="chm-000001",
                person_id="per-tom-okafor",
                emoji="thumbsup",
            ),
        ),
        (
            90002,
            "meredith",
            ChatReactionAddedPayload(
                kind="chat.reaction.added",
                conversation_id=LEGAL,
                chat_message_id="chm-000001",
                person_id="per-meredith-chao",
                emoji="thumbsup",
            ),
        ),
        (
            90003,
            "jess",
            ChatReactionAddedPayload(
                kind="chat.reaction.added",
                conversation_id=LEGAL,
                chat_message_id="chm-000001",
                person_id="per-jess-alvarez",
                emoji="eyes",
            ),
        ),
    ]
    events += [
        Event(
            seq=len(events) + offset,
            time=time,
            tag=payload.kind,
            source=source,
            payload=payload,
        )
        for offset, (time, source, payload) in enumerate(extra)
    ]
    return events


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "slack.db"
    project_system(SYSTEM, slack_events(), path)
    return path


@pytest.fixture
def server(db_path: Path) -> MCPServer:
    built = MCPServer(
        name="workbench-slack", instructions="The organization's slack system."
    )
    SYSTEM.register(built, db_path)
    return built


async def call(server: MCPServer, name: str, arguments: dict | None = None) -> dict:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def test_projection_folds_topic_purpose_members_and_reactions(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        conversations = connection.execute(
            "SELECT conversation_id, name, kind, topic, purpose FROM conversations "
            "ORDER BY conversation_id"
        ).fetchall()
        dm_members = connection.execute(
            "SELECT person_id FROM members WHERE conversation_id=?", (DM,)
        ).fetchall()
        reactions = connection.execute(
            "SELECT conversation_id, chat_message_id, person_id, emoji FROM reactions"
        ).fetchall()
    assert conversations == [
        (LEGAL, "#legal", "channel", "", ""),
        (
            DEALS,
            "#deal-desk",
            "channel",
            "Live deal coordination",
            "Coordinate active deal work",
        ),
        (DM, None, "dm", "", ""),
    ]
    assert sorted(m[0] for m in dm_members) == ["per-jess-alvarez", "per-tom-okafor"]
    assert (LEGAL, "chm-000001", "per-tom-okafor", "thumbsup") in reactions
    assert (LEGAL, "chm-000001", "per-jess-alvarez", "eyes") in reactions


def test_ts_is_derived_unique_and_projection_ordered(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        ts_by_id = dict(
            connection.execute("SELECT chat_message_id, ts FROM messages").fetchall()
        )
    assert ts_by_id == {
        "chm-000001": "500.000000",
        "chm-000002": "900.000001",
        "chm-000003": "900.000002",
        "chm-000004": "1000.000003",
        "chm-000005": "90000.000004",
    }
    assert len(set(ts_by_id.values())) == len(ts_by_id)
    assert all(re.fullmatch(r"\d+\.\d{6}", ts) for ts in ts_by_id.values())


async def test_search_channels_lists_all_in_slack_shape(server: MCPServer) -> None:
    payload = await call(server, "slack_search_channels", {"query": ""})
    assert set(payload) == {"ok", "channels", "response_metadata"}
    assert payload["ok"] is True
    assert payload["response_metadata"] == {"next_cursor": ""}
    channels = payload["channels"]
    assert [c["id"] for c in channels] == [C_LEGAL, C_DEALS, C_DM]
    legal = channels[0]
    assert set(legal) == {
        "id",
        "name",
        "is_channel",
        "is_im",
        "is_private",
        "is_archived",
        "topic",
        "purpose",
        "num_members",
    }
    assert legal["name"] == "legal"
    assert legal["is_channel"] is True and legal["is_im"] is False
    assert legal["is_private"] is False and legal["is_archived"] is False
    assert legal["topic"] == {"value": "", "creator": "", "last_set": 0}
    assert legal["num_members"] == 3
    deals = channels[1]
    assert deals["topic"] == {
        "value": "Live deal coordination",
        "creator": "",
        "last_set": 0,
    }
    dm = channels[2]
    assert dm["is_im"] is True and dm["name"] is None and dm["num_members"] == 2


async def test_search_channels_matches_and_pages(server: MCPServer) -> None:
    by_name = await call(server, "slack_search_channels", {"query": "deal-desk"})
    assert [c["id"] for c in by_name["channels"]] == [C_DEALS]
    by_topic = await call(server, "slack_search_channels", {"query": "coordination"})
    assert [c["id"] for c in by_topic["channels"]] == [C_DEALS]
    by_purpose = await call(
        server, "slack_search_channels", {"query": "active deal work"}
    )
    assert [c["id"] for c in by_purpose["channels"]] == [C_DEALS]
    first = await call(server, "slack_search_channels", {"query": "", "limit": 2})
    assert [c["id"] for c in first["channels"]] == [C_LEGAL, C_DEALS]
    assert first["response_metadata"]["next_cursor"] == "2"
    rest = await call(
        server, "slack_search_channels", {"query": "", "limit": 2, "cursor": "2"}
    )
    assert [c["id"] for c in rest["channels"]] == [C_DM]
    assert rest["response_metadata"]["next_cursor"] == ""


async def test_read_channel_newest_first_threads_reactions(server: MCPServer) -> None:
    payload = await call(server, "slack_read_channel", {"channel_id": C_LEGAL})
    assert set(payload) == {"ok", "messages", "has_more"}
    assert payload["ok"] is True and payload["has_more"] is False
    reply, parent = payload["messages"]
    assert [m["ts"] for m in (reply, parent)] == ["900.000001", "500.000000"]
    assert set(parent) == {
        "type",
        "user",
        "text",
        "ts",
        "thread_ts",
        "reply_count",
        "reactions",
    }
    assert parent["type"] == "message"
    assert parent["user"] == U_DANIEL
    assert parent["text"] == "Taking the NDA review."
    assert parent["thread_ts"] == "500.000000"
    assert parent["reply_count"] == 1
    assert parent["reactions"] == [
        {"name": "thumbsup", "users": [U_TOM, U_MEREDITH], "count": 2},
        {"name": "eyes", "users": [U_JESS], "count": 1},
    ]
    assert set(reply) == {"type", "user", "text", "ts", "thread_ts"}
    assert reply["thread_ts"] == "500.000000"


async def test_read_channel_accepts_internal_id_window_limit(
    server: MCPServer,
) -> None:
    internal = await call(server, "slack_read_channel", {"channel_id": LEGAL})
    assert [m["ts"] for m in internal["messages"]] == ["900.000001", "500.000000"]
    limited = await call(
        server, "slack_read_channel", {"channel_id": C_LEGAL, "limit": 1}
    )
    assert [m["ts"] for m in limited["messages"]] == ["900.000001"]
    assert limited["has_more"] is True
    older = await call(
        server, "slack_read_channel", {"channel_id": C_LEGAL, "latest": "600"}
    )
    assert [m["ts"] for m in older["messages"]] == ["500.000000"]
    newer = await call(
        server, "slack_read_channel", {"channel_id": C_LEGAL, "oldest": "600"}
    )
    assert [m["ts"] for m in newer["messages"]] == ["900.000001"]


async def test_read_channel_caps_the_page_size(tmp_path: Path) -> None:
    """A huge limit must not dump an entire history in one call."""

    events = slack_events()
    top = max(event.seq for event in events)
    for offset in range(120):
        events.append(
            Event(
                seq=top + 1 + offset,
                time=100_000 + offset,
                tag="chat.message",
                source="meredith",
                payload=ChatMessagePayload(
                    kind="chat.message",
                    chat_message_id=f"chm-9{offset:05d}",
                    conversation_id=DEALS,
                    reply_to=None,
                    sender="per-meredith-chao",
                    body=f"filler update {offset}",
                ),
            )
        )
    db = tmp_path / "slack-cap.db"
    project_system(SYSTEM, events, db)
    big = build_server(SYSTEM, db)
    dump = await call(big, "slack_read_channel", {"channel_id": DEALS, "limit": 5000})
    assert len(dump["messages"]) == 100
    assert dump["has_more"] is True
    floor = await call(big, "slack_read_channel", {"channel_id": DEALS, "limit": -5})
    assert len(floor["messages"]) == 1


async def test_read_thread_parent_first(server: MCPServer) -> None:
    payload = await call(
        server,
        "slack_read_thread",
        {"channel_id": C_LEGAL, "message_ts": "500.000000"},
    )
    assert set(payload) == {"ok", "messages"}
    assert [m["ts"] for m in payload["messages"]] == ["500.000000", "900.000001"]
    from_reply = await call(
        server,
        "slack_read_thread",
        {"channel_id": C_LEGAL, "message_ts": "900.000001"},
    )
    assert [m["ts"] for m in from_reply["messages"]] == ["500.000000", "900.000001"]


async def test_search_public_terms_phrases_and_channel_scope(
    server: MCPServer,
) -> None:
    acme = await call(server, "slack_search_public", {"query": "Acme"})
    assert set(acme) == {"ok", "messages", "response_metadata"}
    assert set(acme["messages"]) == {"matches", "total"}
    assert acme["messages"]["total"] == 2, "the dm Acme message must not surface"
    matches = acme["messages"]["matches"]
    assert [m["ts"] for m in matches] == ["90000.000004", "900.000002"]
    assert matches[0]["channel"] == {"id": C_DEALS, "name": "deal-desk"}
    both_terms = await call(server, "slack_search_public", {"query": "Acme kickoff"})
    assert [m["ts"] for m in both_terms["messages"]["matches"]] == ["900.000002"]
    phrase = await call(server, "slack_search_public", {"query": '"kickoff notes"'})
    assert phrase["messages"]["total"] == 1
    scrambled = await call(server, "slack_search_public", {"query": '"notes kickoff"'})
    assert scrambled["messages"]["total"] == 0
    scoped = await call(server, "slack_search_public", {"query": "Acme in:deal-desk"})
    assert scoped["messages"]["total"] == 2
    elsewhere = await call(server, "slack_search_public", {"query": "Acme in:legal"})
    assert elsewhere["messages"]["total"] == 0


async def test_search_public_caps_the_page_size(server: MCPServer) -> None:
    """A huge limit must not dump every match in one call."""
    dump = await call(server, "slack_search_public", {"query": "Acme", "limit": 5000})
    assert len(dump["messages"]["matches"]) <= 20
    assert dump["messages"]["total"] == 2
    paged = await call(
        server, "slack_search_public", {"query": "Acme", "limit": 1, "cursor": "1"}
    )
    assert [m["ts"] for m in paged["messages"]["matches"]] == ["900.000002"]


async def test_search_public_returns_its_pagination_cursor(server: MCPServer) -> None:
    """The docstring promises paging; the cursor must reach the caller."""
    first = await call(server, "slack_search_public", {"query": "Acme", "limit": 1})
    assert first["response_metadata"] == {"next_cursor": "1"}
    assert [m["ts"] for m in first["messages"]["matches"]] == ["90000.000004"]
    rest = await call(
        server,
        "slack_search_public",
        {"query": "Acme", "limit": 1, "cursor": first["response_metadata"]["next_cursor"]},
    )
    assert [m["ts"] for m in rest["messages"]["matches"]] == ["900.000002"]
    assert rest["response_metadata"] == {"next_cursor": ""}


async def test_search_public_and_private_covers_dms(server: MCPServer) -> None:
    """Slack's second search tool reaches dms; the public one never does."""
    public = await call(server, "slack_search_public", {"query": "Acme"})
    assert public["messages"]["total"] == 2

    both = await call(server, "slack_search_public_and_private", {"query": "Acme"})
    assert set(both) == {"ok", "messages", "response_metadata"}
    assert both["messages"]["total"] == 3
    matches = both["messages"]["matches"]
    assert [m["ts"] for m in matches] == ["90000.000004", "1000.000003", "900.000002"]
    dm_hit = matches[1]
    assert dm_hit["text"] == "Acme NDA status?"
    assert dm_hit["channel"] == {"id": C_DM, "name": None}


async def test_search_public_and_private_shares_the_query_grammar(
    server: MCPServer,
) -> None:
    phrase = await call(
        server, "slack_search_public_and_private", {"query": '"NDA status"'}
    )
    assert [m["ts"] for m in phrase["messages"]["matches"]] == ["1000.000003"]
    by_sender = await call(
        server, "slack_search_public_and_private", {"query": "from:Jess Acme"}
    )
    assert [m["user"] for m in by_sender["messages"]["matches"]] == [U_JESS]
    early = await call(
        server, "slack_search_public_and_private", {"query": "Acme before:2026-03-13"}
    )
    assert [m["ts"] for m in early["messages"]["matches"]] == [
        "1000.000003",
        "900.000002",
    ]
    paged = await call(
        server, "slack_search_public_and_private", {"query": "Acme", "limit": 2}
    )
    assert paged["response_metadata"] == {"next_cursor": "2"}
    assert paged["messages"]["total"] == 3


async def test_seat_scopes_conversations_to_membership(
    server: MCPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With a seat, slack is that person's Slack: no channels they never
    joined, and none of anyone else's dms."""
    monkeypatch.setenv("WORKBENCH_SEAT", "per-tom-okafor")

    channels = await call(server, "slack_search_channels", {"query": ""})
    assert [c["id"] for c in channels["channels"]] == [C_LEGAL, C_DM]

    # Display ids stay derived from the whole workspace, not from the slice.
    assert (await call(server, "slack_read_channel", {"channel_id": C_LEGAL}))["ok"]
    with pytest.raises(Exception, match=C_DEALS):
        await server.call_tool("slack_read_channel", {"channel_id": C_DEALS})

    both = await call(server, "slack_search_public_and_private", {"query": "Acme"})
    assert both["messages"]["total"] == 1, "only tom's own dm is searchable"
    assert both["messages"]["matches"][0]["ts"] == "1000.000003"
    public = await call(server, "slack_search_public", {"query": "Acme"})
    assert public["messages"]["total"] == 0, "tom is not in #deal-desk"

    monkeypatch.setenv("WORKBENCH_SEAT", "per-meredith-chao")
    hers = await call(server, "slack_search_public_and_private", {"query": "Acme"})
    assert hers["messages"]["total"] == 2, "meredith never sees the jess/tom dm"
    assert (await call(server, "slack_search_channels", {"query": ""}))["channels"] and [
        c["id"]
        for c in (await call(server, "slack_search_channels", {"query": ""}))["channels"]
    ] == [C_LEGAL, C_DEALS]
    with pytest.raises(Exception, match=C_DM):
        await server.call_tool("slack_list_channel_members", {"channel_id": C_DM})


async def test_search_public_from_and_date_filters(server: MCPServer) -> None:
    by_uid = await call(
        server, "slack_search_public", {"query": f"from:{U_DANIEL} Acme"}
    )
    assert [m["user"] for m in by_uid["messages"]["matches"]] == [U_DANIEL]
    by_name = await call(server, "slack_search_public", {"query": "from:Meredith Acme"})
    assert [m["ts"] for m in by_name["messages"]["matches"]] == ["900.000002"]
    early = await call(
        server, "slack_search_public", {"query": "Acme before:2026-03-13"}
    )
    assert [m["ts"] for m in early["messages"]["matches"]] == ["900.000002"]
    late = await call(server, "slack_search_public", {"query": "Acme after:2026-03-12"})
    assert [m["ts"] for m in late["messages"]["matches"]] == ["90000.000004"]


async def test_search_users_shape_and_matching(server: MCPServer) -> None:
    everyone = await call(server, "slack_search_users", {"query": ""})
    assert set(everyone) == {"ok", "members"}
    assert [u["id"] for u in everyone["members"]] == [
        U_DANIEL,
        U_JESS,
        U_MEREDITH,
        U_TOM,
    ]
    member = everyone["members"][0]
    assert set(member) == {"id", "name", "real_name", "profile", "is_bot", "deleted"}
    assert member["name"] == "daniel"
    assert member["real_name"] == "Daniel Reyes"
    assert member["is_bot"] is False and member["deleted"] is False
    assert set(member["profile"]) == {"real_name", "display_name", "email", "title"}
    by_title = await call(server, "slack_search_users", {"query": "counsel"})
    assert len(by_title["members"]) == 4
    by_email = await call(server, "slack_search_users", {"query": "meredith@"})
    assert [u["id"] for u in by_email["members"]] == [U_MEREDITH]


async def test_read_user_profile_accepts_both_id_forms(server: MCPServer) -> None:
    payload = await call(server, "slack_read_user_profile", {"user_id": U_MEREDITH})
    assert set(payload) == {"ok", "profile"}
    assert payload["profile"] == {
        "real_name": "Meredith Chao",
        "display_name": "Meredith Chao",
        "email": "meredith@example.com",
        "title": "Counsel",
    }
    internal = await call(
        server, "slack_read_user_profile", {"user_id": "per-meredith-chao"}
    )
    assert internal["profile"]["email"] == "meredith@example.com"


async def test_list_channel_members(server: MCPServer) -> None:
    payload = await call(server, "slack_list_channel_members", {"channel_id": C_LEGAL})
    assert payload == {"ok": True, "members": [U_DANIEL, U_MEREDITH, U_TOM]}


async def test_get_reactions(server: MCPServer) -> None:
    payload = await call(
        server,
        "slack_get_reactions",
        {"channel_id": C_LEGAL, "message_ts": "500.000000"},
    )
    assert set(payload) == {"ok", "message"}
    assert payload["message"]["ts"] == "500.000000"
    assert payload["message"]["reactions"] == [
        {"name": "thumbsup", "users": [U_TOM, U_MEREDITH], "count": 2},
        {"name": "eyes", "users": [U_JESS], "count": 1},
    ]
    bare = await call(
        server,
        "slack_get_reactions",
        {"channel_id": C_LEGAL, "message_ts": "900.000001"},
    )
    assert bare["message"]["reactions"] == []


async def test_unknown_ids_raise(server: MCPServer) -> None:
    with pytest.raises(Exception, match="C99999999"):
        await server.call_tool("slack_read_channel", {"channel_id": "C99999999"})
    with pytest.raises(Exception, match="999.000000"):
        await server.call_tool(
            "slack_read_thread", {"channel_id": C_LEGAL, "message_ts": "999.000000"}
        )
    with pytest.raises(Exception, match="U99999999"):
        await server.call_tool("slack_read_user_profile", {"user_id": "U99999999"})
    with pytest.raises(Exception, match="C99999999"):
        await server.call_tool(
            "slack_list_channel_members", {"channel_id": "C99999999"}
        )
    with pytest.raises(Exception, match="404.000000"):
        await server.call_tool(
            "slack_get_reactions", {"channel_id": C_LEGAL, "message_ts": "404.000000"}
        )


async def test_surface_is_slack_named_and_read_only(server: MCPServer) -> None:
    tools = await server.list_tools()
    assert sorted(tool.name for tool in tools) == [
        "slack_get_reactions",
        "slack_list_channel_members",
        "slack_read_channel",
        "slack_read_thread",
        "slack_read_user_profile",
        "slack_search_channels",
        "slack_search_public",
        "slack_search_public_and_private",
        "slack_search_users",
    ]
    for tool in tools:
        assert not any(
            verb in tool.name
            for verb in ("send", "create", "update", "delete", "write", "post")
        ), f"slack exposes a write tool in the read-only phase: {tool.name}"


async def test_leakage_audit_no_offstage_markers(server: MCPServer) -> None:
    arguments = {
        "slack_search_channels": {"query": ""},
        "slack_read_channel": {"channel_id": C_LEGAL},
        "slack_read_thread": {"channel_id": C_LEGAL, "message_ts": "500.000000"},
        "slack_search_public": {"query": "Acme"},
        "slack_search_public_and_private": {"query": "Acme"},
        "slack_search_users": {"query": ""},
        "slack_read_user_profile": {"user_id": U_MEREDITH},
        "slack_list_channel_members": {"channel_id": C_LEGAL},
        "slack_get_reactions": {"channel_id": C_LEGAL, "message_ts": "500.000000"},
    }
    for tool in await server.list_tools():
        result = await server.call_tool(tool.name, arguments[tool.name])
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        for marker in OFFSTAGE_MARKERS:
            assert marker not in text, f"slack.{tool.name} leaked {marker!r}"

"""Read tools over the slack database, shaped like Slack's Web API.

Display ids are derived per call, never stored: channels are ``C{n:08d}``
and users ``U{n:08d}`` where ``n`` is the 1-based position of the internal
id in sorted order over the whole workspace, so the mapping is
deterministic for a given database and independent of who is looking.
Every tool accepts either the Slack-style id or the internal id.

Search comes in Slack's own two flavors: ``slack_search_public`` sees
channels only, and ``slack_search_public_and_private`` also sees the
conversations the caller belongs to, dms included. Both share one query
grammar.

Workspace scoping: the optional ``WORKBENCH_SEAT`` environment variable
names the person_id whose Slack this server presents; it is read at call
time, never at import time. When set, only conversations that person is a
member of exist for these tools — an unjoined channel and someone else's
dm are both unknown ids. When unset the server reads workspace-wide. The
user directory is workspace-wide either way, as it is in Slack.
"""

import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from mcp.server import MCPServer

from workbench.tools.db import connect_readonly
from workbench.tools.framework import (
    PEOPLE_TABLE,
    Person,
    UnknownRefError,
    read_epoch,
    seat,
)
from workbench.tools.slack.tables import (
    CONVERSATIONS,
    MEMBERS,
    MESSAGES,
    REACTIONS,
    ChatMessage,
    Conversation,
    Reaction,
)

_FILTERS = ("in", "from", "before", "after")
_PHRASE = re.compile(r'"([^"]*)"')


@dataclass(frozen=True, slots=True)
class _Directory:
    # Only the conversations the seat may see; ``channel_ids`` still covers
    # the whole workspace so a display id means the same thing for everyone.
    conversations: dict[str, Conversation]
    channel_ids: dict[str, str]
    people: dict[str, Person]
    user_ids: dict[str, str]
    epoch: datetime

    def resolve_channel(self, channel_id: str) -> Conversation:
        internal = _invert(self.channel_ids).get(channel_id, channel_id)
        conversation = self.conversations.get(internal)
        if conversation is None:
            raise UnknownRefError(f"no channel {channel_id}")
        return conversation

    def resolve_person(self, user_id: str) -> Person:
        internal = _invert(self.user_ids).get(user_id, user_id)
        person = self.people.get(internal)
        if person is None:
            raise UnknownRefError(f"no user {user_id}")
        return person


def _invert(mapping: dict[str, str]) -> dict[str, str]:
    return {display: internal for internal, display in mapping.items()}


def _display_ids(internal_ids: Iterable[str], prefix: str) -> dict[str, str]:
    return {
        internal: f"{prefix}{position:08d}"
        for position, internal in enumerate(sorted(internal_ids), start=1)
    }


def _load(connection: sqlite3.Connection) -> _Directory:
    conversations = CONVERSATIONS.select(connection, order_by="conversation_id")
    people = PEOPLE_TABLE.select(connection, order_by="person_id")
    channel_ids = _display_ids((c.conversation_id for c in conversations), "C")
    if (person := seat()) is not None:
        joined = {
            member.conversation_id
            for member in MEMBERS.select(connection, where={"person_id": person})
        }
        conversations = [c for c in conversations if c.conversation_id in joined]
    return _Directory(
        conversations={c.conversation_id: c for c in conversations},
        channel_ids=channel_ids,
        people={p.person_id: p for p in people},
        user_ids=_display_ids((p.person_id for p in people), "U"),
        epoch=read_epoch(connection),
    )


def _channel_name(conversation: Conversation) -> str | None:
    return conversation.name.lstrip("#") if conversation.name else conversation.name


def _ts_key(ts: str) -> tuple[int, int]:
    seconds, microseconds = ts.split(".")
    return (int(seconds), int(microseconds))


def _message_objects(
    messages: Sequence[ChatMessage],
    reactions: Sequence[Reaction],
    directory: _Directory,
) -> dict[str, dict[str, object]]:
    ts_of = {m.chat_message_id: m.ts for m in messages}
    reply_counts = Counter(m.reply_to for m in messages if m.reply_to)
    votes: dict[str, dict[str, list[str]]] = {}
    for reaction in reactions:
        votes.setdefault(reaction.chat_message_id, {}).setdefault(
            reaction.emoji, []
        ).append(directory.user_ids[reaction.person_id])
    objects: dict[str, dict[str, object]] = {}
    for message in messages:
        obj: dict[str, object] = {
            "type": "message",
            "user": directory.user_ids[message.sender],
            "text": message.body,
            "ts": message.ts,
        }
        if message.reply_to is not None:
            obj["thread_ts"] = ts_of[message.reply_to]
        elif message.chat_message_id in reply_counts:
            obj["thread_ts"] = message.ts
            obj["reply_count"] = reply_counts[message.chat_message_id]
        if users_by_emoji := votes.get(message.chat_message_id):
            obj["reactions"] = [
                {"name": emoji, "users": users, "count": len(users)}
                for emoji, users in users_by_emoji.items()
            ]
        objects[message.chat_message_id] = obj
    return objects


def _conversation_messages(
    connection: sqlite3.Connection, conversation: Conversation
) -> tuple[list[ChatMessage], list[Reaction]]:
    messages = MESSAGES.select(
        connection, where={"conversation_id": conversation.conversation_id}
    )
    reactions = REACTIONS.select(
        connection, where={"conversation_id": conversation.conversation_id}
    )
    messages.sort(key=lambda m: _ts_key(m.ts))
    return messages, reactions


def _page[T](items: list[T], limit: int, cursor: str | None) -> tuple[list[T], str]:
    offset = int(cursor) if cursor else 0
    end = offset + limit
    return items[offset:end], str(end) if end < len(items) else ""


def _parse_query(query: str) -> tuple[list[str], dict[str, str]]:
    """Split a search query into AND needles and in:/from:/before:/after:."""
    needles = [phrase for phrase in _PHRASE.findall(query) if phrase]
    filters: dict[str, str] = {}
    for token in _PHRASE.sub(" ", query).split():
        name, _, value = token.partition(":")
        if value and name in _FILTERS:
            filters[name] = value
        else:
            needles.append(token)
    return needles, filters


def _senders_matching(directory: _Directory, value: str) -> set[str]:
    needle = value.lower()
    matched = set()
    for person_id, person in directory.people.items():
        exact = (
            directory.user_ids[person_id].lower(),
            person_id.lower(),
            person.email_address.split("@")[0].lower(),
        )
        if needle in exact or needle in person.name.lower():
            matched.add(person_id)
    return matched


def _event_date(epoch: datetime, seconds: int) -> date:
    return (epoch + timedelta(seconds=seconds)).date()


def _profile(person: Person) -> dict[str, str]:
    return {
        "real_name": person.name,
        "display_name": person.name,
        "email": person.email_address,
        "title": person.title,
    }


def _user_object(person: Person, user_id: str) -> dict[str, object]:
    return {
        "id": user_id,
        "name": person.email_address.split("@")[0],
        "real_name": person.name,
        "profile": _profile(person),
        "is_bot": False,
        "deleted": False,
    }


def _find_by_ts(
    messages: Sequence[ChatMessage], message_ts: str, channel_id: str
) -> ChatMessage:
    for message in messages:
        if message.ts == message_ts:
            return message
    raise UnknownRefError(f"no message {message_ts} in {channel_id}")


def _search_messages(
    db_path: Path, query: str, limit: int, cursor: str | None, *, kinds: tuple[str, ...]
) -> dict:
    """The body both search tools share; ``kinds`` is what they may see."""

    limit = max(1, min(limit, 20))
    needles, filters = _parse_query(query)
    lowered = [needle.lower() for needle in needles]
    with connect_readonly(db_path) as connection:
        directory = _load(connection)
        searched = [
            conversation
            for conversation in directory.conversations.values()
            if conversation.kind in kinds
        ]
        if "in" in filters:
            wanted = filters["in"].lstrip("#").lower()
            searched = [
                c for c in searched if (_channel_name(c) or "").lower() == wanted
            ]
        messages: list[ChatMessage] = []
        reactions: list[Reaction] = []
        for conversation in searched:
            conversation_messages, conversation_reactions = _conversation_messages(
                connection, conversation
            )
            messages += conversation_messages
            reactions += conversation_reactions
    senders = (
        _senders_matching(directory, filters["from"]) if "from" in filters else None
    )
    matches = []
    for message in messages:
        body = message.body.lower()
        if any(needle not in body for needle in lowered):
            continue
        if senders is not None and message.sender not in senders:
            continue
        when = _event_date(directory.epoch, message.time)
        if "before" in filters and when >= date.fromisoformat(filters["before"]):
            continue
        if "after" in filters and when <= date.fromisoformat(filters["after"]):
            continue
        matches.append(message)
    matches.sort(key=lambda m: _ts_key(m.ts), reverse=True)
    messages.sort(key=lambda m: _ts_key(m.ts))
    objects = _message_objects(messages, reactions, directory)
    by_conversation = {c.conversation_id: c for c in searched}
    page, next_cursor = _page(matches, limit, cursor)
    results = []
    for message in page:
        conversation = by_conversation[message.conversation_id]
        results.append(
            {
                **objects[message.chat_message_id],
                "channel": {
                    "id": directory.channel_ids[conversation.conversation_id],
                    "name": _channel_name(conversation),
                },
            }
        )
    return {
        "ok": True,
        "messages": {"matches": results, "total": len(matches)},
        "response_metadata": {"next_cursor": next_cursor},
    }


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def slack_search_channels(
        query: str, limit: int = 100, cursor: str | None = None
    ) -> dict:
        """Find conversations by name, topic, or purpose; empty query lists all."""
        needle = query.lower()
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            member_counts = Counter(
                member.conversation_id for member in MEMBERS.select(connection)
            )
        matches = []
        for conversation in directory.conversations.values():
            name = _channel_name(conversation)
            haystacks = (name or "", conversation.topic, conversation.purpose)
            if needle and not any(needle in hay.lower() for hay in haystacks):
                continue
            matches.append(
                {
                    "id": directory.channel_ids[conversation.conversation_id],
                    "name": name,
                    "is_channel": conversation.kind == "channel",
                    "is_im": conversation.kind == "dm",
                    "is_private": False,
                    "is_archived": False,
                    "topic": {
                        "value": conversation.topic,
                        "creator": "",
                        "last_set": 0,
                    },
                    "purpose": {
                        "value": conversation.purpose,
                        "creator": "",
                        "last_set": 0,
                    },
                    "num_members": member_counts[conversation.conversation_id],
                }
            )
        page, next_cursor = _page(matches, limit, cursor)
        return {
            "ok": True,
            "channels": page,
            "response_metadata": {"next_cursor": next_cursor},
        }

    @server.tool()
    def slack_read_channel(
        channel_id: str,
        limit: int = 20,
        oldest: str | None = None,
        latest: str | None = None,
    ) -> dict:
        """Read a channel's message history, newest first; at most 100
        messages per call (window long histories with oldest/latest)."""
        limit = max(1, min(limit, 100))
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            messages, reactions = _conversation_messages(connection, conversation)
        objects = _message_objects(messages, reactions, directory)
        window = [
            message
            for message in messages
            if (oldest is None or float(message.ts) >= float(oldest))
            and (latest is None or float(message.ts) <= float(latest))
        ]
        newest_first = list(reversed(window))
        return {
            "ok": True,
            "messages": [
                objects[message.chat_message_id] for message in newest_first[:limit]
            ],
            "has_more": len(window) > limit,
        }

    @server.tool()
    def slack_read_thread(channel_id: str, message_ts: str) -> dict:
        """Read a thread: the parent message first, then replies in order."""
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            messages, reactions = _conversation_messages(connection, conversation)
        target = _find_by_ts(messages, message_ts, channel_id)
        by_id = {message.chat_message_id: message for message in messages}
        root = by_id[target.reply_to] if target.reply_to else target
        replies = [m for m in messages if m.reply_to == root.chat_message_id]
        objects = _message_objects(messages, reactions, directory)
        return {
            "ok": True,
            "messages": [
                objects[message.chat_message_id] for message in (root, *replies)
            ],
        }

    @server.tool()
    def slack_search_public(
        query: str, limit: int = 20, cursor: str | None = None
    ) -> dict:
        """Search public channel messages; supports "phrases", in:, from:,
        before:, after:. At most 20 matches per call (page with the
        response's next_cursor; total reports the full match count). Dms are
        out of reach here — use slack_search_public_and_private for those."""
        return _search_messages(db_path, query, limit, cursor, kinds=("channel",))

    @server.tool()
    def slack_search_public_and_private(
        query: str, limit: int = 20, cursor: str | None = None
    ) -> dict:
        """Search every conversation this account can read — public channels
        and dms alike — with the same query grammar as slack_search_public:
        "phrases", in:, from:, before:, after:. At most 20 matches per call
        (page with the response's next_cursor)."""
        return _search_messages(db_path, query, limit, cursor, kinds=("channel", "dm"))

    @server.tool()
    def slack_search_users(query: str, limit: int = 100) -> dict:
        """Find workspace users by name, title, or email; empty query lists all."""
        needle = query.lower()
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
        members = [
            _user_object(person, directory.user_ids[person_id])
            for person_id, person in directory.people.items()
            if not needle
            or any(
                needle in hay.lower()
                for hay in (person.name, person.title, person.email_address)
            )
        ]
        return {"ok": True, "members": members[:limit]}

    @server.tool()
    def slack_read_user_profile(user_id: str) -> dict:
        """Read one user's profile."""
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
        person = directory.resolve_person(user_id)
        return {"ok": True, "profile": _profile(person)}

    @server.tool()
    def slack_list_channel_members(channel_id: str, limit: int = 100) -> dict:
        """List the user ids belonging to a channel."""
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            members = MEMBERS.select(
                connection, where={"conversation_id": conversation.conversation_id}
            )
        ids = sorted(directory.user_ids[member.person_id] for member in members)
        return {"ok": True, "members": ids[:limit]}

    @server.tool()
    def slack_get_reactions(channel_id: str, message_ts: str) -> dict:
        """Read the reactions on one message."""
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            messages, reactions = _conversation_messages(connection, conversation)
        target = _find_by_ts(messages, message_ts, channel_id)
        objects = _message_objects(messages, reactions, directory)
        message = dict(objects[target.chat_message_id])
        message.setdefault("reactions", [])
        return {"ok": True, "message": message}

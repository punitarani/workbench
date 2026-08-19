"""Read and write tools over the slack database, shaped like Slack's Web API.

Display ids are derived per call, never stored: channels are ``C{n:08d}``
and users ``U{n:08d}`` where ``n`` is the 1-based position of the internal
id in sorted order over the whole workspace, so the mapping is
deterministic for a given database and independent of who is looking.
Every tool accepts either the Slack-style id or the internal id.

Search comes in Slack's own two flavors: ``slack_search_public`` sees
channels only, and ``slack_search_public_and_private`` also sees the
conversations the caller belongs to, dms included. Both share one query
grammar. ``sort="score"`` carries no learned relevance here: matches in
``context_channel_id`` rank first, then recency.

``response_format`` follows Slack on every tool that has it: ``detailed``
is the full object, ``concise`` the fields a person skims, ``ids_only``
bare ids.

Writing: the seven write tools never touch the projected tables. A post, a
draft, a scheduled send, a new conversation, a reaction, and a canvas each
land in their own action table, so the world's record stays the world's and
a grader reads exactly what the agent did. The read tools serve both halves,
because someone who posts to a channel sees their message in it. Writes need
a seat (``WORKBENCH_SEAT``): a post with no author is a post misattributed.

Workspace scoping: the optional ``WORKBENCH_SEAT`` environment variable
names the person_id whose Slack this server presents; it is read at call
time, never at import time. When set, only conversations that person is a
member of exist for these tools — an unjoined channel and someone else's
dm are both unknown ids. When unset the server reads workspace-wide. The
user directory is workspace-wide either way, as it is in Slack.

What the record does not carry: no bot and no deactivated accounts, so
``include_bots`` and ``include_deleted`` only ever widen a set that is
already everyone; no archived channels, so ``include_archived`` does the
same; and no uploaded files, so the only files are canvases.
"""

import re
import sqlite3
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from tools.db import connect_readonly, connect_readwrite
from tools.framework import (
    PEOPLE_TABLE,
    Person,
    UnknownRefError,
    read_epoch,
    require_seat,
    seat,
)
from tools.slack.tables import (
    ADDED_REACTIONS,
    CANVASES,
    CONVERSATIONS,
    CREATED_CONVERSATIONS,
    MEMBERS,
    MESSAGE_DRAFTS,
    MESSAGES,
    REACTIONS,
    SCHEDULED_MESSAGES,
    SENT_MESSAGES,
    AddedReaction,
    Canvas,
    ChatMessage,
    Conversation,
    CreatedConversation,
    MessageDraft,
    Reaction,
    ScheduledMessage,
    SentMessage,
)

_FILTERS = ("in", "from", "before", "after")
_PHRASE = re.compile(r'"([^"]*)"')
_MAX_MESSAGES = 100
_MAX_MATCHES = 20
# The workspace has one locale; the record carries none per person.
_LOCALE = "en-US"

# Slack's own vocabularies, verbatim.
type ResponseFormat = Literal["detailed", "concise", "ids_only"]
type ChannelType = Literal["public_channel", "private_channel", "mpim", "im"]
type ContentType = Literal["messages", "files", "channels"]
type SortField = Literal["score", "timestamp"]
type SortDir = Literal["asc", "desc"]
type CanvasAction = Literal["append", "prepend", "replace"]

_CONCISE_MESSAGE = ("user", "text", "ts", "thread_ts", "channel")
_CONCISE_CHANNEL = ("id", "name", "num_members")
_CONCISE_USER = ("id", "name", "real_name")


@dataclass(frozen=True, slots=True)
class _Directory:
    # Only the conversations the seat may see; ``channel_ids`` still covers
    # the whole workspace so a display id means the same thing for everyone.
    conversations: dict[str, Conversation]
    channel_ids: dict[str, str]
    private_ids: frozenset[str]
    members: dict[str, tuple[str, ...]]
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


@dataclass(frozen=True, slots=True)
class _Search:
    """One search call. The two search tools differ only in ``kinds`` — the
    conversation kinds each is allowed to see."""

    query: str
    limit: int
    cursor: str | None
    kinds: tuple[str, ...]
    content_types: tuple[str, ...] | None
    after: str | None
    before: str | None
    context_channel_id: str | None
    include_context: bool
    max_context_length: int
    sort: str
    sort_dir: str
    response_format: str


def _invert(mapping: dict[str, str]) -> dict[str, str]:
    return {display: internal for internal, display in mapping.items()}


def _display_ids(internal_ids: Iterable[str], prefix: str) -> dict[str, str]:
    return {
        internal: f"{prefix}{position:08d}"
        for position, internal in enumerate(sorted(internal_ids), start=1)
    }


def _load(connection: sqlite3.Connection) -> _Directory:
    conversations = CONVERSATIONS.select(connection, order_by="conversation_id")
    created = CREATED_CONVERSATIONS.select(connection, order_by="conversation_id")
    people = PEOPLE_TABLE.select(connection, order_by="person_id")
    channel_ids = _display_ids((c.conversation_id for c in conversations), "C")
    # Conversations the agent opens continue the numbering rather than joining
    # the sort, so opening one never renumbers the workspace mid-rollout.
    for position, row in enumerate(created, start=len(channel_ids) + 1):
        channel_ids[row.conversation_id] = f"C{position:08d}"
    members: dict[str, list[str]] = {}
    for member in MEMBERS.select(connection):
        members.setdefault(member.conversation_id, []).append(member.person_id)
    for row in created:
        members[row.conversation_id] = [p for p in row.member_ids.split(",") if p]
    everything = {c.conversation_id: c for c in conversations} | {
        row.conversation_id: Conversation(
            conversation_id=row.conversation_id,
            name=row.name,
            kind=row.kind,
            topic="",
            purpose="",
        )
        for row in created
    }
    if (person := seat()) is not None:
        everything = {
            conversation_id: conversation
            for conversation_id, conversation in everything.items()
            if person in members.get(conversation_id, ())
        }
    return _Directory(
        conversations=everything,
        channel_ids=channel_ids,
        private_ids=frozenset(row.conversation_id for row in created if row.is_private),
        members={key: tuple(value) for key, value in members.items()},
        people={p.person_id: p for p in people},
        user_ids=_display_ids((p.person_id for p in people), "U"),
        epoch=read_epoch(connection),
    )


def _channel_name(conversation: Conversation) -> str | None:
    return conversation.name.lstrip("#") if conversation.name else conversation.name


def _channel_type(directory: _Directory, conversation: Conversation) -> str:
    if conversation.kind == "dm":
        members = directory.members.get(conversation.conversation_id, ())
        return "mpim" if len(members) > 2 else "im"
    if conversation.conversation_id in directory.private_ids:
        return "private_channel"
    return "public_channel"


def _channel_json(directory: _Directory, conversation: Conversation) -> dict:
    return {
        "id": directory.channel_ids[conversation.conversation_id],
        "name": _channel_name(conversation),
        "is_channel": conversation.kind == "channel",
        "is_im": conversation.kind == "dm",
        "is_private": conversation.conversation_id in directory.private_ids,
        "is_archived": False,
        "topic": {"value": conversation.topic, "creator": "", "last_set": 0},
        "purpose": {"value": conversation.purpose, "creator": "", "last_set": 0},
        "num_members": len(directory.members.get(conversation.conversation_id, ())),
    }


def _ts_key(ts: str) -> tuple[int, int]:
    seconds, _, microseconds = ts.partition(".")
    return (int(seconds), int(microseconds or 0))


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
    """A conversation as it reads now: the record plus what the agent added."""

    where = {"conversation_id": conversation.conversation_id}
    messages = MESSAGES.select(connection, where=where)
    messages += [
        ChatMessage(
            chat_message_id=sent.sent_message_id,
            conversation_id=sent.conversation_id,
            reply_to=sent.reply_to,
            sender=sent.sender,
            body=sent.body,
            time=sent.time,
            ts=sent.ts,
        )
        for sent in SENT_MESSAGES.select(connection, where=where)
    ]
    messages.sort(key=lambda m: _ts_key(m.ts))
    reactions = REACTIONS.select(connection, where=where)
    ids_by_ts = {m.ts: m.chat_message_id for m in messages}
    reactions += [
        Reaction(
            conversation_id=added.conversation_id,
            chat_message_id=ids_by_ts[added.message_ts],
            person_id=added.person_id,
            emoji=added.emoji,
        )
        for added in ADDED_REACTIONS.select(connection, where=where)
        if added.message_ts in ids_by_ts
    ]
    return messages, reactions


def _page[T](items: list[T], limit: int, cursor: str | None) -> tuple[list[T], str]:
    offset = int(cursor) if cursor else 0
    end = offset + limit
    return items[offset:end], str(end) if end < len(items) else ""


def _shape(
    records: list[dict], response_format: str, id_key: str, keep: tuple[str, ...]
) -> list:
    """Slack's response_format: the whole object, the fields a reader skims,
    or bare ids."""

    if response_format == "ids_only":
        return [record[id_key] for record in records]
    if response_format == "concise":
        return [
            {key: value for key, value in record.items() if key in keep}
            for record in records
        ]
    return records


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


def _within(when: date, after: str | None, before: str | None) -> bool:
    """after: and before: are exclusive on both ends, as in Slack."""

    if after is not None and when <= date.fromisoformat(after):
        return False
    return before is None or when < date.fromisoformat(before)


def _in_window(message: ChatMessage, oldest: str | None, latest: str | None) -> bool:
    key = _ts_key(message.ts)
    return (oldest is None or key >= _ts_key(oldest)) and (
        latest is None or key <= _ts_key(latest)
    )


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


def _reply_target(
    messages: Sequence[ChatMessage], thread_ts: str, channel_id: str
) -> str:
    # A reply addressed at a reply belongs to that thread's parent, as in Slack.
    parent = _find_by_ts(messages, thread_ts, channel_id)
    return parent.reply_to or parent.chat_message_id


def _excerpt(message: dict[str, object], max_length: int) -> dict[str, object]:
    return {
        "user": message["user"],
        "text": str(message["text"])[:max_length],
        "ts": message["ts"],
    }


def _neighbours(
    messages: Sequence[ChatMessage],
    objects: dict[str, dict[str, object]],
    max_length: int,
) -> dict[str, dict[str, object]]:
    """The message either side of each one, which is Slack's search context."""

    by_conversation: dict[str, list[ChatMessage]] = {}
    for message in messages:
        by_conversation.setdefault(message.conversation_id, []).append(message)
    around: dict[str, dict[str, object]] = {}
    for conversation_messages in by_conversation.values():
        for position, message in enumerate(conversation_messages):
            context: dict[str, object] = {}
            if position:
                previous = conversation_messages[position - 1]
                context["previous"] = _excerpt(
                    objects[previous.chat_message_id], max_length
                )
            if position + 1 < len(conversation_messages):
                following = conversation_messages[position + 1]
                context["next"] = _excerpt(
                    objects[following.chat_message_id], max_length
                )
            around[message.chat_message_id] = context
    return around


def _search_messages(db_path: Path, search: _Search) -> dict:
    """The body both search tools share."""

    limit = max(1, min(search.limit, _MAX_MATCHES))
    needles, filters = _parse_query(search.query)
    lowered = [needle.lower() for needle in needles]
    with connect_readonly(db_path) as connection:
        directory = _load(connection)
        searched = [
            conversation
            for conversation in directory.conversations.values()
            if conversation.kind in search.kinds
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
    context_id = (
        directory.resolve_channel(search.context_channel_id).conversation_id
        if search.context_channel_id
        else None
    )
    senders = (
        _senders_matching(directory, filters["from"]) if "from" in filters else None
    )
    # These tools search messages; the record shares no files, and channels
    # have their own search tool.
    searchable = search.content_types is None or "messages" in search.content_types
    matches = []
    for message in messages if searchable else ():
        body = message.body.lower()
        if any(needle not in body for needle in lowered):
            continue
        if senders is not None and message.sender not in senders:
            continue
        when = _event_date(directory.epoch, message.time)
        if not _within(when, filters.get("after"), filters.get("before")):
            continue
        if not _within(when, search.after, search.before):
            continue
        matches.append(message)
    matches.sort(key=lambda m: _ts_key(m.ts), reverse=search.sort_dir == "desc")
    if search.sort == "score" and context_id is not None:
        matches.sort(key=lambda m: m.conversation_id != context_id)
    messages.sort(key=lambda m: _ts_key(m.ts))
    objects = _message_objects(messages, reactions, directory)
    by_conversation = {c.conversation_id: c for c in searched}
    page, next_cursor = _page(matches, limit, search.cursor)
    around = (
        _neighbours(messages, objects, search.max_context_length)
        if search.include_context
        else {}
    )
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
                **around.get(message.chat_message_id, {}),
            }
        )
    return {
        "ok": True,
        "messages": {
            "matches": _shape(results, search.response_format, "ts", _CONCISE_MESSAGE),
            "total": len(matches),
        },
        "response_metadata": {"next_cursor": next_cursor},
    }


def _next_id(
    connection: sqlite3.Connection, table: str, prefix: str, width: int = 8
) -> str:
    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    return f"{prefix}{count + 1:0{width}d}"


def _head_time(connection: sqlite3.Connection) -> int:
    """The world's head time — a rollout's "now" is where the record stops."""

    return connection.execute("SELECT MAX(time) FROM messages").fetchone()[0] or 0


def _post_time(connection: sqlite3.Connection, epoch: datetime) -> tuple[int, str]:
    """When a post lands: one second past the head per post already sent, so
    every agent ts is unique and reads back in the order it was sent."""

    posted = connection.execute("SELECT COUNT(*) FROM sent_messages").fetchone()[0]
    time = _head_time(connection) + 1 + posted
    return time, f"{int((epoch + timedelta(seconds=time)).timestamp())}.000000"


def _open_draft(connection: sqlite3.Connection, draft_id: str) -> MessageDraft:
    drafts = MESSAGE_DRAFTS.select(connection, where={"draft_id": draft_id})
    if not drafts or drafts[0].sent:
        raise UnknownRefError(f"no unsent draft {draft_id}")
    return drafts[0]


def _name_taken(connection: sqlite3.Connection, channel_name: str) -> bool:
    taken = {row.name for row in CONVERSATIONS.select(connection)} | {
        row.name for row in CREATED_CONVERSATIONS.select(connection)
    }
    return f"#{channel_name.lstrip('#')}" in taken


def _find_canvas(
    connection: sqlite3.Connection, canvas_id: str, noun: str = "canvas"
) -> Canvas:
    canvases = CANVASES.select(connection, where={"canvas_id": canvas_id})
    if not canvases:
        raise UnknownRefError(f"no {noun} {canvas_id}")
    return canvases[0]


def _sections(content: str) -> list[dict[str, str]]:
    """A canvas's blocks, with ids derived per call like every display id."""

    blocks = [block.strip() for block in content.split("\n\n") if block.strip()]
    return [
        {"id": f"S{position:08d}", "content": block}
        for position, block in enumerate(blocks, start=1)
    ]


def _canvas_json(canvas: Canvas) -> dict:
    return {
        "id": canvas.canvas_id,
        "title": canvas.title,
        "sections": _sections(canvas.content),
    }


def _edit(current: str, content: str, action: str, section_id: str | None) -> str:
    """One canvas edit as a splice: where the new content lands and what it
    displaces. A section_id scopes the edit to that section."""

    sections = _sections(current)
    bodies = [section["content"] for section in sections]
    if section_id is None:
        at, end = {
            "append": (len(bodies), len(bodies)),
            "prepend": (0, 0),
            "replace": (0, len(bodies)),
        }[action]
    else:
        ids = [section["id"] for section in sections]
        if section_id not in ids:
            raise UnknownRefError(f"no section {section_id}")
        position = ids.index(section_id)
        at, end = {
            "append": (position + 1, position + 1),
            "prepend": (position, position),
            "replace": (position, position + 1),
        }[action]
    spliced = (*bodies[:at], content, *bodies[end:])
    return "\n\n".join(block for block in spliced if block)


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def slack_search_channels(
        query: str,
        limit: int = 100,
        cursor: str | None = None,
        include_archived: bool = False,
        channel_types: list[ChannelType] | None = None,
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """Find conversations by name, topic, or purpose; empty query lists all."""
        # Nothing on the record is archived, so include_archived only ever
        # widens a listing that is already every channel.
        del include_archived
        needle = query.lower()
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
        matches = []
        for conversation in directory.conversations.values():
            name = _channel_name(conversation)
            haystacks = (name or "", conversation.topic, conversation.purpose)
            if needle and not any(needle in hay.lower() for hay in haystacks):
                continue
            kind = _channel_type(directory, conversation)
            if channel_types and kind not in channel_types:
                continue
            matches.append(_channel_json(directory, conversation))
        page, next_cursor = _page(matches, limit, cursor)
        return {
            "ok": True,
            "channels": _shape(page, response_format, "id", _CONCISE_CHANNEL),
            "response_metadata": {"next_cursor": next_cursor},
        }

    @server.tool()
    def slack_read_channel(
        channel_id: str,
        limit: int = 20,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """Read a channel's message history, newest first; at most 100
        messages per call (window long histories with oldest/latest, or page
        with the response's next_cursor)."""
        limit = max(1, min(limit, _MAX_MESSAGES))
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            messages, reactions = _conversation_messages(connection, conversation)
        objects = _message_objects(messages, reactions, directory)
        window = [m for m in messages if _in_window(m, oldest, latest)]
        page, next_cursor = _page(list(reversed(window)), limit, cursor)
        history = [objects[message.chat_message_id] for message in page]
        return {
            "ok": True,
            "messages": _shape(history, response_format, "ts", _CONCISE_MESSAGE),
            "has_more": bool(next_cursor),
            "response_metadata": {"next_cursor": next_cursor},
        }

    @server.tool()
    def slack_read_thread(
        channel_id: str,
        message_ts: str,
        limit: int = 100,
        cursor: str | None = None,
        oldest: str | None = None,
        latest: str | None = None,
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """Read a thread: the parent message first, then replies in order."""
        limit = max(1, min(limit, _MAX_MESSAGES))
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
            messages, reactions = _conversation_messages(connection, conversation)
        target = _find_by_ts(messages, message_ts, channel_id)
        by_id = {message.chat_message_id: message for message in messages}
        root = by_id[target.reply_to] if target.reply_to else target
        # Slack always returns the parent; oldest/latest window the replies.
        replies = [
            m
            for m in messages
            if m.reply_to == root.chat_message_id and _in_window(m, oldest, latest)
        ]
        objects = _message_objects(messages, reactions, directory)
        page, next_cursor = _page(replies, limit, cursor)
        thread = [objects[message.chat_message_id] for message in (root, *page)]
        return {
            "ok": True,
            "messages": _shape(thread, response_format, "ts", _CONCISE_MESSAGE),
            "has_more": bool(next_cursor),
            "response_metadata": {"next_cursor": next_cursor},
        }

    @server.tool()
    def slack_search_public(
        query: str,
        limit: int = 20,
        cursor: str | None = None,
        content_types: list[ContentType] | None = None,
        after: str | None = None,
        before: str | None = None,
        context_channel_id: str | None = None,
        include_bots: bool = False,
        include_context: bool = False,
        max_context_length: int = 200,
        sort: SortField = "score",
        sort_dir: SortDir = "desc",
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """Search public channel messages; supports "phrases", in:, from:,
        before:, after:. At most 20 matches per call (page with the
        response's next_cursor; total reports the full match count). Dms are
        out of reach here — use slack_search_public_and_private for those."""
        # No sender on the record is a bot, so include_bots changes nothing.
        del include_bots
        return _search_messages(
            db_path,
            _Search(
                query=query,
                limit=limit,
                cursor=cursor,
                kinds=("channel",),
                content_types=tuple(content_types) if content_types else None,
                after=after,
                before=before,
                context_channel_id=context_channel_id,
                include_context=include_context,
                max_context_length=max_context_length,
                sort=sort,
                sort_dir=sort_dir,
                response_format=response_format,
            ),
        )

    @server.tool()
    def slack_search_public_and_private(
        query: str,
        limit: int = 20,
        cursor: str | None = None,
        content_types: list[ContentType] | None = None,
        after: str | None = None,
        before: str | None = None,
        context_channel_id: str | None = None,
        include_bots: bool = False,
        include_context: bool = False,
        max_context_length: int = 200,
        sort: SortField = "score",
        sort_dir: SortDir = "desc",
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """Search every conversation this account can read — public channels
        and dms alike — with the same query grammar as slack_search_public:
        "phrases", in:, from:, before:, after:. At most 20 matches per call
        (page with the response's next_cursor)."""
        del include_bots
        return _search_messages(
            db_path,
            _Search(
                query=query,
                limit=limit,
                cursor=cursor,
                kinds=("channel", "dm"),
                content_types=tuple(content_types) if content_types else None,
                after=after,
                before=before,
                context_channel_id=context_channel_id,
                include_context=include_context,
                max_context_length=max_context_length,
                sort=sort,
                sort_dir=sort_dir,
                response_format=response_format,
            ),
        )

    @server.tool()
    def slack_search_users(
        query: str, limit: int = 100, response_format: ResponseFormat = "detailed"
    ) -> dict:
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
        return {
            "ok": True,
            "members": _shape(members[:limit], response_format, "id", _CONCISE_USER),
        }

    @server.tool()
    def slack_read_user_profile(
        user_id: str | None = None, include_locale: bool = False
    ) -> dict:
        """Read a user's profile; defaults to the account this server presents."""
        person_id = user_id or require_seat("slack_read_user_profile")
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
        profile = _profile(directory.resolve_person(person_id))
        if include_locale:
            profile |= {"locale": _LOCALE}
        return {"ok": True, "profile": profile}

    @server.tool()
    def slack_list_channel_members(
        channel_id: str,
        limit: int = 100,
        include_bots: bool = False,
        include_deleted: bool = False,
        response_format: ResponseFormat = "detailed",
    ) -> dict:
        """List who belongs to a channel."""
        # No account on the record is a bot or deactivated, so both flags only
        # ever widen a list that is already every member.
        del include_bots, include_deleted
        with connect_readonly(db_path) as connection:
            directory = _load(connection)
            conversation = directory.resolve_channel(channel_id)
        members = sorted(
            (
                _user_object(directory.people[person_id], directory.user_ids[person_id])
                for person_id in directory.members.get(conversation.conversation_id, ())
            ),
            key=lambda member: member["id"],
        )
        return {
            "ok": True,
            "members": _shape(members[:limit], response_format, "id", _CONCISE_USER),
        }

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

    @server.tool()
    def slack_search_emojis(query: str) -> dict:
        """Find the emoji this workspace actually uses before reacting with one."""
        needle = query.lower()
        with connect_readonly(db_path) as connection:
            counts = Counter(r.emoji for r in REACTIONS.select(connection))
            counts += Counter(r.emoji for r in ADDED_REACTIONS.select(connection))
        return {
            "ok": True,
            "emojis": [
                {"name": name, "count": count}
                for name, count in sorted(counts.items())
                if not needle or needle in name.lower()
            ],
        }

    @server.tool()
    def slack_read_file(file_id: str) -> dict:
        """Read a file shared in Slack. Canvases are files, and the projected
        workspace shares no others."""
        with connect_readonly(db_path) as connection:
            canvas = _find_canvas(connection, file_id, "file")
        return {
            "ok": True,
            "file": {
                "id": canvas.canvas_id,
                "title": canvas.title,
                "filetype": "canvas",
                "content": canvas.content,
            },
        }

    @server.tool()
    def slack_read_canvas(canvas_id: str) -> dict:
        """Read a canvas section by section; a section's id addresses an edit."""
        with connect_readonly(db_path) as connection:
            canvas = _find_canvas(connection, canvas_id)
        return {"ok": True, "canvas": _canvas_json(canvas)}

    @server.tool()
    def slack_send_message(
        channel_id: str,
        message: str,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
        draft_id: str | None = None,
    ) -> dict:
        """Post to a channel or dm as this account. Pass thread_ts to reply in
        a thread, reply_broadcast to send that reply to the channel too, or
        draft_id with an empty message to post a draft as it stands."""
        person = require_seat("slack_send_message")
        with connect_readwrite(db_path) as connection:
            directory = _load(connection)
            directory.resolve_person(person)
            conversation = directory.resolve_channel(channel_id)
            messages, _ = _conversation_messages(connection, conversation)
            draft = _open_draft(connection, draft_id) if draft_id else None
            body = message or (draft.body if draft else "")
            reply_to = (
                _reply_target(messages, thread_ts, channel_id)
                if thread_ts is not None
                else (draft.reply_to if draft else None)
            )
            time, ts = _post_time(connection, directory.epoch)
            SENT_MESSAGES.insert(
                connection,
                [
                    SentMessage(
                        sent_message_id=_next_id(
                            connection, "sent_messages", "chm-agent-", 6
                        ),
                        conversation_id=conversation.conversation_id,
                        reply_to=reply_to,
                        sender=person,
                        body=body,
                        time=time,
                        ts=ts,
                        reply_broadcast=reply_broadcast,
                        draft_id=draft_id,
                    )
                ],
            )
            if draft is not None:
                connection.execute(
                    "UPDATE message_drafts SET sent=1 WHERE draft_id=?", (draft_id,)
                )
            connection.commit()
        return {
            "ok": True,
            "channel": directory.channel_ids[conversation.conversation_id],
            "ts": ts,
            "message": {
                "type": "message",
                "user": directory.user_ids[person],
                "text": body,
                "ts": ts,
            },
        }

    @server.tool()
    def slack_send_message_draft(
        channel_id: str, message: str, thread_ts: str | None = None
    ) -> dict:
        """Compose a message without posting it; slack_send_message posts it
        by draft_id when a person has approved the wording."""
        person = require_seat("slack_send_message_draft")
        with connect_readwrite(db_path) as connection:
            directory = _load(connection)
            directory.resolve_person(person)
            conversation = directory.resolve_channel(channel_id)
            messages, _ = _conversation_messages(connection, conversation)
            draft = MessageDraft(
                draft_id=_next_id(connection, "message_drafts", "D"),
                conversation_id=conversation.conversation_id,
                reply_to=(
                    _reply_target(messages, thread_ts, channel_id)
                    if thread_ts is not None
                    else None
                ),
                author=person,
                body=message,
                time=_head_time(connection),
                sent=False,
            )
            MESSAGE_DRAFTS.insert(connection, [draft])
            connection.commit()
        return {
            "ok": True,
            "draft_id": draft.draft_id,
            "channel": directory.channel_ids[conversation.conversation_id],
        }

    @server.tool()
    def slack_schedule_message(
        channel_id: str,
        message: str,
        post_at: int,
        thread_ts: str | None = None,
        reply_broadcast: bool = False,
    ) -> dict:
        """Queue a message to post at post_at (unix seconds) — the tool for
        anything that should land at the start of someone's day."""
        person = require_seat("slack_schedule_message")
        with connect_readwrite(db_path) as connection:
            directory = _load(connection)
            directory.resolve_person(person)
            conversation = directory.resolve_channel(channel_id)
            messages, _ = _conversation_messages(connection, conversation)
            scheduled = ScheduledMessage(
                scheduled_message_id=_next_id(connection, "scheduled_messages", "Q"),
                conversation_id=conversation.conversation_id,
                reply_to=(
                    _reply_target(messages, thread_ts, channel_id)
                    if thread_ts is not None
                    else None
                ),
                sender=person,
                body=message,
                post_at=post_at,
                reply_broadcast=reply_broadcast,
            )
            SCHEDULED_MESSAGES.insert(connection, [scheduled])
            connection.commit()
        return {
            "ok": True,
            "scheduled_message_id": scheduled.scheduled_message_id,
            "channel": directory.channel_ids[conversation.conversation_id],
            "post_at": post_at,
        }

    @server.tool()
    def slack_create_conversation(
        channel_name: str | None = None,
        is_private: bool = False,
        user_ids: list[str] | None = None,
    ) -> dict:
        """Open a channel for a piece of work, or a dm with the people named
        in user_ids. This account joins whatever it opens."""
        person = require_seat("slack_create_conversation")
        if not channel_name and not user_ids:
            raise UnknownRefError("a conversation needs a channel_name or user_ids")
        with connect_readwrite(db_path) as connection:
            directory = _load(connection)
            invited = [
                directory.resolve_person(user_id).person_id
                for user_id in (user_ids or ())
            ]
            # Channel names are unique workspace-wide, including the channels
            # this seat cannot see.
            if channel_name and _name_taken(connection, channel_name):
                raise UnknownRefError(f"channel {channel_name} already exists")
            created = CreatedConversation(
                conversation_id=_next_id(
                    connection, "created_conversations", "cnv-agent-", 6
                ),
                name=f"#{channel_name.lstrip('#')}" if channel_name else None,
                kind="channel" if channel_name else "dm",
                is_private=is_private,
                member_ids=",".join(dict.fromkeys([person, *invited])),
                time=_head_time(connection),
            )
            CREATED_CONVERSATIONS.insert(connection, [created])
            connection.commit()
            directory = _load(connection)
        conversation = directory.conversations[created.conversation_id]
        return {"ok": True, "channel": _channel_json(directory, conversation)}

    @server.tool()
    def slack_add_reaction(channel_id: str, message_ts: str, emoji: str) -> dict:
        """React to a message — a workplace's ack, decision, or applause."""
        person = require_seat("slack_add_reaction")
        name = emoji.strip(":")
        with connect_readwrite(db_path) as connection:
            directory = _load(connection)
            directory.resolve_person(person)
            conversation = directory.resolve_channel(channel_id)
            messages, _ = _conversation_messages(connection, conversation)
            _find_by_ts(messages, message_ts, channel_id)
            reaction = AddedReaction(
                conversation_id=conversation.conversation_id,
                message_ts=message_ts,
                person_id=person,
                emoji=name,
            )
            # Slack refuses a second identical reaction; adding one twice is
            # a no-op rather than a duplicate row.
            if not ADDED_REACTIONS.select(connection, where=reaction.model_dump()):
                ADDED_REACTIONS.insert(connection, [reaction])
                connection.commit()
        return {
            "ok": True,
            "channel": directory.channel_ids[conversation.conversation_id],
        }

    @server.tool()
    def slack_create_canvas(title: str, content: str) -> dict:
        """Write a canvas — where a standing doc lives beside the channel that
        needs it. Blank lines separate sections."""
        person = require_seat("slack_create_canvas")
        with connect_readwrite(db_path) as connection:
            canvas = Canvas(
                canvas_id=_next_id(connection, "canvases", "F"),
                title=title,
                content=content,
                owner=person,
                time=_head_time(connection),
            )
            CANVASES.insert(connection, [canvas])
            connection.commit()
        return {"ok": True, "canvas": _canvas_json(canvas)}

    @server.tool()
    def slack_update_canvas(
        canvas_id: str,
        content: str,
        action: CanvasAction = "append",
        section_id: str | None = None,
    ) -> dict:
        """Edit a canvas: append, prepend, or replace the whole thing — or
        pass the section_id slack_read_canvas reports to edit one section."""
        require_seat("slack_update_canvas")
        with connect_readwrite(db_path) as connection:
            canvas = _find_canvas(connection, canvas_id)
            updated = _edit(canvas.content, content, action, section_id)
            connection.execute(
                "UPDATE canvases SET content=? WHERE canvas_id=?",
                (updated, canvas.canvas_id),
            )
            connection.commit()
        return {
            "ok": True,
            "canvas": _canvas_json(canvas.model_copy(update={"content": updated})),
        }

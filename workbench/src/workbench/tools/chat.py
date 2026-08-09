"""Chat projection: conversations, members, and messages become chat.db."""

from collections.abc import Sequence
from pathlib import Path

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.tools._sql import PEOPLE_SCHEMA, create_db, insert, project_people

handled_tags = ("chat.conversation.created", "chat.message", "person.record")

SCHEMA = (
    PEOPLE_SCHEMA
    + """
CREATE TABLE conversations (
    conversation_id TEXT PRIMARY KEY,
    name TEXT,
    kind TEXT NOT NULL CHECK (kind IN ('channel', 'dm'))
);
CREATE TABLE members (
    conversation_id TEXT NOT NULL,
    person_id TEXT NOT NULL
);
CREATE TABLE messages (
    chat_message_id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    reply_to TEXT,
    sender TEXT NOT NULL,
    body TEXT NOT NULL,
    time INTEGER NOT NULL
);
"""
)


def project(events: Sequence[Event], db_path: Path) -> None:
    with create_db(db_path, SCHEMA) as connection:
        project_people(connection, events)
        for event in events:
            payload = event.payload
            if isinstance(payload, ChatConversationCreatedPayload):
                insert(
                    connection,
                    "conversations",
                    ("conversation_id", "name", "kind"),
                    [
                        (
                            payload.conversation_id,
                            payload.name,
                            payload.conversation_type,
                        )
                    ],
                )
                insert(
                    connection,
                    "members",
                    ("conversation_id", "person_id"),
                    ((payload.conversation_id, p) for p in payload.members),
                )
            elif isinstance(payload, ChatMessagePayload):
                insert(
                    connection,
                    "messages",
                    (
                        "chat_message_id",
                        "conversation_id",
                        "reply_to",
                        "sender",
                        "body",
                        "time",
                    ),
                    [
                        (
                            payload.chat_message_id,
                            payload.conversation_id,
                            payload.reply_to,
                            payload.sender,
                            payload.body,
                            int(event.time),
                        )
                    ],
                )

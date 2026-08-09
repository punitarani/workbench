"""Mail projection: the world log's email events become mail.db."""

from collections.abc import Sequence
from pathlib import Path

from workbench.core.events import Event
from workbench.core.events.email import EmailMessagePayload
from workbench.tools._sql import PEOPLE_SCHEMA, create_db, insert, project_people

handled_tags = ("email.message", "person.record")

SCHEMA = (
    PEOPLE_SCHEMA
    + """
CREATE TABLE messages (
    message_id TEXT PRIMARY KEY,
    thread_id TEXT NOT NULL,
    in_reply_to TEXT,
    sender TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    time INTEGER NOT NULL
);
CREATE TABLE recipients (
    message_id TEXT NOT NULL,
    person_id TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('to', 'cc'))
);
CREATE TABLE attachments (
    message_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    document_id TEXT NOT NULL
);
"""
)


def project(events: Sequence[Event], db_path: Path) -> None:
    with create_db(db_path, SCHEMA) as connection:
        project_people(connection, events)
        for event in events:
            payload = event.payload
            if not isinstance(payload, EmailMessagePayload):
                continue
            insert(
                connection,
                "messages",
                (
                    "message_id",
                    "thread_id",
                    "in_reply_to",
                    "sender",
                    "subject",
                    "body",
                    "time",
                ),
                [
                    (
                        payload.message_id,
                        payload.thread_id,
                        payload.in_reply_to,
                        payload.sender,
                        payload.subject,
                        payload.body,
                        int(event.time),
                    )
                ],
            )
            insert(
                connection,
                "recipients",
                ("message_id", "person_id", "kind"),
                [
                    *((payload.message_id, p, "to") for p in payload.to),
                    *((payload.message_id, p, "cc") for p in payload.cc),
                ],
            )
            insert(
                connection,
                "attachments",
                ("message_id", "filename", "media_type", "document_id"),
                (
                    (payload.message_id, a.filename, a.media_type, a.document_id)
                    for a in payload.attachments
                ),
            )

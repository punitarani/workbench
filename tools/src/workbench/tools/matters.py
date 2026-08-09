"""Matter-tracker projection: folded ticket state plus complete history."""

from collections.abc import Sequence
from pathlib import Path

from workbench.core.events import Event
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.tools._sql import PEOPLE_SCHEMA, create_db, insert, project_people

handled_tags = (
    "ticket.created",
    "ticket.updated",
    "ticket.commented",
    "person.record",
)

FOLDED_FIELDS = ("title", "description", "assignee", "status", "priority")

SCHEMA = (
    PEOPLE_SCHEMA
    + """
CREATE TABLE tickets (
    ticket_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    requester TEXT NOT NULL,
    assignee TEXT,
    status TEXT NOT NULL,
    priority TEXT NOT NULL,
    ticket_type TEXT NOT NULL,
    created_time INTEGER NOT NULL
);
CREATE TABLE history (
    ticket_id TEXT NOT NULL,
    actor TEXT NOT NULL,
    field TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    time INTEGER NOT NULL
);
CREATE TABLE comments (
    ticket_id TEXT NOT NULL,
    actor TEXT NOT NULL,
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
            if isinstance(payload, TicketCreatedPayload):
                insert(
                    connection,
                    "tickets",
                    (
                        "ticket_id",
                        "title",
                        "description",
                        "requester",
                        "assignee",
                        "status",
                        "priority",
                        "ticket_type",
                        "created_time",
                    ),
                    [
                        (
                            payload.ticket_id,
                            payload.title,
                            payload.description,
                            payload.requester,
                            payload.assignee,
                            payload.status,
                            payload.priority,
                            payload.ticket_type,
                            int(event.time),
                        )
                    ],
                )
            elif isinstance(payload, TicketUpdatedPayload):
                for change in payload.changes:
                    insert(
                        connection,
                        "history",
                        (
                            "ticket_id",
                            "actor",
                            "field",
                            "old_value",
                            "new_value",
                            "time",
                        ),
                        [
                            (
                                payload.ticket_id,
                                payload.actor,
                                change.field,
                                change.old,
                                change.new,
                                int(event.time),
                            )
                        ],
                    )
                    if change.field in FOLDED_FIELDS:
                        connection.execute(
                            f"UPDATE tickets SET {change.field}=? WHERE ticket_id=?",
                            (change.new, payload.ticket_id),
                        )
            elif isinstance(payload, TicketCommentedPayload):
                insert(
                    connection,
                    "comments",
                    ("ticket_id", "actor", "body", "time"),
                    [
                        (
                            payload.ticket_id,
                            payload.actor,
                            payload.body,
                            int(event.time),
                        )
                    ],
                )

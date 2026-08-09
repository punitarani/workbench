"""Project ticket events into the matter-tracker database.

Ticket state folds in memory (validated on every fold), so each ticket row
lands once, already in its final state; history and comments append.
"""

import sqlite3
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.tools.matters.tables import (
    COMMENTS,
    HISTORY,
    TICKETS,
    Comment,
    HistoryEntry,
    Ticket,
)

FOLDED_FIELDS = ("title", "description", "assignee", "status", "priority")


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    tickets: dict[str, Ticket] = {}
    history: list[HistoryEntry] = []
    comments: list[Comment] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, TicketCreatedPayload):
            tickets[payload.ticket_id] = Ticket(
                ticket_id=payload.ticket_id,
                title=payload.title,
                description=payload.description,
                requester=payload.requester,
                assignee=payload.assignee,
                status=payload.status,
                priority=payload.priority,
                ticket_type=payload.ticket_type,
                created_time=int(event.time),
            )
        elif isinstance(payload, TicketUpdatedPayload):
            for change in payload.changes:
                history.append(
                    HistoryEntry(
                        ticket_id=payload.ticket_id,
                        actor=payload.actor,
                        field=change.field,
                        old_value=change.old,
                        new_value=change.new,
                        time=int(event.time),
                    )
                )
                if change.field in FOLDED_FIELDS:
                    folded = tickets[payload.ticket_id]
                    tickets[payload.ticket_id] = Ticket.model_validate(
                        {**folded.model_dump(), change.field: change.new}
                    )
        elif isinstance(payload, TicketCommentedPayload):
            comments.append(
                Comment(
                    ticket_id=payload.ticket_id,
                    actor=payload.actor,
                    body=payload.body,
                    time=int(event.time),
                )
            )
    TICKETS.insert(connection, tickets.values())
    HISTORY.insert(connection, history)
    COMMENTS.insert(connection, comments)

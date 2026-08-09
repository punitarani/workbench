"""Project ticket, time, and org events into the Clio database.

Ticket state folds in memory like the matter tracker (validated on every
fold); Clio's matter numbers and display numbers materialize after the
fold, once every organization and person record has been seen.
"""

import sqlite3
from collections.abc import Mapping, Sequence

from pydantic import BaseModel

from workbench.core.events import Event
from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)
from workbench.core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.tools.clio.tables import (
    ACTIVITIES,
    MATTER_HISTORY,
    MATTERS,
    NOTES,
    ORGANIZATIONS,
    Activity,
    Matter,
    MatterHistoryEntry,
    Note,
    Organization,
    clio_status,
)

FOLDED_FIELDS = ("title", "description", "assignee", "status", "priority")


class _TicketState(BaseModel):
    title: str
    description: str
    requester: str
    assignee: str | None
    status: str
    priority: str
    ticket_type: str
    client_ref: str | None
    open_time: int


def _display_number(
    number: int,
    state: _TicketState,
    org_names: Mapping[str, str],
    person_names: Mapping[str, str],
) -> str:
    if state.client_ref is not None:
        client = org_names[state.client_ref].replace(" ", "")
    else:
        client = person_names[state.requester].split()[-1]
    return f"{number:05d}-{client}"


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    tickets: dict[str, _TicketState] = {}
    organizations: dict[str, Organization] = {}
    person_names: dict[str, str] = {}
    history: list[MatterHistoryEntry] = []
    notes: list[Note] = []
    activities: list[Activity] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, PersonRecordPayload):
            person_names[payload.person_id] = payload.name
        elif isinstance(payload, OrganizationRecordPayload):
            organizations[payload.org_id] = Organization(
                org_id=payload.org_id,
                name=payload.name,
                category=payload.category,
            )
        elif isinstance(payload, TicketCreatedPayload):
            tickets[payload.ticket_id] = _TicketState(
                title=payload.title,
                description=payload.description,
                requester=payload.requester,
                assignee=payload.assignee,
                status=payload.status,
                priority=payload.priority,
                ticket_type=payload.ticket_type,
                client_ref=payload.client_ref,
                open_time=int(event.time),
            )
        elif isinstance(payload, TicketUpdatedPayload):
            for change in payload.changes:
                history.append(
                    MatterHistoryEntry(
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
                    tickets[payload.ticket_id] = _TicketState.model_validate(
                        {**folded.model_dump(), change.field: change.new}
                    )
        elif isinstance(payload, TicketCommentedPayload):
            notes.append(
                Note(
                    ticket_id=payload.ticket_id,
                    author=payload.actor,
                    detail=payload.body,
                    time=int(event.time),
                )
            )
        elif isinstance(payload, TimeLoggedPayload):
            activities.append(
                Activity(
                    ticket_id=payload.ticket_id,
                    person=payload.person_id,
                    quantity_seconds=payload.minutes * 60,
                    note=payload.note,
                    time=int(event.time),
                )
            )
    org_names = {org_id: org.name for org_id, org in organizations.items()}
    matters = [
        Matter(
            ticket_id=ticket_id,
            matter_number=number,
            display_number=_display_number(number, state, org_names, person_names),
            description=state.title,
            detail=state.description,
            status=clio_status(state.status),
            practice_area=state.ticket_type,
            client_org=state.client_ref,
            responsible_person=state.assignee,
            originating_person=state.requester,
            open_time=state.open_time,
        )
        for number, (ticket_id, state) in enumerate(tickets.items(), 1)
    ]
    MATTERS.insert(connection, matters)
    MATTER_HISTORY.insert(connection, history)
    NOTES.insert(connection, notes)
    ACTIVITIES.insert(connection, activities)
    ORGANIZATIONS.insert(connection, organizations.values())

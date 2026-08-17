"""The world log, read as plain facts, with nothing borrowed from the tools.

This module exists to disagree. Every reference solver reads the
materialized ``state/*.db``, which the projections under
``workbench.tools.*.project`` wrote; an oracle derived that way and a
grader checked that way share a code path, so a mistake anywhere along it
is invisible — it simply becomes the truth.

So this reads ``world.jsonl`` directly and re-derives the same quantities
by hand. It imports nothing from ``workbench.tools`` or
``workbench.environment`` on purpose: the projection rules are restated
here from the events, and where the restatement and the projection
disagree, one of them is wrong and a person has to look.

Two defects this would have caught the day they were introduced, both of
which instead survived into paid rollouts:

* the firm's hours summed 817.27 from the rounded rows and 817.23 from the
  entries, and the task named neither;
* two documents shared the title "Single Audit Playbook", so a grader keyed
  on the title alone scored a perfect answer 0.976 and called it the
  model's error.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Person:
    person_id: str
    name: str
    email_address: str
    affiliation: str
    title: str = ""
    department: str = ""


@dataclass(frozen=True)
class Activity:
    person_id: str
    ticket_id: str
    minutes: int
    rate_cents: int | None
    billable: bool
    # What the entry says it was for. The only place the *subject* of the
    # work is written down, and so the only way to tell whether the
    # engagement it was booked to is the one it belongs to.
    note: str = ""
    # When the entry was logged. Clio dates an activity and never stamps an
    # hour on it, so anything graded off this must be counted in whole days
    # -- an answer keyed to the *moment* is one no agent could recover.
    at: int = 0


@dataclass
class Ticket:
    ticket_id: str
    number: int
    title: str
    requester: str
    assignee: str | None
    client_ref: str | None
    opened_at: int
    status: str
    # Every field change in the order the log recorded it, as
    # (time, actor, field, old, new). A ticket's *current* status is the
    # last status change, or the status it was created with.
    changes: list[tuple[int, str, str, str, str]] = field(default_factory=list)


@dataclass
class Document:
    document_id: str
    title: str
    path: str
    created_at: int
    # (revision, author) in log order; revision 1 is the creation.
    chain: list[tuple[int, str]] = field(default_factory=list)

    @property
    def workspace(self) -> str:
        """Top-level path segment, or the firm's own when there is none.

        Restated from the record rather than imported: a path of
        ``brief.docx`` has no directory, and naming a workspace after the
        file would invent one that no tool ever serves.

        Folded, because the file room is not case-sensitive and this world's
        authors wrote both ``Engagements/`` and ``engagements/``.
        """

        parts = [part for part in self.path.split("/") if part]
        return parts[0].casefold() if len(parts) > 1 else "firm"


@dataclass(frozen=True)
class Email:
    message_id: str
    thread_id: str
    in_reply_to: str | None
    sender: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    subject: str
    body: str
    time: int
    attachments: tuple[str, ...]

    @property
    def recipients(self) -> frozenset[str]:
        return frozenset(self.to) | frozenset(self.cc)


@dataclass(frozen=True)
class Chat:
    conversation_id: str
    sender: str
    body: str
    time: int


@dataclass
class WorldFacts:
    people: dict[str, Person] = field(default_factory=dict)
    orgs: dict[str, str] = field(default_factory=dict)
    tickets: dict[str, Ticket] = field(default_factory=dict)
    activities: list[Activity] = field(default_factory=list)
    documents: dict[str, Document] = field(default_factory=dict)
    emails: dict[str, Email] = field(default_factory=dict)
    chats: list[Chat] = field(default_factory=list)
    # conversation_id -> the channel's name, which is what Slack serves and
    # what a task may therefore ask an answer to be spelled in.
    channels: dict[str, str] = field(default_factory=dict)
    # The instant `time: 0` refers to, as the run recorded it. Every
    # projected database carries the same string in its `meta` table, so
    # reading it here keeps a caller from hardcoding a date that is only
    # true of one world.
    epoch: str = ""

    # --- derived views, each restating a rule the tools also implement ---

    def name(self, person_id: str) -> str:
        person = self.people.get(person_id)
        return person.name if person else person_id

    @property
    def internal(self) -> frozenset[str]:
        return frozenset(
            p.person_id for p in self.people.values() if p.affiliation == "internal"
        )

    def display_number(self, ticket_id: str) -> str:
        """``00005-Mensah``: the number, then the client or the requester.

        Restated from ``clio``'s own vocabulary because a task keyed on
        ``tkt-000005`` grades whether the agent guessed an internal id that
        no tool emits, and one model scored 1.000 and 0.273 on two rollouts
        of exactly that coin toss.
        """

        ticket = self.tickets[ticket_id]
        if ticket.client_ref is not None:
            client = self.orgs.get(ticket.client_ref, ticket.client_ref)
            return f"{ticket.number:05d}-{client.replace(' ', '')}"
        return f"{ticket.number:05d}-{self.name(ticket.requester).split()[-1]}"

    def current_status(self, ticket_id: str) -> str:
        ticket = self.tickets[ticket_id]
        for _time, _actor, changed, _old, new in reversed(ticket.changes):
            if changed == "status":
                return new
        return ticket.status

    def threads(self) -> dict[str, list[Email]]:
        out: dict[str, list[Email]] = defaultdict(list)
        for email in self.emails.values():
            out[email.thread_id].append(email)
        for messages in out.values():
            messages.sort(key=lambda m: (m.time, m.message_id))
        return dict(out)

    def attached_documents(self) -> dict[str, set[str]]:
        """document_id -> the message ids that carried it."""

        out: dict[str, set[str]] = defaultdict(set)
        for email in self.emails.values():
            for document_id in email.attachments:
                out[document_id].add(email.message_id)
        return dict(out)


def _int(value: Any, default: int = 0) -> int:
    return int(value) if isinstance(value, (int, float)) else default


def load_world(path: Path) -> WorldFacts:
    """Fold ``world.jsonl`` into facts, in log order.

    Order matters and is the log's, not a sort: a ticket's status is the
    last change recorded, and a document's chain is the sequence of
    revisions as they happened.
    """

    facts = WorldFacts()
    ticket_number = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            event = json.loads(line)
            payload = event.get("payload") or {}
            tag, when = event.get("tag"), _int(event.get("time"))
            match tag:
                case "sim.run.started":
                    facts.epoch = payload.get("epoch", "")
                case "person.record":
                    facts.people[payload["person_id"]] = Person(
                        person_id=payload["person_id"],
                        name=payload["name"],
                        email_address=payload.get("email_address", ""),
                        affiliation=payload.get("affiliation", "internal"),
                        title=payload.get("title", ""),
                        department=payload.get("department", ""),
                    )
                case "org.record":
                    facts.orgs[payload["org_id"]] = payload["name"]
                case "ticket.created":
                    ticket_number += 1
                    facts.tickets[payload["ticket_id"]] = Ticket(
                        ticket_id=payload["ticket_id"],
                        number=ticket_number,
                        title=payload.get("title", ""),
                        requester=payload.get("requester", ""),
                        assignee=payload.get("assignee"),
                        client_ref=payload.get("client_ref"),
                        opened_at=when,
                        status=payload.get("status", ""),
                    )
                case "ticket.updated":
                    ticket = facts.tickets.get(payload["ticket_id"])
                    if ticket is None:
                        continue
                    for change in payload.get("changes", []):
                        ticket.changes.append(
                            (
                                when,
                                payload.get("actor", ""),
                                change.get("field", ""),
                                str(change.get("old", "")),
                                str(change.get("new", "")),
                            )
                        )
                case "work.time.logged":
                    facts.activities.append(
                        Activity(
                            person_id=payload["person_id"],
                            ticket_id=payload["ticket_id"],
                            minutes=_int(payload.get("minutes")),
                            rate_cents=payload.get("rate_cents"),
                            billable=bool(payload.get("billable")),
                            note=payload.get("note") or "",
                            at=when,
                        )
                    )
                case "document.created":
                    facts.documents[payload["document_id"]] = Document(
                        document_id=payload["document_id"],
                        title=payload.get("title", ""),
                        path=payload.get("path", ""),
                        created_at=when,
                        chain=[(1, payload.get("author", ""))],
                    )
                case "document.revised":
                    document = facts.documents.get(payload["document_id"])
                    if document is not None:
                        document.chain.append(
                            (
                                _int(payload.get("revision"), 0),
                                payload.get("author", ""),
                            )
                        )
                case "email.message":
                    facts.emails[payload["message_id"]] = Email(
                        message_id=payload["message_id"],
                        thread_id=payload["thread_id"],
                        in_reply_to=payload.get("in_reply_to"),
                        sender=payload["sender"],
                        to=tuple(payload.get("to", ())),
                        cc=tuple(payload.get("cc", ())),
                        subject=payload.get("subject", ""),
                        body=payload.get("body", ""),
                        time=when,
                        attachments=tuple(
                            a["document_id"]
                            for a in payload.get("attachments", ())
                            if a.get("document_id")
                        ),
                    )
                case "chat.conversation.created":
                    facts.channels[payload["conversation_id"]] = (
                        payload.get("name") or payload["conversation_id"]
                    )
                case "chat.message":
                    facts.chats.append(
                        Chat(
                            conversation_id=payload.get("conversation_id", ""),
                            sender=payload.get("sender", ""),
                            body=payload.get("body", ""),
                            time=when,
                        )
                    )
    return facts

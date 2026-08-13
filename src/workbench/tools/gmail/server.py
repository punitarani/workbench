"""Gmail-shaped read tools over the gmail database.

The surface mirrors Google's official Gmail MCP server: ``search_threads``,
``get_thread``, ``get_message``, and ``list_labels``, returning flattened
Message objects (id, snippet, subject, sender, toRecipients, ccRecipients,
date, plaintextBody, attachmentIds, attachments, labelIds). Sender and
recipients render as ``Name <email>`` resolved from the people table; ids
stay in the database for coherence.

``search_threads`` implements a deterministic subset of Gmail query syntax:
bare terms AND together as case-insensitive substrings over subject, body,
and participant names, addresses, and ids; quoted phrases; ``from:``/
``to:``/``cc:`` matching person id, name, or email address; ``subject:``;
``label:``; ``has:attachment``; ``after:``/``before:`` with YYYY/MM/DD
dates (after is inclusive of the day, before exclusive); and ``-term``
negation. Tokens with unknown operators are treated as bare terms.

Mailbox scoping: the optional ``WORKBENCH_SEAT`` environment variable names
the person_id whose mailbox this server presents; it is read at call time,
never at import time. When set, the tools surface only messages where that
person is the sender or a recipient, and ``labelIds`` derive per seat:
INBOX when the seat received the message, SENT when the seat sent it, and
never UNREAD (all mail is read). When unset the server reads org-wide and
``labelIds`` is always ``[]``.

Dates render as ISO-8601 strings: the world log's epoch (read from the
shared meta table at call time) plus the message's simulated time in
seconds.
"""

import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
from workbench.tools.gmail.tables import (
    ATTACHMENTS,
    MESSAGES,
    RECIPIENTS,
    Attachment,
    Message,
)

_MAX_PAGE_SIZE = 50
_OPERATORS = frozenset({"from", "to", "cc", "subject", "label", "has"})
_DATE_OPERATORS = frozenset({"after", "before"})
_TOKEN = re.compile(r'-?\w+:"[^"]*"|-?"[^"]*"|\S+')


@dataclass(frozen=True, slots=True)
class _Term:
    op: str | None
    value: str
    negated: bool


@dataclass(frozen=True, slots=True)
class _Mail:
    message: Message
    to: tuple[str, ...]
    cc: tuple[str, ...]
    attachments: tuple[Attachment, ...]


def _parse_date(value: str) -> datetime | None:
    parts = value.split("/")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        return None
    year, month, day = (int(part) for part in parts)
    try:
        return datetime(year, month, day, tzinfo=UTC)
    except ValueError:
        return None


def _parse_query(query: str) -> list[_Term]:
    terms: list[_Term] = []
    for token in _TOKEN.findall(query):
        negated = token.startswith("-")
        body = token.removeprefix("-")
        op: str | None = None
        value = body
        if body.startswith('"'):
            value = body.strip('"')
        elif ":" in body:
            head, _, tail = body.partition(":")
            known = head.lower() in _OPERATORS or head.lower() in _DATE_OPERATORS
            if known and tail:
                op, value = head.lower(), tail.strip('"')
        if op == "has" and value.lower() != "attachment":
            op, value = None, body
        if op in _DATE_OPERATORS and _parse_date(value) is None:
            op, value = None, body
        if value:
            terms.append(_Term(op=op, value=value, negated=negated))
    return terms


def _load(
    connection: sqlite3.Connection,
) -> tuple[list[_Mail], dict[str, Person], datetime]:
    epoch = read_epoch(connection)
    people = {p.person_id: p for p in PEOPLE_TABLE.select(connection)}
    recipients = RECIPIENTS.select(connection)
    attachments = ATTACHMENTS.select(connection)
    messages = sorted(MESSAGES.select(connection), key=lambda m: (m.time, m.message_id))
    mailbox = [
        _Mail(
            message=message,
            to=tuple(
                r.person_id
                for r in recipients
                if r.message_id == message.message_id and r.kind == "to"
            ),
            cc=tuple(
                r.person_id
                for r in recipients
                if r.message_id == message.message_id and r.kind == "cc"
            ),
            attachments=tuple(
                a for a in attachments if a.message_id == message.message_id
            ),
        )
        for message in messages
    ]
    return mailbox, people, epoch


def _visible(mail: _Mail, person: str | None) -> bool:
    if person is None:
        return True
    return person == mail.message.sender or person in mail.to or person in mail.cc


def _labels(mail: _Mail, person: str | None) -> list[str]:
    if person is None:
        return []
    labels = []
    if person in mail.to or person in mail.cc:
        labels.append("INBOX")
    if person == mail.message.sender:
        labels.append("SENT")
    return labels


def _display(person_id: str, people: dict[str, Person]) -> str:
    person = people[person_id]
    return f"{person.name} <{person.email_address}>"


def _person_matches(person_id: str, needle: str, people: dict[str, Person]) -> bool:
    person = people[person_id]
    return any(
        needle in field.lower()
        for field in (person_id, person.name, person.email_address)
    )


def _matches(
    term: _Term,
    mail: _Mail,
    people: dict[str, Person],
    person: str | None,
    epoch: datetime,
) -> bool:
    message = mail.message
    needle = term.value.lower()
    if term.op is None:
        participants = (message.sender, *mail.to, *mail.cc)
        haystack = " ".join(
            (
                message.subject,
                message.body,
                *(people[p].name for p in participants),
                *(people[p].email_address for p in participants),
                *participants,
            )
        ).lower()
        hit = needle in haystack
    elif term.op == "from":
        hit = _person_matches(message.sender, needle, people)
    elif term.op == "to":
        hit = any(_person_matches(p, needle, people) for p in mail.to)
    elif term.op == "cc":
        hit = any(_person_matches(p, needle, people) for p in mail.cc)
    elif term.op == "subject":
        hit = needle in message.subject.lower()
    elif term.op == "label":
        hit = term.value.upper() in _labels(mail, person)
    elif term.op == "has":
        hit = bool(mail.attachments)
    else:
        parsed = _parse_date(term.value)
        assert parsed is not None  # parsed terms carry valid dates
        # Query dates mean calendar days in the record's own timezone.
        boundary = parsed.replace(tzinfo=epoch.tzinfo)
        moment = epoch + timedelta(seconds=message.time)
        hit = moment >= boundary if term.op == "after" else moment < boundary
    return hit != term.negated


def _message_json(
    mail: _Mail, people: dict[str, Person], person: str | None, epoch: datetime
) -> dict:
    message = mail.message
    return {
        "id": message.message_id,
        "snippet": message.snippet,
        "subject": message.subject,
        "sender": _display(message.sender, people),
        "toRecipients": [_display(p, people) for p in mail.to],
        "ccRecipients": [_display(p, people) for p in mail.cc],
        "date": (epoch + timedelta(seconds=message.time)).isoformat(),
        "plaintextBody": message.body,
        "attachmentIds": [a.document_id for a in mail.attachments],
        "attachments": [
            {"id": a.document_id, "mimeType": a.media_type, "filename": a.filename}
            for a in mail.attachments
        ],
        "labelIds": _labels(mail, person),
    }


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def search_threads(
        query: str = "", pageSize: int = 20, pageToken: str | None = None
    ) -> dict:
        """Search mail with Gmail query syntax; returns a page of threads."""
        person = seat()
        terms = _parse_query(query)
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
        threads: dict[str, list[_Mail]] = {}
        for mail in mailbox:
            if _visible(mail, person):
                threads.setdefault(mail.message.thread_id, []).append(mail)
        matched = sorted(
            (
                (thread_id, mails)
                for thread_id, mails in threads.items()
                if any(
                    all(_matches(term, mail, people, person, epoch) for term in terms)
                    for mail in mails
                )
            ),
            key=lambda item: (item[1][0].message.time, item[0]),
        )
        size = min(max(pageSize, 1), _MAX_PAGE_SIZE)
        offset = max(int(pageToken), 0) if pageToken else 0
        exhausted = offset + size >= len(matched)
        return {
            "threads": [
                {
                    "id": thread_id,
                    "messages": [
                        _message_json(m, people, person, epoch) for m in mails
                    ],
                }
                for thread_id, mails in matched[offset : offset + size]
            ],
            "nextPageToken": None if exhausted else str(offset + size),
            "resultCountEstimate": str(len(matched)),
        }

    @server.tool()
    def get_thread(threadId: str) -> dict:
        """Read one mail thread; messages arrive oldest first."""
        person = seat()
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
        mails = [
            mail
            for mail in mailbox
            if mail.message.thread_id == threadId and _visible(mail, person)
        ]
        if not mails:
            raise UnknownRefError(f"no thread {threadId}")
        return {
            "id": threadId,
            "messages": [_message_json(m, people, person, epoch) for m in mails],
        }

    @server.tool()
    def get_message(messageId: str) -> dict:
        """Read one mail message by id."""
        person = seat()
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
        for mail in mailbox:
            if mail.message.message_id == messageId and _visible(mail, person):
                return _message_json(mail, people, person, epoch)
        raise UnknownRefError(f"no message {messageId}")

    @server.tool()
    def list_labels() -> dict:
        """List the user's labels; system labels are not listed."""
        return {"labels": []}

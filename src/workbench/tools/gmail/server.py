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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from workbench.tools.db import Table, connect_readonly, connect_readwrite
from workbench.tools.framework import (
    PEOPLE_TABLE,
    Person,
    UnknownRefError,
    read_epoch,
    seat,
)
from workbench.tools.gmail.tables import (
    ATTACHMENTS,
    DRAFTS,
    LABEL_APPLICATIONS,
    MESSAGES,
    RECIPIENTS,
    USER_LABELS,
    Attachment,
    Draft,
    LabelApplication,
    Message,
    UserLabel,
)

_MAX_PAGE_SIZE = 50
_MAX_LABEL_PAGE = 250
# Google's MessageFormat enum, verbatim.
type MessageFormat = Literal[
    "MESSAGE_FORMAT_UNSPECIFIED", "MINIMAL", "FULL_CONTENT", "METADATA_ONLY"
]
# Google's ThreadView enum, verbatim.
type ThreadView = Literal[
    "THREAD_VIEW_UNSPECIFIED", "THREAD_VIEW_MINIMAL", "THREAD_VIEW_METADATA_ONLY"
]
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


def _labels(
    mail: _Mail, person: str | None, applied: Mapping[str, list[str]] | None = None
) -> list[str]:
    """System labels the seat implies, plus anything the agent applied.

    TRASH and SPAM are agent-applied like any other label, which is what
    makes ``includeTrash`` and the trash/spam tools agree with each other.
    """

    labels = []
    if person is not None:
        if person in mail.to or person in mail.cc:
            labels.append("INBOX")
        if person == mail.message.sender:
            labels.append("SENT")
    if applied:
        labels.extend(applied.get(mail.message.message_id, ()))
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


def _html_body(body: str) -> str:
    """The HTML alternative Gmail returns beside the plaintext one.

    The record stores what people wrote, which is plain text; Gmail always
    carries both, so the paragraph-wrapped form is derived here rather than
    stored twice.
    """

    paragraphs = [
        para.strip().replace("\n", "<br>")
        for para in body.split("\n\n")
        if para.strip()
    ]
    return "".join(f"<p>{para}</p>" for para in paragraphs)


def _message_json(
    mail: _Mail,
    people: dict[str, Person],
    person: str | None,
    epoch: datetime,
    *,
    message_format: str = "FULL_CONTENT",
    applied: Mapping[str, list[str]] | None = None,
) -> dict:
    """One Message object in the official server's shape.

    ``messageFormat`` follows Google's enum: METADATA_ONLY drops the
    subject, snippet, body, and attachment filenames; MINIMAL keeps the
    headers and snippet but no body; FULL_CONTENT is everything.
    """

    message = mail.message
    metadata_only = message_format == "METADATA_ONLY"
    full = message_format in ("FULL_CONTENT", "MESSAGE_FORMAT_UNSPECIFIED")
    # Key order follows the official Message object so a consumer diffing
    # our JSON against Google's sees the same field sequence.
    payload: dict = {"id": message.message_id}
    if not metadata_only:
        payload["snippet"] = message.snippet
        payload["subject"] = message.subject
    payload |= {
        "sender": _display(message.sender, people),
        "toRecipients": [_display(p, people) for p in mail.to],
        "ccRecipients": [_display(p, people) for p in mail.cc],
        "date": (epoch + timedelta(seconds=message.time)).isoformat(),
    }
    if full:
        payload["plaintextBody"] = message.body
        payload["htmlBody"] = _html_body(message.body)
    if not metadata_only:
        payload["attachmentIds"] = [a.document_id for a in mail.attachments]
        payload["attachments"] = [
            {"id": a.document_id, "mimeType": a.media_type, "filename": a.filename}
            for a in mail.attachments
        ]
    else:
        payload["attachmentIds"] = [a.document_id for a in mail.attachments]
        payload["attachments"] = [
            {"id": a.document_id, "mimeType": a.media_type} for a in mail.attachments
        ]
    payload["labelIds"] = _labels(mail, person, applied)
    return payload


def _applied_labels(connection: sqlite3.Connection) -> dict[str, list[str]]:
    applied: dict[str, list[str]] = {}
    for row in LABEL_APPLICATIONS.select(connection):
        applied.setdefault(row.message_id, []).append(row.label_id)
    return applied


def _threads_by_message(connection: sqlite3.Connection) -> dict[str, str]:
    return {m.message_id: m.thread_id for m in MESSAGES.select(connection)}


def _now(connection: sqlite3.Connection) -> int:
    """The world's head time — a rollout's "now" is where the record stops."""

    messages = MESSAGES.select(connection)
    return max((m.time for m in messages), default=0)


def _next_id(
    connection: sqlite3.Connection, table: Table, name: str, prefix: str
) -> str:
    existing = len(table.select(connection))
    return (
        f"{prefix}_{existing + 1:06d}"
        if prefix == "Label"
        else (f"{prefix}-{existing + 1:06d}")
    )


def _draft_json(draft: Draft, epoch: datetime) -> dict:
    return {
        "id": draft.draft_id,
        "subject": draft.subject,
        "threadId": draft.thread_id,
        "toRecipients": [a for a in draft.to_addresses.split(",") if a],
        "ccRecipients": [a for a in draft.cc_addresses.split(",") if a],
        "bccRecipients": [a for a in draft.bcc_addresses.split(",") if a],
        "plaintextBody": draft.body,
        "htmlBody": draft.html_body or _html_body(draft.body),
        "date": (epoch + timedelta(seconds=draft.time)).isoformat(),
    }


def _thread_members(db_path: Path, thread_id: str) -> list[str]:
    with connect_readonly(db_path) as connection:
        members = [
            m.message_id
            for m in MESSAGES.select(connection, where={"thread_id": thread_id})
        ]
    if not members:
        raise UnknownRefError(f"no thread {thread_id}")
    return members


def _apply_labels(
    db_path: Path, message_ids: Sequence[str], label_ids: Sequence[str], *, add: bool
) -> None:
    """Add or remove label applications, idempotently.

    Both official label tools are marked idempotent, so applying a label
    twice is a no-op rather than a duplicate row.
    """

    with connect_readwrite(db_path) as connection:
        known = {m.message_id for m in MESSAGES.select(connection)}
        missing = [mid for mid in message_ids if mid not in known]
        if missing:
            raise UnknownRefError(f"no message {missing[0]}")
        current = {
            (row.message_id, row.label_id)
            for row in LABEL_APPLICATIONS.select(connection)
        }
        if add:
            fresh = [
                LabelApplication(label_id=label, message_id=message)
                for message in message_ids
                for label in label_ids
                if (message, label) not in current
            ]
            if fresh:
                LABEL_APPLICATIONS.insert(connection, fresh)
        else:
            connection.executemany(
                "DELETE FROM label_applications WHERE message_id=? AND label_id=?",
                [(message, label) for message in message_ids for label in label_ids],
            )
        connection.commit()


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def search_threads(
        query: str = "",
        pageSize: int = 20,
        pageToken: str | None = None,
        includeTrash: bool = False,
        view: ThreadView = "THREAD_VIEW_MINIMAL",
    ) -> dict:
        """Search mail with Gmail query syntax; returns a page of threads."""
        person = seat()
        terms = _parse_query(query)
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
            applied = _applied_labels(connection)
        if not includeTrash:
            mailbox = [
                mail
                for mail in mailbox
                if "TRASH" not in applied.get(mail.message.message_id, ())
            ]
        message_format = (
            "METADATA_ONLY" if view == "THREAD_VIEW_METADATA_ONLY" else "MINIMAL"
        )
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
                        _message_json(
                            m,
                            people,
                            person,
                            epoch,
                            message_format=message_format,
                            applied=applied,
                        )
                        for m in mails
                    ],
                }
                for thread_id, mails in matched[offset : offset + size]
            ],
            "nextPageToken": None if exhausted else str(offset + size),
            "resultCountEstimate": str(len(matched)),
        }

    @server.tool()
    def get_thread(
        threadId: str, messageFormat: MessageFormat = "FULL_CONTENT"
    ) -> dict:
        """Read one mail thread; messages arrive oldest first."""
        person = seat()
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
            applied = _applied_labels(connection)
        mails = [
            mail
            for mail in mailbox
            if mail.message.thread_id == threadId and _visible(mail, person)
        ]
        if not mails:
            raise UnknownRefError(f"no thread {threadId}")
        return {
            "id": threadId,
            "messages": [
                _message_json(
                    m,
                    people,
                    person,
                    epoch,
                    message_format=messageFormat,
                    applied=applied,
                )
                for m in mails
            ],
        }

    @server.tool()
    def get_message(
        messageId: str, messageFormat: MessageFormat = "FULL_CONTENT"
    ) -> dict:
        """Read one mail message by id."""
        person = seat()
        with connect_readonly(db_path) as connection:
            mailbox, people, epoch = _load(connection)
            applied = _applied_labels(connection)
        for mail in mailbox:
            if mail.message.message_id == messageId and _visible(mail, person):
                return _message_json(
                    mail,
                    people,
                    person,
                    epoch,
                    message_format=messageFormat,
                    applied=applied,
                )
        raise UnknownRefError(f"no message {messageId}")

    @server.tool()
    def list_labels(pageSize: int = 100, pageToken: str | None = None) -> dict:
        """List the user's labels. System labels (INBOX, SENT, TRASH, SPAM,
        STARRED, UNREAD, IMPORTANT, DRAFT) are addressed by their well-known
        ids and are not listed."""
        with connect_readonly(db_path) as connection:
            labels = USER_LABELS.select(connection, order_by="label_id")
            applied = _applied_labels(connection)
            threads = _threads_by_message(connection)
        # Gmail reports label counts by *thread*, not by message.
        thread_counts: dict[str, set[str]] = {}
        for message_id, names in applied.items():
            for name in names:
                thread_counts.setdefault(name, set()).add(
                    threads.get(message_id, message_id)
                )
        size = min(max(pageSize, 1), _MAX_LABEL_PAGE)
        offset = max(int(pageToken), 0) if pageToken else 0
        page = labels[offset : offset + size]
        return {
            "labels": [
                {
                    "labelId": label.label_id,
                    "name": label.display_name,
                    "color": {
                        "textColor": label.text_color,
                        "backgroundColor": label.background_color,
                    },
                    "threadsTotal": len(thread_counts.get(label.label_id, ())),
                    "threadsUnread": 0,
                }
                for label in page
            ],
            "nextPageToken": (
                None if offset + size >= len(labels) else str(offset + size)
            ),
        }

    @server.tool()
    def list_drafts(
        pageSize: int = 20,
        pageToken: str | None = None,
        query: str = "",
        view: str = "",
    ) -> dict:
        """List unsent drafts, newest first."""
        del view
        with connect_readonly(db_path) as connection:
            epoch = read_epoch(connection)
            drafts = sorted(
                DRAFTS.select(connection), key=lambda d: (-d.time, d.draft_id)
            )
        needle = query.lower().strip()
        if needle:
            drafts = [
                draft
                for draft in drafts
                if needle in draft.subject.lower() or needle in draft.body.lower()
            ]
        size = min(max(pageSize, 1), _MAX_PAGE_SIZE)
        offset = max(int(pageToken), 0) if pageToken else 0
        page = drafts[offset : offset + size]
        return {
            "drafts": [_draft_json(draft, epoch) for draft in page],
            "nextPageToken": (
                None if offset + size >= len(drafts) else str(offset + size)
            ),
        }

    @server.tool()
    def create_draft(
        to: list[str] | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
        subject: str = "",
        body: str = "",
        htmlBody: str = "",
        replyToMessageId: str | None = None,
    ) -> dict:
        """Compose an unsent draft. There is no send tool — a person opens
        the draft and sends it, exactly as on the official Gmail MCP server."""
        with connect_readwrite(db_path) as connection:
            epoch = read_epoch(connection)
            thread_id = None
            if replyToMessageId is not None:
                rows = MESSAGES.select(
                    connection, where={"message_id": replyToMessageId}
                )
                if not rows:
                    raise UnknownRefError(f"no message {replyToMessageId}")
                thread_id = rows[0].thread_id
            draft = Draft(
                draft_id=_next_id(connection, DRAFTS, "drafts", "draft"),
                thread_id=thread_id,
                subject=subject,
                body=body,
                html_body=htmlBody,
                to_addresses=",".join(to or ()),
                cc_addresses=",".join(cc or ()),
                bcc_addresses=",".join(bcc or ()),
                reply_to_message_id=replyToMessageId,
                time=_now(connection),
            )
            DRAFTS.insert(connection, [draft])
            connection.commit()
        return _draft_json(draft, epoch)

    @server.tool()
    def create_label(displayName: str, color: dict | None = None) -> dict:
        """Create a user label."""
        palette = color or {}
        with connect_readwrite(db_path) as connection:
            label = UserLabel(
                label_id=_next_id(connection, USER_LABELS, "user_labels", "Label"),
                display_name=displayName,
                text_color=str(palette.get("textColor", "#000000")),
                background_color=str(palette.get("backgroundColor", "#ffffff")),
            )
            USER_LABELS.insert(connection, [label])
            connection.commit()
        return {
            "labelId": label.label_id,
            "name": label.display_name,
            "color": {
                "textColor": label.text_color,
                "backgroundColor": label.background_color,
            },
            "threadsTotal": 0,
            "threadsUnread": 0,
        }

    @server.tool()
    def label_message(messageId: str, labelIds: list[str]) -> dict:
        """Apply labels to one message. Labels are addressed by id."""
        _apply_labels(db_path, [messageId], labelIds, add=True)
        return {}

    @server.tool()
    def unlabel_message(messageId: str, labelIds: list[str]) -> dict:
        """Remove labels from one message."""
        _apply_labels(db_path, [messageId], labelIds, add=False)
        return {}

    @server.tool()
    def label_thread(threadId: str, labelIds: list[str]) -> dict:
        """Apply labels to every message in a thread."""
        _apply_labels(db_path, _thread_members(db_path, threadId), labelIds, add=True)
        return {}

    @server.tool()
    def unlabel_thread(threadId: str, labelIds: list[str]) -> dict:
        """Remove labels from every message in a thread."""
        _apply_labels(db_path, _thread_members(db_path, threadId), labelIds, add=False)
        return {}

    @server.tool()
    def trash_message(messageId: str) -> dict:
        """Move a message to Trash."""
        _apply_labels(db_path, [messageId], ["TRASH"], add=True)
        return {}

    @server.tool()
    def untrash_message(messageId: str) -> dict:
        """Remove a message from Trash."""
        _apply_labels(db_path, [messageId], ["TRASH"], add=False)
        return {}

    @server.tool()
    def trash_thread(threadId: str) -> dict:
        """Move every message in a thread to Trash."""
        _apply_labels(db_path, _thread_members(db_path, threadId), ["TRASH"], add=True)
        return {}

    @server.tool()
    def untrash_thread(threadId: str) -> dict:
        """Remove every message in a thread from Trash."""
        _apply_labels(db_path, _thread_members(db_path, threadId), ["TRASH"], add=False)
        return {}

    @server.tool()
    def mark_message_spam(messageId: str) -> dict:
        """Mark a message as spam."""
        _apply_labels(db_path, [messageId], ["SPAM"], add=True)
        return {}

    @server.tool()
    def unmark_message_spam(messageId: str) -> dict:
        """Unmark a message as spam."""
        _apply_labels(db_path, [messageId], ["SPAM"], add=False)
        return {}

    @server.tool()
    def mark_thread_spam(threadId: str) -> dict:
        """Mark every message in a thread as spam."""
        _apply_labels(db_path, _thread_members(db_path, threadId), ["SPAM"], add=True)
        return {}

    @server.tool()
    def unmark_thread_spam(threadId: str) -> dict:
        """Unmark every message in a thread as spam."""
        _apply_labels(db_path, _thread_members(db_path, threadId), ["SPAM"], add=False)
        return {}

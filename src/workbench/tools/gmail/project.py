"""Project email events into the gmail database."""

import sqlite3
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.events.email import EmailMessagePayload
from workbench.tools.gmail.tables import (
    ATTACHMENTS,
    MESSAGES,
    RECIPIENTS,
    Attachment,
    Message,
    Recipient,
)


def _snippet(body: str) -> str:
    return " ".join(body.split())[:100]


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    messages: list[Message] = []
    recipients: list[Recipient] = []
    attachments: list[Attachment] = []
    for event in events:
        payload = event.payload
        if not isinstance(payload, EmailMessagePayload):
            continue
        messages.append(
            Message(
                message_id=payload.message_id,
                thread_id=payload.thread_id,
                in_reply_to=payload.in_reply_to,
                sender=payload.sender,
                subject=payload.subject,
                body=payload.body,
                time=int(event.time),
                snippet=_snippet(payload.body),
            )
        )
        for kind, people in (("to", payload.to), ("cc", payload.cc)):
            recipients += (
                Recipient(message_id=payload.message_id, person_id=person, kind=kind)
                for person in people
            )
        attachments += (
            Attachment(
                message_id=payload.message_id,
                filename=attachment.filename,
                media_type=attachment.media_type,
                document_id=attachment.document_id,
            )
            for attachment in payload.attachments
        )
    MESSAGES.insert(connection, messages)
    RECIPIENTS.insert(connection, recipients)
    ATTACHMENTS.insert(connection, attachments)

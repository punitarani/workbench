from typing import Literal

from pydantic import Field

from core.events._base import Payload
from core.ids import DocumentId, MessageId, PersonId, ThreadId


class Attachment(Payload):
    filename: str
    media_type: str
    # Content always lives in a document.created event; the email references it.
    document_id: DocumentId


class EmailMessagePayload(Payload):
    kind: Literal["email.message"]
    message_id: MessageId
    thread_id: ThreadId
    in_reply_to: MessageId | None
    sender: PersonId
    to: tuple[PersonId, ...] = Field(min_length=1)
    cc: tuple[PersonId, ...] = ()
    subject: str
    body: str
    attachments: tuple[Attachment, ...] = ()

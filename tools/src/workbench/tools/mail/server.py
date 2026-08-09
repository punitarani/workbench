"""Read tools over the mail database."""

from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.db import Query, connect_readonly
from workbench.tools.framework import UnknownRefError
from workbench.tools.mail.tables import ATTACHMENTS, MESSAGES, RECIPIENTS, Message


class ThreadSummary(BaseModel):
    thread_id: str
    subject: str
    message_count: int
    started: int
    last_activity: int


class AttachmentView(BaseModel):
    filename: str
    media_type: str
    document_id: str


class MessageView(Message):
    to: tuple[str, ...]
    cc: tuple[str, ...]
    attachments: tuple[AttachmentView, ...]


THREADS = Query(
    ThreadSummary,
    "SELECT thread_id, MIN(subject) AS subject, COUNT(*) AS message_count, "
    "MIN(time) AS started, MAX(time) AS last_activity "
    "FROM messages GROUP BY thread_id ORDER BY MIN(time)",
)

SEARCH = Query(
    Message,
    "SELECT * FROM messages WHERE subject LIKE ? OR body LIKE ? ORDER BY time",
)


def _view(connection, message: Message) -> MessageView:
    recipients = RECIPIENTS.select(connection, where={"message_id": message.message_id})
    attachments = ATTACHMENTS.select(
        connection, where={"message_id": message.message_id}
    )
    return MessageView(
        **message.model_dump(),
        to=tuple(r.person_id for r in recipients if r.kind == "to"),
        cc=tuple(r.person_id for r in recipients if r.kind == "cc"),
        attachments=tuple(
            AttachmentView(
                filename=a.filename,
                media_type=a.media_type,
                document_id=a.document_id,
            )
            for a in attachments
        ),
    )


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_threads() -> list[dict]:
        """List mail threads with subject, participants, and message count."""
        with connect_readonly(db_path) as connection:
            return [t.model_dump() for t in THREADS.run(connection)]

    @server.tool()
    def read_thread(thread_id: str) -> list[dict]:
        """Read every message in a thread, oldest first."""
        with connect_readonly(db_path) as connection:
            messages = MESSAGES.select(
                connection, where={"thread_id": thread_id}, order_by="time"
            )
            if not messages:
                raise UnknownRefError(f"no thread {thread_id}")
            return [_view(connection, m).model_dump() for m in messages]

    @server.tool()
    def search_mail(query: str) -> list[dict]:
        """Search subjects and bodies; returns matching messages."""
        pattern = f"%{query}%"
        with connect_readonly(db_path) as connection:
            return [m.model_dump() for m in SEARCH.run(connection, pattern, pattern)]

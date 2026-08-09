"""MCP servers over the projected tool databases.

Read-only in this phase: databases open through SQLite's read-only URI mode,
and every exposed tool is a query. Unknown ids raise — the error carries the
id, never a guess.
"""

import sqlite3
from pathlib import Path

from mcp.server import MCPServer

from workbench.core.errors import WorkbenchError


class UnknownRefError(WorkbenchError):
    """A tool was asked about an id that does not exist."""


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _rows(connection: sqlite3.Connection, sql: str, *params) -> list[dict]:
    return [dict(row) for row in connection.execute(sql, params)]


def _add_directory(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def directory() -> list[dict]:
        """List everyone in the organization's directory."""
        with _connect(db_path) as connection:
            return _rows(connection, "SELECT * FROM people ORDER BY person_id")


def _build_mail(server: MCPServer, db_path: Path) -> None:
    def _message(connection, row: dict) -> dict:
        recipients = _rows(
            connection,
            "SELECT person_id, kind FROM recipients WHERE message_id=?",
            row["message_id"],
        )
        row["to"] = [r["person_id"] for r in recipients if r["kind"] == "to"]
        row["cc"] = [r["person_id"] for r in recipients if r["kind"] == "cc"]
        row["attachments"] = _rows(
            connection,
            "SELECT filename, media_type, document_id FROM attachments "
            "WHERE message_id=?",
            row["message_id"],
        )
        return row

    @server.tool()
    def list_threads() -> list[dict]:
        """List mail threads with subject, participants, and message count."""
        with _connect(db_path) as connection:
            return _rows(
                connection,
                "SELECT thread_id, MIN(subject) AS subject, COUNT(*) AS "
                "message_count, MIN(time) AS started, MAX(time) AS last_activity "
                "FROM messages GROUP BY thread_id ORDER BY MIN(time)",
            )

    @server.tool()
    def read_thread(thread_id: str) -> list[dict]:
        """Read every message in a thread, oldest first."""
        with _connect(db_path) as connection:
            messages = _rows(
                connection,
                "SELECT * FROM messages WHERE thread_id=? ORDER BY time",
                thread_id,
            )
            if not messages:
                raise UnknownRefError(f"no thread {thread_id}")
            return [_message(connection, m) for m in messages]

    @server.tool()
    def search_mail(query: str) -> list[dict]:
        """Search subjects and bodies; returns matching messages."""
        with _connect(db_path) as connection:
            pattern = f"%{query}%"
            return _rows(
                connection,
                "SELECT * FROM messages WHERE subject LIKE ? OR body LIKE ? "
                "ORDER BY time",
                pattern,
                pattern,
            )


def _build_chat(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_conversations() -> list[dict]:
        """List channels and direct-message conversations with members."""
        with _connect(db_path) as connection:
            conversations = _rows(
                connection, "SELECT * FROM conversations ORDER BY conversation_id"
            )
            for conversation in conversations:
                conversation["members"] = [
                    r["person_id"]
                    for r in _rows(
                        connection,
                        "SELECT person_id FROM members WHERE conversation_id=?",
                        conversation["conversation_id"],
                    )
                ]
            return conversations

    @server.tool()
    def read_conversation(conversation_id: str) -> list[dict]:
        """Read a conversation's messages, oldest first."""
        with _connect(db_path) as connection:
            known = _rows(
                connection,
                "SELECT conversation_id FROM conversations WHERE conversation_id=?",
                conversation_id,
            )
            if not known:
                raise UnknownRefError(f"no conversation {conversation_id}")
            return _rows(
                connection,
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY time",
                conversation_id,
            )

    @server.tool()
    def search_chat(query: str) -> list[dict]:
        """Search message bodies across conversations."""
        with _connect(db_path) as connection:
            return _rows(
                connection,
                "SELECT * FROM messages WHERE body LIKE ? ORDER BY time",
                f"%{query}%",
            )


def _build_dms(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_documents() -> list[dict]:
        """List documents in the repository with their current revision."""
        with _connect(db_path) as connection:
            return _rows(connection, "SELECT * FROM documents ORDER BY path")

    @server.tool()
    def read_document(ref: str) -> dict:
        """Read a document's current content by id or path."""
        with _connect(db_path) as connection:
            documents = _rows(
                connection,
                "SELECT * FROM documents WHERE document_id=? OR path=?",
                ref,
                ref,
            )
            if not documents:
                raise UnknownRefError(f"no document {ref}")
            document = documents[0]
            head = _rows(
                connection,
                "SELECT content, author, change_summary FROM revisions "
                "WHERE document_id=? AND revision=?",
                document["document_id"],
                document["head_revision"],
            )[0]
            return {**document, **head}

    @server.tool()
    def document_history(document_id: str) -> list[dict]:
        """List a document's revisions with authors and change summaries."""
        with _connect(db_path) as connection:
            revisions = _rows(
                connection,
                "SELECT revision, author, change_summary, time FROM revisions "
                "WHERE document_id=? ORDER BY revision",
                document_id,
            )
            if not revisions:
                raise UnknownRefError(f"no document {document_id}")
            return revisions


def _build_matters(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_tickets(status: str | None = None) -> list[dict]:
        """List matters, optionally filtered by status."""
        with _connect(db_path) as connection:
            if status is None:
                return _rows(connection, "SELECT * FROM tickets ORDER BY created_time")
            return _rows(
                connection,
                "SELECT * FROM tickets WHERE status=? ORDER BY created_time",
                status,
            )

    @server.tool()
    def read_ticket(ticket_id: str) -> dict:
        """Read one matter with its full history and comments."""
        with _connect(db_path) as connection:
            tickets = _rows(
                connection, "SELECT * FROM tickets WHERE ticket_id=?", ticket_id
            )
            if not tickets:
                raise UnknownRefError(f"no ticket {ticket_id}")
            ticket = tickets[0]
            ticket["history"] = _rows(
                connection,
                "SELECT actor, field, old_value, new_value, time FROM history "
                "WHERE ticket_id=? ORDER BY time",
                ticket_id,
            )
            ticket["comments"] = _rows(
                connection,
                "SELECT actor, body, time FROM comments WHERE ticket_id=? "
                "ORDER BY time",
                ticket_id,
            )
            return ticket


_BUILDERS = {
    "mail": _build_mail,
    "chat": _build_chat,
    "dms": _build_dms,
    "matters": _build_matters,
}


def build_server(tool_name: str, db_path: Path) -> MCPServer:
    if tool_name not in _BUILDERS:
        raise WorkbenchError(f"unknown tool {tool_name!r}")
    server = MCPServer(
        name=f"workbench-{tool_name}",
        instructions=f"The organization's {tool_name} system.",
    )
    _BUILDERS[tool_name](server, db_path)
    _add_directory(server, db_path)
    return server

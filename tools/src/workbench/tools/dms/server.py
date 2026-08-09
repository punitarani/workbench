"""Read tools over the document-repository database."""

from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.db import Query, connect_readonly
from workbench.tools.dms.tables import DOCUMENTS, Document
from workbench.tools.framework import UnknownRefError


class RevisionHead(BaseModel):
    content: str
    author: str
    change_summary: str


class HistoryEntry(BaseModel):
    revision: int
    author: str
    change_summary: str
    time: int


BY_REF = Query(Document, "SELECT * FROM documents WHERE document_id=? OR path=?")

HEAD = Query(
    RevisionHead,
    "SELECT content, author, change_summary FROM revisions "
    "WHERE document_id=? AND revision=?",
)

HISTORY = Query(
    HistoryEntry,
    "SELECT revision, author, change_summary, time FROM revisions "
    "WHERE document_id=? ORDER BY revision",
)


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_documents() -> list[dict]:
        """List documents in the repository with their current revision."""
        with connect_readonly(db_path) as connection:
            documents = DOCUMENTS.select(connection, order_by="path")
            return [d.model_dump() for d in documents]

    @server.tool()
    def read_document(ref: str) -> dict:
        """Read a document's current content by id or path."""
        with connect_readonly(db_path) as connection:
            documents = BY_REF.run(connection, ref, ref)
            if not documents:
                raise UnknownRefError(f"no document {ref}")
            document = documents[0]
            [head] = HEAD.run(connection, document.document_id, document.head_revision)
            return {**document.model_dump(), **head.model_dump()}

    @server.tool()
    def document_history(document_id: str) -> list[dict]:
        """List a document's revisions with authors and change summaries."""
        with connect_readonly(db_path) as connection:
            history = HISTORY.run(connection, document_id)
            if not history:
                raise UnknownRefError(f"no document {document_id}")
            return [entry.model_dump() for entry in history]

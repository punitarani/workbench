"""Project document events into the repository database.

Head revisions fold in memory, so the write is append-only: every document
row lands once, already carrying its final head_revision.
"""

import sqlite3
from collections.abc import Sequence

from workbench.core.events import Event
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.tools.dms.tables import DOCUMENTS, REVISIONS, Document, Revision


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    documents: dict[str, Document] = {}
    revisions: list[Revision] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, DocumentCreatedPayload):
            documents[payload.document_id] = Document(
                document_id=payload.document_id,
                title=payload.title,
                path=payload.path,
                location=payload.location,
                content_format=payload.content_format,
                head_revision=1,
            )
            revisions.append(
                Revision(
                    document_id=payload.document_id,
                    revision=1,
                    author=payload.author,
                    content=payload.content,
                    change_summary="Created.",
                    time=int(event.time),
                )
            )
        elif isinstance(payload, DocumentRevisedPayload):
            head = documents[payload.document_id]
            documents[payload.document_id] = head.model_copy(
                update={"head_revision": payload.revision}
            )
            revisions.append(
                Revision(
                    document_id=payload.document_id,
                    revision=payload.revision,
                    author=payload.author,
                    content=payload.content,
                    change_summary=payload.change_summary,
                    time=int(event.time),
                )
            )
    DOCUMENTS.insert(connection, documents.values())
    REVISIONS.insert(connection, revisions)

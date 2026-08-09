"""Document-repository projection: documents and full revision history."""

from collections.abc import Sequence
from pathlib import Path

from workbench.core.events import Event
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.tools._sql import PEOPLE_SCHEMA, create_db, insert, project_people

handled_tags = ("document.created", "document.revised", "person.record")

SCHEMA = (
    PEOPLE_SCHEMA
    + """
CREATE TABLE documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT NOT NULL,
    location TEXT NOT NULL,
    content_format TEXT NOT NULL,
    head_revision INTEGER NOT NULL
);
CREATE TABLE revisions (
    document_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    change_summary TEXT NOT NULL,
    time INTEGER NOT NULL,
    PRIMARY KEY (document_id, revision)
);
"""
)


def project(events: Sequence[Event], db_path: Path) -> None:
    with create_db(db_path, SCHEMA) as connection:
        project_people(connection, events)
        heads: dict[str, int] = {}
        for event in events:
            payload = event.payload
            if isinstance(payload, DocumentCreatedPayload):
                heads[payload.document_id] = 1
                insert(
                    connection,
                    "documents",
                    (
                        "document_id",
                        "title",
                        "path",
                        "location",
                        "content_format",
                        "head_revision",
                    ),
                    [
                        (
                            payload.document_id,
                            payload.title,
                            payload.path,
                            payload.location,
                            payload.content_format,
                            1,
                        )
                    ],
                )
                insert(
                    connection,
                    "revisions",
                    (
                        "document_id",
                        "revision",
                        "author",
                        "content",
                        "change_summary",
                        "time",
                    ),
                    [
                        (
                            payload.document_id,
                            1,
                            payload.author,
                            payload.content,
                            "Created.",
                            int(event.time),
                        )
                    ],
                )
            elif isinstance(payload, DocumentRevisedPayload):
                heads[payload.document_id] = payload.revision
                connection.execute(
                    "UPDATE documents SET head_revision=? WHERE document_id=?",
                    (payload.revision, payload.document_id),
                )
                insert(
                    connection,
                    "revisions",
                    (
                        "document_id",
                        "revision",
                        "author",
                        "content",
                        "change_summary",
                        "time",
                    ),
                    [
                        (
                            payload.document_id,
                            payload.revision,
                            payload.author,
                            payload.content,
                            payload.change_summary,
                            int(event.time),
                        )
                    ],
                )

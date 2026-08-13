"""Project document events into the iManage database.

Head versions fold in memory, so the write is append-only: every document
row lands once, already carrying its final head_version. Document numbers
are assigned 1-based by first appearance, so the "LEGAL!{number}.{version}"
display ids are stable per document_id. Version 1 is the creation.
"""

import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel

from workbench.core.events import Event
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.tools.imanage.tables import DOCUMENTS, VERSIONS, Document, Version

_FORMAT_EXTENSIONS = {"markdown": "md", "spreadsheet": "xlsx", "formatted": "docx"}


def _workspace(path: str) -> str:
    """The workspace is the top-level path segment: /legal/... -> legal."""
    return path.strip("/").split("/")[0]


def _extension(path: str, content_format: str) -> str:
    basename = path.rsplit("/", 1)[-1]
    if "." in basename:
        return basename.rsplit(".", 1)[-1]
    return _FORMAT_EXTENSIONS.get(content_format, content_format)


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    documents: dict[str, BaseModel] = {}
    versions: list[Version] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, DocumentCreatedPayload):
            documents[payload.document_id] = Document(
                document_id=payload.document_id,
                document_number=len(documents) + 1,
                name=payload.title,
                path=payload.path,
                extension=_extension(payload.path, payload.content_format),
                workspace=_workspace(payload.path),
                head_version=1,
                **{"class": "DOC"},
            )
            versions.append(
                Version(
                    document_id=payload.document_id,
                    version=1,
                    author=payload.author,
                    content=payload.content,
                    comment="Created.",
                    time=int(event.time),
                )
            )
        elif isinstance(payload, DocumentRevisedPayload):
            head = documents[payload.document_id]
            documents[payload.document_id] = head.model_copy(
                update={"head_version": payload.revision}
            )
            versions.append(
                Version(
                    document_id=payload.document_id,
                    version=payload.revision,
                    author=payload.author,
                    content=payload.content,
                    comment=payload.change_summary,
                    time=int(event.time),
                )
            )
    DOCUMENTS.insert(connection, documents.values())
    VERSIONS.insert(connection, versions)

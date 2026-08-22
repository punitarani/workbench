"""Project document events into the iManage database.

Head versions fold in memory, so the write is append-only: every document
row lands once, already carrying its final head_version. Document numbers
are assigned 1-based by first appearance, so the "LEGAL!{number}.{version}"
display ids are stable per document_id. Version 1 is the creation.
"""

import sqlite3
from collections.abc import Sequence

from pydantic import BaseModel

from core.events import Event
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.filing import extension_of as _extension
from core.filing import filed_name
from core.filing import workspace_of as _workspace
from tools.imanage.tables import DOCUMENTS, VERSIONS, Document, Version


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
                # The path the system reports is the path the file is at.
                # These were two different strings: the profile served the
                # author's declared path and the file room wrote
                # `{workspace}/{basename}`, so a six-month world served 304
                # of 308 documents at a location that did not exist and an
                # agent that read a path and opened it failed 98.7% of the
                # time. Every document id resolved, so no referential check
                # could see it.
                #
                # The declared extension is wrong for the same reason and
                # in the same direction: a workbook an author named `.docx`
                # renders as `.xlsx`, so the served name would not open
                # even where the folders happened to agree. `filed_name`
                # decides both, and the materializer writes what it says.
                #
                # It is also workspace-relative, where the declared path may
                # lead with a slash. That is not cosmetic: `workspace_root /
                # "/legal/x.md"` discards the root and resolves at the
                # filesystem root, so a leading slash turns the obvious way
                # to open a served path into a file the agent will never
                # find, in a way that looks like the document is missing.
                path=filed_name(payload.path, payload.content_format),
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

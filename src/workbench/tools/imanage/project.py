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

_FORMAT_EXTENSIONS = {
    "markdown": "md",
    "spreadsheet": "xlsx",
    "formatted": "docx",
    "slides": "pptx",
}
# Where a document lands when its author gave a bare filename. Every
# document belongs to some workspace in iManage; without this a path of
# "brief.docx" made the file its own workspace and materialized as the
# directory "brief.docx/brief.docx".
_DEFAULT_WORKSPACE = "firm"


def _workspace(path: str) -> str:
    """The workspace is the top-level path segment: /legal/... -> legal.

    A path with no directory at all has no workspace to name, so it goes to
    the firm's own — never to a workspace named after the file.

    Folded to lower case because authors are not consistent and a file room
    is not case-sensitive. This world produced both ``Engagements`` and
    ``engagements``, which the surface served as two separate workspaces
    holding one engagement's papers between them — and one task keys its
    rows on ``(document, workspace)``, so the split would have scored two
    identical filings as two different answers.
    """

    segments = [segment for segment in path.strip("/").split("/") if segment]
    return segments[0].casefold() if len(segments) > 1 else _DEFAULT_WORKSPACE


# What each format may legitimately be called. A formatted document is a
# .docx normally and a .pdf when it is issued; tabular content is a .xlsx
# normally and a .csv when it is an extract. Anything else is the author
# mislabelling their own work.
_ALLOWED_EXTENSIONS = {
    # Plain text is legitimately a .csv or a .txt: a comma-separated
    # extract stored as text is a CSV, and the CSV reader has always
    # parsed exactly that.
    "markdown": ("md", "txt", "csv"),
    "spreadsheet": ("xlsx", "csv"),
    "formatted": ("docx", "pdf"),
    "slides": ("pptx",),
}


def _extension(path: str, content_format: str) -> str:
    """The suffix the file will actually carry.

    A name must never lie about its bytes. An author who declares a
    workbook and names it `.docx` produced a file that Word cannot open,
    and an agent that trusts the extension is misled by the environment
    rather than by the work — so the format wins the disagreement.
    """

    canonical = _FORMAT_EXTENSIONS.get(content_format, content_format)
    basename = path.rsplit("/", 1)[-1]
    if "." not in basename:
        return canonical
    suffix = basename.rsplit(".", 1)[-1].lower()
    allowed = _ALLOWED_EXTENSIONS.get(content_format)
    if allowed is None:
        return suffix
    return suffix if suffix in allowed else canonical


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

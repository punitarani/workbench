from typing import Literal

from pydantic import Field

from core.events._base import Payload
from core.ids import DocumentId, PersonId


class DocumentCreatedPayload(Payload):
    kind: Literal["document.created"]
    document_id: DocumentId
    author: PersonId
    title: str
    path: str
    location: Literal["repository", "attachment"]
    # markdown holds the text itself; the rest hold the canonical JSON of
    # the core.artifacts models, rendered into real office files
    # only at materialization: spreadsheet -> .xlsx, slides -> .pptx, and
    # formatted -> .docx or .pdf depending on the path's suffix.
    content_format: Literal["markdown", "spreadsheet", "formatted", "slides"]
    content: str


class DocumentRevisedPayload(Payload):
    kind: Literal["document.revised"]
    document_id: DocumentId
    # Creation is revision 1; every revision stores the full text, not a diff.
    revision: int = Field(ge=2)
    author: PersonId
    content: str
    change_summary: str

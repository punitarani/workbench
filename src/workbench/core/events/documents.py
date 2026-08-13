from typing import Literal

from pydantic import Field

from workbench.core.events._base import Payload
from workbench.core.ids import DocumentId, PersonId


class DocumentCreatedPayload(Payload):
    kind: Literal["document.created"]
    document_id: DocumentId
    author: PersonId
    title: str
    path: str
    location: Literal["repository", "attachment"]
    content_format: Literal["markdown"]
    content: str


class DocumentRevisedPayload(Payload):
    kind: Literal["document.revised"]
    document_id: DocumentId
    # Creation is revision 1; every revision stores the full text, not a diff.
    revision: int = Field(ge=2)
    author: PersonId
    content: str
    change_summary: str

"""Row models and tables for the document-repository database."""

from typing import Annotated

from pydantic import BaseModel

from workbench.tools.db import Id, Ref, Table


class Document(BaseModel):
    document_id: Annotated[str, Id("document")]
    title: str
    path: str
    location: str
    content_format: str
    head_revision: int


class Revision(BaseModel):
    document_id: Annotated[str, Ref("document")]
    revision: int
    author: Annotated[str, Ref("person")]
    content: str
    change_summary: str
    time: int


DOCUMENTS = Table("documents", Document, primary_key=("document_id",))
REVISIONS = Table("revisions", Revision, primary_key=("document_id", "revision"))

"""Row models and tables for the iManage work-product database.

Documents live in one library ("LEGAL"). The ``class`` column matches the
Work API profile key; it is a Python keyword, so the row model is built
with ``create_model`` rather than a class statement.
"""

from typing import Annotated

from pydantic import BaseModel, create_model

from workbench.tools.db import Id, Ref, Table

LIBRARY = "LEGAL"

Document = create_model(
    "Document",
    document_id=(Annotated[str, Id("document")], ...),
    document_number=(int, ...),
    name=(str, ...),
    path=(str, ...),
    extension=(str, ...),
    **{"class": (str, ...)},
    workspace=(str, ...),
    head_version=(int, ...),
)


class Version(BaseModel):
    document_id: Annotated[str, Ref("document")]
    version: int
    author: Annotated[str, Ref("person")]
    content: str
    comment: str
    time: int


DOCUMENTS = Table("documents", Document, primary_key=("document_id",))
VERSIONS = Table("versions", Version, primary_key=("document_id", "version"))

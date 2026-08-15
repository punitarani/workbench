"""Row models and tables for the iManage work-product database.

Documents live in one library ("LEGAL"). The ``class`` column matches the
Work API profile key; it is a Python keyword, so the row model is built
with ``create_model`` rather than a class statement. ``document_number``
is the library's own numbering, assigned once at projection: it is the
mapping behind the served "LEGAL!{number}.{version}" ids.
"""

from typing import Annotated, Literal

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


class Action(BaseModel):
    """One document or workspace this server opened for the signed-in user.

    iManage's actions panel. Written by the tools rather than by the
    projection, so the table is empty when a rollout starts. ``target_id``
    holds the world's own id — a document_id or a workspace name — because
    the "LEGAL!..." form is minted at the server boundary; the column
    carries both kinds, so it declares no Ref.
    """

    action_id: Annotated[str, Id("imanage.action")]
    tool: str
    target_kind: Literal["document", "workspace"]
    target_id: str
    person_id: Annotated[str | None, Ref("person")]
    time: int


DOCUMENTS = Table("documents", Document, primary_key=("document_id",))
VERSIONS = Table("versions", Version, primary_key=("document_id", "version"))
# Action table: empty after projection, written by the tools and read by
# the recents, the actions panel, and graders.
ACTIONS = Table("actions", Action, primary_key=("action_id",))

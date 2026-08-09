"""Read tools over the iManage work-product database.

Tool names mirror the official iManage MCP server (GA May 2026) and the
JSON responses are shaped like Work API profiles. Documents are addressed
by display id "LEGAL!{number}.{version}"; a missing version means head.
Workspaces have no table of their own: they derive from the workspace
column, numbered 1-based by first appearance (minimum document number).

``search`` looks through every version, so a hit can be text that a later
version deleted. Each document hit therefore reports ``matched_versions``
(the versions whose stored text matched, empty when the match was on
document metadata) and ``in_head`` (whether the match survives into the
head version).

Seat scoping: a document management system is firm-wide by design, so the
document tools read the whole library whatever ``WORKBENCH_SEAT`` says.
The seat only decides who "I" am: ``get_user_information`` with no query
answers with the seat rather than the whole staff list.
"""

import re
import sqlite3
from datetime import UTC, timedelta
from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.db import Query, connect_readonly
from workbench.tools.framework import (
    PEOPLE_TABLE,
    UnknownRefError,
    read_epoch,
    seat,
)
from workbench.tools.imanage.tables import DOCUMENTS, LIBRARY, VERSIONS, Version

_DISPLAY_ID = re.compile(rf"{LIBRARY}!(\d+)(?:\.(\d+))?")


class _WorkspaceRow(BaseModel):
    workspace: str
    first_number: int
    document_count: int


_WORKSPACES = Query(
    _WorkspaceRow,
    "SELECT workspace, MIN(document_number) AS first_number, "
    "COUNT(*) AS document_count FROM documents "
    "GROUP BY workspace ORDER BY first_number",
)

class _VersionHit(BaseModel):
    document_id: str
    version: int


_SEARCH_METADATA = Query(
    DOCUMENTS.model,
    "SELECT * FROM documents "
    "WHERE instr(lower(name), ?) > 0 OR instr(lower(path), ?) > 0 "
    "ORDER BY document_number",
)

_SEARCH_VERSIONS = Query(
    _VersionHit,
    "SELECT document_id, version FROM versions "
    "WHERE instr(lower(comment), ?) > 0 OR instr(lower(content), ?) > 0 "
    "ORDER BY document_id, version",
)


def _date(connection: sqlite3.Connection, seconds: int) -> str:
    moment = read_epoch(connection) + timedelta(seconds=seconds)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workspaces(connection: sqlite3.Connection) -> list[dict]:
    return [
        {
            "id": f"{LIBRARY}!W{number}",
            "name": row.workspace,
            "wstype": "workspace",
            "document_count": row.document_count,
        }
        for number, row in enumerate(_WORKSPACES.run(connection), start=1)
    ]


def _resolve_workspace(connection: sqlite3.Connection, workspace_id: str) -> dict:
    for workspace in _workspaces(connection):
        if workspace_id in (workspace["id"], workspace["name"]):
            return workspace
    raise UnknownRefError(f"no workspace {workspace_id}")


def _resolve_document(
    connection: sqlite3.Connection, ref: str
) -> tuple[BaseModel, int]:
    """Resolve "LEGAL!n.v", "LEGAL!n", bare "n", or an internal document id.

    Returns the document row and the referenced version (head when the
    reference names none).
    """
    number: int | None = None
    version: int | None = None
    if match := _DISPLAY_ID.fullmatch(ref):
        number = int(match.group(1))
        version = int(match.group(2)) if match.group(2) else None
    elif ref.isdigit():
        number = int(ref)
    where = {"document_number": number} if number is not None else {"document_id": ref}
    documents = DOCUMENTS.select(connection, where=where)
    if not documents:
        raise UnknownRefError(f"no document {ref}")
    [document] = documents
    return document, version if version is not None else document.head_version


def _version(
    connection: sqlite3.Connection, document: BaseModel, version: int, ref: str
) -> Version:
    rows = VERSIONS.select(
        connection, where={"document_id": document.document_id, "version": version}
    )
    if not rows:
        raise UnknownRefError(f"no version {version} of document {ref}")
    return rows[0]


def _person_name(connection: sqlite3.Connection, person_id: str) -> str:
    people = PEOPLE_TABLE.select(connection, where={"person_id": person_id})
    return people[0].name if people else person_id


def _document_hit(document: BaseModel) -> dict:
    dumped = document.model_dump()
    return {
        "id": f"{LIBRARY}!{dumped['document_number']}.{dumped['head_version']}",
        "document_number": dumped["document_number"],
        "version": dumped["head_version"],
        "name": dumped["name"],
        "wstype": "document",
        "workspace_name": dumped["workspace"],
        "path": dumped["path"],
    }


def _profile(connection: sqlite3.Connection, document: BaseModel, row: Version) -> dict:
    dumped = document.model_dump()
    workspace = _resolve_workspace(connection, dumped["workspace"])
    [created] = VERSIONS.select(
        connection, where={"document_id": dumped["document_id"], "version": 1}
    )
    return {
        "id": f"{LIBRARY}!{dumped['document_number']}.{row.version}",
        "database": LIBRARY,
        "document_number": dumped["document_number"],
        "version": row.version,
        "name": dumped["name"],
        "extension": dumped["extension"],
        "class": dumped["class"],
        "author": row.author,
        "author_description": _person_name(connection, row.author),
        "operator": row.author,
        "edit_date": _date(connection, row.time),
        "create_date": _date(connection, created.time),
        "size": len(row.content),
        "comment": row.comment,
        "is_checked_out": False,
        "wstype": "document",
        "workspace_id": workspace["id"],
        "workspace_name": workspace["name"],
        "path": dumped["path"],
        "content_type": "D",
    }


def _number_query(query: str) -> int | None:
    text = query.strip().removeprefix("#")
    return int(text) if text.isdigit() else None


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def search(query: str) -> dict:
        """Search workspaces and documents by name, path, comment, or
        content; a purely numeric query (or "#N") looks up a document
        number."""
        with connect_readonly(db_path) as connection:
            number = _number_query(query)
            if number is not None:
                documents = DOCUMENTS.select(
                    connection, where={"document_number": number}
                )
                return {"results": [_document_hit(d) for d in documents]}
            needle = query.lower()
            results = [
                workspace
                for workspace in _workspaces(connection)
                if needle in workspace["name"].lower()
            ]
            results += [
                _document_hit(document)
                for document in _SEARCH_DOCS.run(
                    connection, needle, needle, needle, needle
                )
            ]
            return {"results": results}

    @server.tool()
    def search_workspaces(criteria: str) -> list[dict]:
        """Search workspaces by name."""
        with connect_readonly(db_path) as connection:
            needle = criteria.lower()
            return [
                workspace
                for workspace in _workspaces(connection)
                if needle in workspace["name"].lower()
            ]

    @server.tool()
    def get_workspace_profile(workspace_id: str) -> dict:
        """Read a workspace's profile by id (e.g. "LEGAL!W1")."""
        with connect_readonly(db_path) as connection:
            return _resolve_workspace(connection, workspace_id)

    @server.tool()
    def get_container_children(container_id: str) -> dict:
        """List the documents inside a workspace."""
        with connect_readonly(db_path) as connection:
            workspace = _resolve_workspace(connection, container_id)
            documents = DOCUMENTS.select(
                connection,
                where={"workspace": workspace["name"]},
                order_by="document_number",
            )
            data = [
                {
                    "id": f"{LIBRARY}!{d['document_number']}.{d['head_version']}",
                    "name": d["name"],
                    "wstype": "document",
                    "path": d["path"],
                }
                for d in (document.model_dump() for document in documents)
            ]
            return {"data": data, "total_count": len(data)}

    @server.tool()
    def get_document_profile(document_id: str) -> dict:
        """Read a document version's profile; "LEGAL!n.v", "LEGAL!n", "n",
        and internal ids are accepted, defaulting to the head version."""
        with connect_readonly(db_path) as connection:
            document, version = _resolve_document(connection, document_id)
            row = _version(connection, document, version, document_id)
            return _profile(connection, document, row)

    @server.tool()
    def get_document_versions(document_id: str) -> dict:
        """List every version of a document with full profiles, ascending."""
        with connect_readonly(db_path) as connection:
            document, _ = _resolve_document(connection, document_id)
            rows = VERSIONS.select(
                connection,
                where={"document_id": document.document_id},
                order_by="version",
            )
            return {"data": [_profile(connection, document, row) for row in rows]}

    @server.tool()
    def download_document(document_id: str) -> dict:
        """Download a document version's text content (head when the
        reference names no version)."""
        with connect_readonly(db_path) as connection:
            document, version = _resolve_document(connection, document_id)
            row = _version(connection, document, version, document_id)
            return {
                "name": document.model_dump()["name"],
                "version": row.version,
                "content": row.content,
            }

    @server.tool()
    def get_libraries() -> dict:
        """List the libraries on this server."""
        return {"data": [{"id": LIBRARY, "display_name": LIBRARY, "type": "worksite"}]}

    @server.tool()
    def get_user_information(query: str = "") -> dict:
        """Look up users by name or email; an empty query lists everyone."""
        with connect_readonly(db_path) as connection:
            people = PEOPLE_TABLE.select(connection, order_by="person_id")
        needle = query.lower()
        return {
            "data": [
                {
                    "id": person.person_id,
                    "full_name": person.name,
                    "email": person.email_address,
                    "location": person.department,
                    "is_external": person.affiliation != "internal",
                }
                for person in people
                if not needle
                or needle in person.name.lower()
                or needle in person.email_address.lower()
            ]
        }

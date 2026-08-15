"""Read tools over the iManage work-product database.

Tool names mirror the official iManage Work MCP connector (GA May 2026)
and the JSON responses are shaped like Work API profiles.

Served ids follow the Work API grammar and are minted here, at the server
boundary: a document version is "LEGAL!{number}.{version}" (a reference
carrying no version means the head), a workspace "LEGAL!W{n}", a workspace
template "LEGAL!T{n}". The database keeps the world's own ids — ``doc-…``
for a document, the folder name for a workspace — so the record stays
coherent with every other system, and ``documents.document_number`` is the
mapping, assigned once at projection by order of first appearance. The
translation runs both ways: every tool that takes an id also accepts the
internal id or a bare document number, so an id this server hands out can
be handed straight back to it. Workspaces have no table of their own: they
derive from the workspace column, numbered 1-based by first appearance
(minimum document number), and a workspace's template shares its number.

``search`` looks through every version, so a hit can be text that a later
version deleted. Each document hit therefore reports ``matched_versions``
(the versions whose stored text matched, empty when the match was on
document metadata) and ``in_head`` (whether the match survives into the
head version).

Recents and the actions panel read one clock. Opening a document or a
workspace writes a row to the actions table — searching does not — and a
version the signed-in user wrote is the record's own evidence that they
touched that document; the recents rank documents and matters by the later
of the two. A read either answers or raises, so a logged action is always
``completed``, and reading has nothing to undo.

Pagination follows the official caps: 100 results a page and 500 across
all pages however many are asked for, with no caller-chosen page size, and
``get_document_versions`` answers with at most 1000 versions.

Seat scoping: a document management system is firm-wide by design, so the
document tools read the whole library whatever ``WORKBENCH_SEAT`` says.
The seat only decides who "I" am: ``get_user_information`` with no query
answers with the seat rather than the whole staff list, and the recents
and the actions panel carry that person's own work.
"""

import csv
import io
import re
import sqlite3
from collections.abc import Sequence
from datetime import UTC, timedelta
from pathlib import Path

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.db import Query, connect_readonly, connect_readwrite
from workbench.tools.framework import (
    PEOPLE_TABLE,
    UnknownRefError,
    read_epoch,
    seat,
)
from workbench.tools.imanage.tables import (
    ACTIONS,
    DOCUMENTS,
    LIBRARY,
    VERSIONS,
    Action,
    Version,
)

_DISPLAY_ID = re.compile(rf"{LIBRARY}!(\d+)(?:\.(\d+))?")
_PAGE_SIZE = 100
_MAX_RESULTS = 500
_MAX_VERSIONS = 1000


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


class _DocumentRef(BaseModel):
    document_id: str


class _VersionHit(_DocumentRef):
    version: int


# Metadata and version text are searched separately: a name or path
# describes the document as it stands, a version body describes only that
# version, and a hit has to say which of the two it was.
_SEARCH_METADATA = Query(
    _DocumentRef,
    "SELECT document_id FROM documents "
    "WHERE instr(lower(name), ?) > 0 OR instr(lower(path), ?) > 0",
)

_SEARCH_VERSIONS = Query(
    _VersionHit,
    "SELECT document_id, version FROM versions "
    "WHERE instr(lower(comment), ?) > 0 OR instr(lower(content), ?) > 0 "
    "ORDER BY document_id, version",
)


class _HeadTime(BaseModel):
    time: int


_HEAD_TIME = Query(_HeadTime, "SELECT COALESCE(MAX(time), 0) AS time FROM versions")


def _date(connection: sqlite3.Connection, seconds: int) -> str:
    moment = read_epoch(connection) + timedelta(seconds=seconds)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now(connection: sqlite3.Connection) -> int:
    """The world's head time — a rollout's "now" is where the record stops."""

    return _HEAD_TIME.run(connection)[0].time


def _served_id(document: dict, version: int) -> str:
    """The Work API id for one version of a document row."""

    return f"{LIBRARY}!{document['document_number']}.{version}"


def _paginate[T](items: Sequence[T], page: int) -> tuple[list[T], int, int | None]:
    """One page under the official caps: 100 results a page, 500 over all
    pages. The reported total is the capped one, which is what a caller can
    actually page through."""

    capped = list(items[:_MAX_RESULTS])
    start = max(page - 1, 0) * _PAGE_SIZE
    window = capped[start : start + _PAGE_SIZE]
    exhausted = start + _PAGE_SIZE >= len(capped)
    return window, len(capped), None if exhausted else page + 1


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


def _document_hit(
    document: BaseModel, matched_versions: Sequence[int] = (), *, in_head: bool = True
) -> dict:
    """One search result. ``id`` and ``version`` name the head, the document
    as it stands today; ``matched_versions`` names where the query actually
    hit, so a match on superseded text cannot pass for a current one."""

    dumped = document.model_dump()
    return {
        "id": _served_id(dumped, dumped["head_version"]),
        "document_number": dumped["document_number"],
        "version": dumped["head_version"],
        "name": dumped["name"],
        "wstype": "document",
        "workspace_name": dumped["workspace"],
        "path": dumped["path"],
        "matched_versions": list(matched_versions),
        "in_head": in_head,
    }


def _document_hits(connection: sqlite3.Connection, needle: str) -> list[dict]:
    versions: dict[str, list[int]] = {}
    for hit in _SEARCH_VERSIONS.run(connection, needle, needle):
        versions.setdefault(hit.document_id, []).append(hit.version)
    metadata = {
        row.document_id for row in _SEARCH_METADATA.run(connection, needle, needle)
    }
    documents = DOCUMENTS.select(connection, order_by="document_number")
    hits = []
    for document in documents:
        dumped = document.model_dump()
        document_id = dumped["document_id"]
        matched = versions.get(document_id, [])
        if not matched and document_id not in metadata:
            continue
        # A name or path match describes the document as it stands, so it is
        # current by construction even when no version body matched.
        in_head = document_id in metadata or dumped["head_version"] in matched
        hits.append(_document_hit(document, matched, in_head=in_head))
    return hits


def _profile(connection: sqlite3.Connection, document: BaseModel, row: Version) -> dict:
    dumped = document.model_dump()
    workspace = _resolve_workspace(connection, dumped["workspace"])
    [created] = VERSIONS.select(
        connection, where={"document_id": dumped["document_id"], "version": 1}
    )
    return {
        "id": _served_id(dumped, row.version),
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


def _record(db_path: Path, tool: str, kind: str, target_id: str) -> None:
    """Log an opened document or workspace to the actions table.

    Always called after the read has closed its transaction: an open read
    would block the write.
    """

    with connect_readwrite(db_path) as connection:
        ACTIONS.insert(
            connection,
            [
                Action(
                    action_id=f"act-{len(ACTIONS.select(connection)) + 1:06d}",
                    tool=tool,
                    target_kind=kind,
                    target_id=target_id,
                    person_id=seat(),
                    time=_now(connection),
                )
            ],
        )
        connection.commit()


def _own_actions(connection: sqlite3.Connection) -> list[tuple[int, Action]]:
    """The signed-in user's actions oldest first, each with its ordinal.

    Every action a rollout logs carries the same head time, so the ordinal
    is what keeps recency a total order.
    """

    person = seat()
    return [
        (ordinal, action)
        for ordinal, action in enumerate(
            ACTIONS.select(connection, order_by="action_id"), start=1
        )
        if person is None or action.person_id == person
    ]


def _touch(stamps: dict[str, tuple[int, int]], key: str, when: tuple[int, int]) -> None:
    stamps[key] = max(stamps.get(key, when), when)


def _document_recency(connection: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    """Internal document id -> when the signed-in user last touched it.

    Two kinds of evidence on one clock: a version that person wrote, which
    is the record's own trace of the work, and an open this server logged.
    A server with no seat counts the whole library's work.
    """

    person = seat()
    stamps: dict[str, tuple[int, int]] = {}
    for version in VERSIONS.select(connection):
        if person is None or version.author == person:
            _touch(stamps, version.document_id, (version.time, 0))
    for ordinal, action in _own_actions(connection):
        if action.target_kind == "document":
            _touch(stamps, action.target_id, (action.time, ordinal))
    return stamps


def _workspace_recency(connection: sqlite3.Connection) -> dict[str, tuple[int, int]]:
    """Workspace name -> when the user last touched the matter, by opening
    it or by touching a document filed in it."""

    workspaces = {
        dumped["document_id"]: dumped["workspace"]
        for dumped in (row.model_dump() for row in DOCUMENTS.select(connection))
    }
    stamps: dict[str, tuple[int, int]] = {}
    for document_id, when in _document_recency(connection).items():
        _touch(stamps, workspaces[document_id], when)
    for ordinal, action in _own_actions(connection):
        if action.target_kind == "workspace":
            _touch(stamps, action.target_id, (action.time, ordinal))
    return stamps


def _action_target(
    connection: sqlite3.Connection, action: Action, documents: dict[str, dict]
) -> str:
    """The served id for what an action names; the table stores the world's."""

    if action.target_kind == "document":
        document = documents[action.target_id]
        return _served_id(document, document["head_version"])
    return _resolve_workspace(connection, action.target_id)["id"]


def _by_recency(stamps: dict[str, tuple[int, int]]) -> list[str]:
    """Most recent first; the key breaks ties so the order is total."""

    return sorted(stamps, key=lambda key: (stamps[key], key), reverse=True)


def _templates(connection: sqlite3.Connection) -> list[dict]:
    """A library's matter templates.

    The record keeps no template store, so a library offers the shapes its
    matters already have: one template per workspace, carrying the folders
    that workspace files documents into and sharing its number.
    """

    folders: dict[str, set[str]] = {}
    for document in DOCUMENTS.select(connection):
        dumped = document.model_dump()
        segments = dumped["path"].strip("/").split("/")
        folders.setdefault(dumped["workspace"], set()).update(segments[1:-1])
    return [
        {
            "id": f"{LIBRARY}!T{number}",
            "name": workspace["name"],
            "database": LIBRARY,
            "wstype": "workspace_template",
            "folders": sorted(folders.get(workspace["name"], ())),
        }
        for number, workspace in enumerate(_workspaces(connection), start=1)
    ]


def _csv_rows(content: str) -> tuple[list[str], list[dict]]:
    """The header and rows of a CSV document's stored text.

    A short row pads with empty strings and a long one truncates to the
    header, the way a spreadsheet reader treats ragged columns.
    """

    rows = [cells for cells in csv.reader(io.StringIO(content)) if cells]
    if not rows:
        return [], []
    header, *body = rows
    return header, [
        {
            name: cells[index] if index < len(cells) else ""
            for index, name in enumerate(header)
        }
        for cells in body
    ]


def _number_query(query: str) -> int | None:
    text = query.strip().removeprefix("#")
    return int(text) if text.isdigit() else None


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def search(query: str, page: int = 1) -> dict:
        """Search workspaces and documents by name, path, comment, or
        content; a purely numeric query (or "#N") looks up a document
        number. Content search spans every version, so each document hit
        carries matched_versions and in_head: a hit whose in_head is false
        matched text the head version no longer contains."""
        with connect_readonly(db_path) as connection:
            number = _number_query(query)
            if number is not None:
                documents = DOCUMENTS.select(
                    connection, where={"document_number": number}
                )
                results = [_document_hit(d) for d in documents]
            else:
                needle = query.lower()
                results = [
                    workspace
                    for workspace in _workspaces(connection)
                    if needle in workspace["name"].lower()
                ]
                results += _document_hits(connection, needle)
        window, total, next_page = _paginate(results, page)
        return {"results": window, "total_count": total, "next_page": next_page}

    @server.tool()
    def search_workspaces(criteria: str) -> list[dict]:
        """Search workspaces by name."""
        with connect_readonly(db_path) as connection:
            needle = criteria.lower()
            matched = [
                workspace
                for workspace in _workspaces(connection)
                if needle in workspace["name"].lower()
            ]
        # A bare list carries no page cursor, so it answers with the first
        # page and nothing more.
        return matched[:_PAGE_SIZE]

    @server.tool()
    def get_workspace_profile(workspace_id: str) -> dict:
        """Read a workspace's profile by id (e.g. "LEGAL!W1")."""
        with connect_readonly(db_path) as connection:
            workspace = _resolve_workspace(connection, workspace_id)
        _record(db_path, "get_workspace_profile", "workspace", workspace["name"])
        return workspace

    @server.tool()
    def get_container_children(container_id: str, page: int = 1) -> dict:
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
                    "id": _served_id(d, d["head_version"]),
                    "name": d["name"],
                    "wstype": "document",
                    "path": d["path"],
                }
                for d in (document.model_dump() for document in documents)
            ]
        _record(db_path, "get_container_children", "workspace", workspace["name"])
        window, total, next_page = _paginate(data, page)
        return {"data": window, "total_count": total, "next_page": next_page}

    @server.tool()
    def get_document_profile(document_id: str) -> dict:
        """Read a document version's profile; "LEGAL!n.v", "LEGAL!n", "n",
        and internal ids are accepted, defaulting to the head version."""
        with connect_readonly(db_path) as connection:
            document, version = _resolve_document(connection, document_id)
            row = _version(connection, document, version, document_id)
            profile = _profile(connection, document, row)
        _record(db_path, "get_document_profile", "document", document.document_id)
        return profile

    @server.tool()
    def get_document_versions(document_id: str) -> dict:
        """List every version of a document with full profiles, ascending."""
        with connect_readonly(db_path) as connection:
            document, _ = _resolve_document(connection, document_id)
            rows = VERSIONS.select(
                connection,
                where={"document_id": document.document_id},
                order_by="version",
            )[:_MAX_VERSIONS]
            return {"data": [_profile(connection, document, row) for row in rows]}

    @server.tool()
    def download_document(document_id: str) -> dict:
        """Download a document version's text content (head when the
        reference names no version)."""
        with connect_readonly(db_path) as connection:
            document, version = _resolve_document(connection, document_id)
            row = _version(connection, document, version, document_id)
            content = {
                "name": document.model_dump()["name"],
                "version": row.version,
                "content": row.content,
            }
        _record(db_path, "download_document", "document", document.document_id)
        return content

    @server.tool()
    def fetch(id: str) -> dict:
        """Open whatever an id names — a workspace, or a document version
        with its text — so an id from search reads without knowing its kind."""
        with connect_readonly(db_path) as connection:
            try:
                workspace = _resolve_workspace(connection, id)
            except UnknownRefError:
                workspace = None
            if workspace is None:
                document, version = _resolve_document(connection, id)
                row = _version(connection, document, version, id)
                found = _profile(connection, document, row) | {"content": row.content}
                target = ("document", document.document_id)
            else:
                found, target = workspace, ("workspace", workspace["name"])
        _record(db_path, "fetch", *target)
        return found

    @server.tool()
    def get_rows_from_csv_document(document_id: str) -> dict:
        """Read every row of a CSV document, each keyed by column header."""
        with connect_readonly(db_path) as connection:
            document, version = _resolve_document(connection, document_id)
            row = _version(connection, document, version, document_id)
            dumped = document.model_dump()
            if dumped["extension"].lower() != "csv":
                raise UnknownRefError(
                    f"document {document_id} is a {dumped['extension']} document, "
                    "not a csv"
                )
            columns, rows = _csv_rows(row.content)
        _record(
            db_path, "get_rows_from_csv_document", "document", dumped["document_id"]
        )
        return {
            "id": _served_id(dumped, row.version),
            "name": dumped["name"],
            "columns": columns,
            "data": rows,
            "total_count": len(rows),
        }

    @server.tool()
    def get_recent_documents(page: int = 1) -> dict:
        """List the documents this user worked on most recently, newest
        first — what they wrote and what this server opened for them."""
        with connect_readonly(db_path) as connection:
            documents = {
                document.document_id: document
                for document in DOCUMENTS.select(connection)
            }
            order = _by_recency(_document_recency(connection))
            window, total, next_page = _paginate(order, page)
            data = []
            for document_id in window:
                document = documents[document_id]
                head = document.model_dump()["head_version"]
                data.append(
                    _profile(
                        connection,
                        document,
                        _version(connection, document, head, document_id),
                    )
                )
        return {"data": data, "total_count": total, "next_page": next_page}

    @server.tool()
    def get_recent_workspaces(page: int = 1) -> dict:
        """List the matters this user worked in most recently, newest first."""
        with connect_readonly(db_path) as connection:
            workspaces = {w["name"]: w for w in _workspaces(connection)}
            order = [
                name
                for name in _by_recency(_workspace_recency(connection))
                if name in workspaces
            ]
            window, total, next_page = _paginate(order, page)
            data = [workspaces[name] for name in window]
        return {"data": data, "total_count": total, "next_page": next_page}

    @server.tool()
    def get_workspace_templates(library_name: str) -> dict:
        """List the matter templates a library offers for new workspaces."""
        if library_name.upper() != LIBRARY:
            raise UnknownRefError(f"no library {library_name}")
        with connect_readonly(db_path) as connection:
            templates = _templates(connection)
        return {"data": templates[:_PAGE_SIZE], "total_count": len(templates)}

    @server.tool()
    def list_actions(page: int = 1) -> dict:
        """List the actions this user has performed, most recent first, with
        each one's status and whether it can be undone."""
        with connect_readonly(db_path) as connection:
            actions = [action for _, action in reversed(_own_actions(connection))]
            window, total, next_page = _paginate(actions, page)
            documents = {
                document.document_id: document.model_dump()
                for document in DOCUMENTS.select(connection)
            }
            data = [
                {
                    "id": action.action_id,
                    "action": action.tool,
                    "target_type": action.target_kind,
                    "target_id": _action_target(connection, action, documents),
                    "user_id": action.person_id,
                    "action_date": _date(connection, action.time),
                    # A read answers or raises, so nothing half-done is
                    # logged, and reading leaves nothing to undo.
                    "status": "completed",
                    "can_undo": False,
                }
                for action in window
            ]
        return {"data": data, "total_count": total, "next_page": next_page}

    @server.tool()
    def get_libraries() -> dict:
        """List the libraries on this server."""
        return {"data": [{"id": LIBRARY, "display_name": LIBRARY, "type": "worksite"}]}

    @server.tool()
    def get_user_information(query: str = "") -> dict:
        """Look up users by name or email. An empty query answers with the
        signed-in user, or with everyone when this server has no seat."""
        with connect_readonly(db_path) as connection:
            people = PEOPLE_TABLE.select(connection, order_by="person_id")
        needle = query.lower()
        if not needle and (person_id := seat()) is not None:
            people = [person for person in people if person.person_id == person_id]
            if not people:
                raise UnknownRefError(f"no user for seat {person_id}")
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

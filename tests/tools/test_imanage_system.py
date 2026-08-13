"""The iManage system: projection and Work-API-profile-shaped read tools.

Not registry-driven yet: the system projects and serves through the
framework directly, so these tests stay self-contained.
"""

import json
import sqlite3
from pathlib import Path

import pytest

from workbench.core.events import Event, EventPayload
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.people import PersonRecordPayload
from workbench.tools.framework import build_server, project_system
from workbench.tools.imanage import SYSTEM

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")

PROFILE_KEYS = {
    "id",
    "database",
    "document_number",
    "version",
    "name",
    "extension",
    "class",
    "author",
    "author_description",
    "operator",
    "edit_date",
    "create_date",
    "size",
    "comment",
    "is_checked_out",
    "wstype",
    "workspace_id",
    "workspace_name",
    "path",
    "content_type",
}


def _person(
    person_id: str,
    name: str,
    affiliation: str = "internal",
    department: str = "Legal",
) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{name.split()[0].lower()}@example.com",
        title="Counsel",
        department=department,
        manager=None,
        affiliation=affiliation,
        timezone="America/Los_Angeles",
    )


def _document(document_id: str, author: str, title: str, path: str, content: str):
    return DocumentCreatedPayload(
        kind="document.created",
        document_id=document_id,
        author=author,
        title=title,
        path=path,
        location="attachment" if path.startswith("/attachments/") else "repository",
        content_format="markdown",
        content=content,
    )


def _events() -> list[Event]:
    payloads: list[tuple[int, EventPayload]] = [
        (
            0,
            SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-fixture",
                seed_root=7,
                workplace_id="legal-demo",
                config_hash="0" * 64,
                schema_version=1,
                epoch="2026-03-12T00:00:00-07:00",
                timezone="America/Los_Angeles",
            ),
        ),
        (0, _person("per-daniel-reyes", "Daniel Reyes")),
        (0, _person("per-meredith-chao", "Meredith Chao")),
        (0, _person("per-jordan-hale", "Jordan Hale", "external", "Outside Counsel")),
        (
            100,
            _document(
                "doc-000001",
                "per-daniel-reyes",
                "NDA Playbook",
                "/legal/playbooks/nda-playbook.md",
                "Standard NDA fallback positions.",
            ),
        ),
        (
            200,
            _document(
                "doc-000002",
                "per-meredith-chao",
                "Fee Letter",
                "/attachments/fee-letter.md",
                "Fee terms for the Acme engagement.",
            ),
        ),
        (
            300,
            _document(
                "doc-000003",
                "per-daniel-reyes",
                "Engagement Letter",
                "/legal/letters/engagement-letter.md",
                "Engagement scope and staffing.",
            ),
        ),
        (
            700,
            DocumentRevisedPayload(
                kind="document.revised",
                document_id="doc-000001",
                revision=2,
                author="per-meredith-chao",
                content="Adds indemnification fallback.",
                change_summary="Tighten indemnity.",
            ),
        ),
    ]
    return [
        Event(seq=seq, time=time, tag=payload.kind, source="gm", payload=payload)
        for seq, (time, payload) in enumerate(payloads)
    ]


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "imanage.db"
    project_system(SYSTEM, _events(), path)
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> list:
    """Returns the parsed content items; list returns arrive one item each."""
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    return [json.loads(c.text) for c in result.content if hasattr(c, "text")]


def test_projection_numbers_and_workspaces(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        documents = connection.execute(
            "SELECT document_id, document_number, workspace, extension, class, "
            "head_version FROM documents ORDER BY document_number"
        ).fetchall()
        versions = connection.execute(
            "SELECT version, comment FROM versions WHERE document_id='doc-000001' "
            "ORDER BY version"
        ).fetchall()
    assert documents == [
        ("doc-000001", 1, "legal", "md", "DOC", 2),
        ("doc-000002", 2, "attachments", "md", "DOC", 1),
        ("doc-000003", 3, "legal", "md", "DOC", 1),
    ]
    assert versions == [(1, "Created."), (2, "Tighten indemnity.")]


async def test_search_by_content_and_number(server) -> None:
    [by_content] = await call(server, "search", {"query": "Indemnification"})
    assert [hit["id"] for hit in by_content["results"]] == ["LEGAL!1.2"]
    assert by_content["results"][0] == {
        "id": "LEGAL!1.2",
        "document_number": 1,
        "version": 2,
        "name": "NDA Playbook",
        "wstype": "document",
        "workspace_name": "legal",
        "path": "/legal/playbooks/nda-playbook.md",
        "matched_versions": [2],
        "in_head": True,
    }

    for query in ("#2", "2"):
        [numeric] = await call(server, "search", {"query": query})
        assert [hit["id"] for hit in numeric["results"]] == ["LEGAL!2.1"]

    [mixed] = await call(server, "search", {"query": "attachments"})
    assert mixed["results"][0]["wstype"] == "workspace"
    assert mixed["results"][0]["id"] == "LEGAL!W2"
    assert [h["id"] for h in mixed["results"] if h["wstype"] == "document"] == [
        "LEGAL!2.1"
    ]


async def test_search_reports_which_versions_matched(server) -> None:
    """A hit on superseded text must say so: "Standard NDA fallback
    positions." lives in version 1 only, and the head is version 2."""

    [stale] = await call(server, "search", {"query": "fallback positions"})
    [hit] = stale["results"]
    assert hit["id"] == "LEGAL!1.2"
    assert hit["version"] == 2
    assert hit["matched_versions"] == [1]
    assert hit["in_head"] is False

    [current] = await call(server, "search", {"query": "fallback"})
    [both] = current["results"]
    assert both["matched_versions"] == [1, 2]
    assert both["in_head"] is True

    # A name or path match is document metadata, current by construction.
    [by_name] = await call(server, "search", {"query": "Engagement Letter"})
    [named] = [h for h in by_name["results"] if h["wstype"] == "document"]
    assert named["matched_versions"] == []
    assert named["in_head"] is True

    [numeric] = await call(server, "search", {"query": "#1"})
    assert numeric["results"][0]["matched_versions"] == []
    assert numeric["results"][0]["in_head"] is True


async def test_seat_resolves_the_empty_user_query(server, monkeypatch) -> None:
    """iManage lists firm documents whatever the seat, but "who am I" —
    get_user_information with no query — must be the seat, not everyone."""

    monkeypatch.setenv("WORKBENCH_SEAT", "per-meredith-chao")
    [me] = await call(server, "get_user_information")
    assert [row["id"] for row in me["data"]] == ["per-meredith-chao"]
    [searched] = await call(server, "get_user_information", {"query": "daniel"})
    assert [row["id"] for row in searched["data"]] == ["per-daniel-reyes"]

    [documents] = await call(server, "search", {"query": "fee"})
    assert [h["id"] for h in documents["results"] if h["wstype"] == "document"] == [
        "LEGAL!2.1"
    ]

    monkeypatch.delenv("WORKBENCH_SEAT")
    [everyone] = await call(server, "get_user_information")
    assert len(everyone["data"]) == 3


async def test_search_workspaces(server) -> None:
    workspaces = await call(server, "search_workspaces", {"criteria": "leg"})
    assert workspaces == [
        {"id": "LEGAL!W1", "name": "legal", "wstype": "workspace", "document_count": 2}
    ]


async def test_document_profile_exact_keys(server) -> None:
    [profile] = await call(server, "get_document_profile", {"document_id": "LEGAL!1.2"})
    assert set(profile) == PROFILE_KEYS
    assert profile == {
        "id": "LEGAL!1.2",
        "database": "LEGAL",
        "document_number": 1,
        "version": 2,
        "name": "NDA Playbook",
        "extension": "md",
        "class": "DOC",
        "author": "per-meredith-chao",
        "author_description": "Meredith Chao",
        "operator": "per-meredith-chao",
        "edit_date": "2026-03-12T07:11:40Z",
        "create_date": "2026-03-12T07:01:40Z",
        "size": len("Adds indemnification fallback."),
        "comment": "Tighten indemnity.",
        "is_checked_out": False,
        "wstype": "document",
        "workspace_id": "LEGAL!W1",
        "workspace_name": "legal",
        "path": "/legal/playbooks/nda-playbook.md",
        "content_type": "D",
    }
    for ref in ("LEGAL!1", "1", "doc-000001"):
        [head] = await call(server, "get_document_profile", {"document_id": ref})
        assert head == profile, f"{ref} must resolve to the head version"
    [v1] = await call(server, "get_document_profile", {"document_id": "LEGAL!1.1"})
    assert (v1["version"], v1["comment"], v1["author"]) == (
        1,
        "Created.",
        "per-daniel-reyes",
    )


async def test_document_versions_ascending(server) -> None:
    [versions] = await call(
        server, "get_document_versions", {"document_id": "doc-000001"}
    )
    assert [entry["version"] for entry in versions["data"]] == [1, 2]
    for entry in versions["data"]:
        assert set(entry) == PROFILE_KEYS
    first, second = versions["data"]
    assert first["author_description"] == "Daniel Reyes"
    assert first["id"] == "LEGAL!1.1"
    assert second["edit_date"] == "2026-03-12T07:11:40Z"


async def test_download_by_explicit_version(server) -> None:
    [v1] = await call(server, "download_document", {"document_id": "LEGAL!1.1"})
    assert v1 == {
        "name": "NDA Playbook",
        "version": 1,
        "content": "Standard NDA fallback positions.",
    }
    [head] = await call(server, "download_document", {"document_id": "doc-000001"})
    assert (head["version"], head["content"]) == (2, "Adds indemnification fallback.")


async def test_container_children(server) -> None:
    [workspace] = await call(
        server, "get_workspace_profile", {"workspace_id": "LEGAL!W1"}
    )
    assert workspace == {
        "id": "LEGAL!W1",
        "name": "legal",
        "wstype": "workspace",
        "document_count": 2,
    }
    [children] = await call(
        server, "get_container_children", {"container_id": "LEGAL!W1"}
    )
    assert children["total_count"] == 2
    assert children["data"] == [
        {
            "id": "LEGAL!1.2",
            "name": "NDA Playbook",
            "wstype": "document",
            "path": "/legal/playbooks/nda-playbook.md",
        },
        {
            "id": "LEGAL!3.1",
            "name": "Engagement Letter",
            "wstype": "document",
            "path": "/legal/letters/engagement-letter.md",
        },
    ]


async def test_libraries_and_user_information(server) -> None:
    [libraries] = await call(server, "get_libraries")
    assert libraries == {
        "data": [{"id": "LEGAL", "display_name": "LEGAL", "type": "worksite"}]
    }
    [everyone] = await call(server, "get_user_information")
    assert len(everyone["data"]) == 3
    [meredith] = await call(server, "get_user_information", {"query": "meredith"})
    assert meredith["data"] == [
        {
            "id": "per-meredith-chao",
            "full_name": "Meredith Chao",
            "email": "meredith@example.com",
            "location": "Legal",
            "is_external": False,
        }
    ]
    [jordan] = await call(server, "get_user_information", {"query": "jordan@"})
    assert jordan["data"][0]["is_external"] is True
    assert jordan["data"][0]["location"] == "Outside Counsel"


async def test_unknown_ids_raise(server) -> None:
    unknowns = [
        ("get_workspace_profile", {"workspace_id": "LEGAL!W9"}, "LEGAL!W9"),
        ("get_container_children", {"container_id": "LEGAL!W9"}, "LEGAL!W9"),
        ("get_document_profile", {"document_id": "doc-999999"}, "doc-999999"),
        ("get_document_profile", {"document_id": "LEGAL!9"}, "LEGAL!9"),
        ("get_document_profile", {"document_id": "LEGAL!1.9"}, "LEGAL!1.9"),
        ("get_document_versions", {"document_id": "999"}, "999"),
        ("download_document", {"document_id": "LEGAL!9.1"}, "LEGAL!9.1"),
    ]
    for name, arguments, marker in unknowns:
        with pytest.raises(Exception, match=marker):
            await server.call_tool(name, arguments)


async def test_leakage_and_no_write_tools(server) -> None:
    arguments = {
        "search": {"query": "a"},
        "search_workspaces": {"criteria": "a"},
        "get_workspace_profile": {"workspace_id": "LEGAL!W1"},
        "get_container_children": {"container_id": "LEGAL!W1"},
        "get_document_profile": {"document_id": "LEGAL!1.1"},
        "get_document_versions": {"document_id": "LEGAL!1"},
        "download_document": {"document_id": "LEGAL!1"},
    }
    tools = await server.list_tools()
    assert {tool.name for tool in tools} >= {
        "search",
        "search_workspaces",
        "get_workspace_profile",
        "get_container_children",
        "get_document_profile",
        "get_document_versions",
        "download_document",
        "get_libraries",
        "get_user_information",
    }
    for tool in tools:
        assert not any(
            verb in tool.name
            for verb in ("send", "create", "update", "delete", "write", "post")
        ), f"imanage exposes a write tool in the read-only phase: {tool.name}"
        result = await server.call_tool(tool.name, arguments.get(tool.name, {}))
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        for marker in OFFSTAGE_MARKERS:
            assert marker not in text, f"imanage.{tool.name} leaked {marker!r}"

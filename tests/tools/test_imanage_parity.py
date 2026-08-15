"""iManage surface parity: the official tool set, the id grammar, and the caps."""

import json
import re
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

# The official iManage Work MCP connector as published 2026-08-14: the nine
# read tools we already served, plus fetch, the CSV reader, the two recents,
# the template list, and the actions panel.
OFFICIAL_TOOLS = frozenset(
    {
        "search",
        "fetch",
        "search_workspaces",
        "get_workspace_profile",
        "get_workspace_templates",
        "get_container_children",
        "get_document_profile",
        "get_document_versions",
        "get_rows_from_csv_document",
        "get_recent_documents",
        "get_recent_workspaces",
        "download_document",
        "get_libraries",
        "get_user_information",
        "list_actions",
    }
)

DOCUMENT_ID = re.compile(r"LEGAL!\d+\.\d+")
WORKSPACE_ID = re.compile(r"LEGAL!W\d+")

# A ragged final row: a spreadsheet writer that stopped short of the last
# column is exactly what a CSV reader has to survive.
RATE_CARD = (
    "matter,partner,rate\n"
    "Acme merger,Chao,675\n"
    "Acme lease,Reyes,540\n"
    "Acme diligence,Reyes\n"
)


def _person(person_id: str, name: str) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{name.split()[0].lower()}@calder.example",
        title="Counsel",
        department="Legal",
        manager=None,
        affiliation="internal",
        timezone="America/Los_Angeles",
    )


def _document(
    document_id: str, author: str, title: str, path: str, content: str
) -> DocumentCreatedPayload:
    return DocumentCreatedPayload(
        kind="document.created",
        document_id=document_id,
        author=author,
        title=title,
        path=path,
        location="repository",
        content_format="markdown",
        content=content,
    )


def _started() -> SimRunStartedPayload:
    return SimRunStartedPayload(
        kind="sim.run.started",
        run_id="run-imanage-parity",
        seed_root=11,
        workplace_id="calder",
        config_hash="0" * 64,
        schema_version=1,
        epoch="2026-03-12T00:00:00-07:00",
        timezone="America/Los_Angeles",
    )


def _log(payloads: list[tuple[int, EventPayload]]) -> list[Event]:
    return [
        Event(seq=seq, time=time, tag=payload.kind, source="gm", payload=payload)
        for seq, (time, payload) in enumerate(payloads)
    ]


def _events() -> list[Event]:
    return _log(
        [
            (0, _started()),
            (0, _person("per-ana", "Ana Reyes")),
            (0, _person("per-ben", "Ben Chao")),
            (
                100,
                _document(
                    "doc-000001",
                    "per-ana",
                    "NDA Playbook",
                    "/legal/playbooks/nda-playbook.md",
                    "Standard NDA fallback positions.",
                ),
            ),
            (
                200,
                _document(
                    "doc-000002",
                    "per-ben",
                    "Engagement Letter",
                    "/legal/letters/engagement-letter.md",
                    "Engagement scope and staffing.",
                ),
            ),
            (
                300,
                _document(
                    "doc-000003",
                    "per-ana",
                    "Rate Card",
                    "/clients/acme/rate-card.csv",
                    RATE_CARD,
                ),
            ),
            (
                400,
                _document(
                    "doc-000004",
                    "per-ben",
                    "Closing Checklist",
                    "/clients/acme/closing-checklist.md",
                    "Signature pages, funds flow, stock ledger.",
                ),
            ),
            (
                700,
                DocumentRevisedPayload(
                    kind="document.revised",
                    document_id="doc-000001",
                    revision=2,
                    author="per-ben",
                    content="Adds indemnification fallback.",
                    change_summary="Tighten indemnity.",
                ),
            ),
        ]
    )


def _bulk_events(count: int) -> list[Event]:
    """One workspace holding more documents than any page or cap allows."""

    payloads: list[tuple[int, EventPayload]] = [
        (0, _started()),
        (0, _person("per-ana", "Ana Reyes")),
    ]
    for number in range(1, count + 1):
        payloads.append(
            (
                number,
                _document(
                    f"doc-{number:06d}",
                    "per-ana",
                    f"Brief {number}",
                    f"/vault/matter-{number:04d}/brief.md",
                    "Boilerplate clause text.",
                ),
            )
        )
    return _log(payloads)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "imanage.db"
    project_system(SYSTEM, _events(), path)
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


@pytest.fixture
def bulk_server(tmp_path: Path):
    path = tmp_path / "bulk.db"
    project_system(SYSTEM, _bulk_events(620), path)
    return build_server(SYSTEM, path)


async def call(server, name: str, **arguments) -> dict:
    result = await server.call_tool(name, arguments)
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


async def test_tool_inventory_matches_the_official_surface(server) -> None:
    listed = {tool.name for tool in await server.list_tools()}
    assert listed == OFFICIAL_TOOLS


class TestIdGrammar:
    """Served ids are "LIBRARY!number.version"; the world's own ids stay in
    the database, and an id we hand out can be handed straight back."""

    async def test_every_served_id_uses_the_work_api_grammar(self, server) -> None:
        results = (await call(server, "search", query="e"))["results"]
        documents = [hit for hit in results if hit["wstype"] == "document"]
        workspaces = [hit for hit in results if hit["wstype"] == "workspace"]
        assert documents and workspaces
        assert all(DOCUMENT_ID.fullmatch(hit["id"]) for hit in documents)
        assert all(WORKSPACE_ID.fullmatch(hit["id"]) for hit in workspaces)
        children = await call(server, "get_container_children", container_id="LEGAL!W1")
        assert all(DOCUMENT_ID.fullmatch(child["id"]) for child in children["data"])

    async def test_a_served_id_reads_back(self, server) -> None:
        [hit] = [
            result
            for result in (await call(server, "search", query="indemnification"))[
                "results"
            ]
            if result["wstype"] == "document"
        ]
        served = hit["id"]
        assert served == "LEGAL!1.2"
        profile = await call(server, "get_document_profile", document_id=served)
        assert profile["id"] == served
        download = await call(server, "download_document", document_id=served)
        assert download["version"] == 2
        fetched = await call(server, "fetch", id=served)
        assert fetched["id"] == served
        versions = await call(server, "get_document_versions", document_id=served)
        assert [entry["id"] for entry in versions["data"]] == ["LEGAL!1.1", served]

    async def test_head_number_and_internal_id_resolve_alike(self, server) -> None:
        profile = await call(server, "get_document_profile", document_id="LEGAL!1.2")
        for reference in ("LEGAL!1", "1", "doc-000001"):
            assert (
                await call(server, "get_document_profile", document_id=reference)
            ) == profile

    async def test_workspace_ids_round_trip(self, server) -> None:
        [workspace] = [
            hit
            for hit in (await call(server, "search", query="clients"))["results"]
            if hit["wstype"] == "workspace"
        ]
        profile = await call(
            server, "get_workspace_profile", workspace_id=workspace["id"]
        )
        assert profile["id"] == workspace["id"]
        children = await call(
            server, "get_container_children", container_id=workspace["id"]
        )
        assert [child["name"] for child in children["data"]] == [
            "Rate Card",
            "Closing Checklist",
        ]

    async def test_the_database_keeps_the_world_ids(self, server, db_path) -> None:
        await call(server, "download_document", document_id="LEGAL!2")
        with sqlite3.connect(db_path) as connection:
            documents = connection.execute(
                "SELECT document_id FROM documents ORDER BY document_number"
            ).fetchall()
            targets = connection.execute("SELECT target_id FROM actions").fetchall()
        assert documents == [(f"doc-{n:06d}",) for n in range(1, 5)]
        # The action names the document the way the record does, not the way
        # the server served it: the grammar lives at the boundary only.
        assert targets == [("doc-000002",)]


class TestCsvRows:
    async def test_rows_are_keyed_by_header(self, server) -> None:
        rows = await call(server, "get_rows_from_csv_document", document_id="LEGAL!3")
        assert rows["columns"] == ["matter", "partner", "rate"]
        assert rows["total_count"] == 3
        assert rows["data"][0] == {
            "matter": "Acme merger",
            "partner": "Chao",
            "rate": "675",
        }
        assert rows["id"] == "LEGAL!3.1"

    async def test_a_short_row_pads_to_the_header(self, server) -> None:
        rows = await call(
            server, "get_rows_from_csv_document", document_id="doc-000003"
        )
        assert rows["data"][-1] == {
            "matter": "Acme diligence",
            "partner": "Reyes",
            "rate": "",
        }

    async def test_a_document_that_is_not_a_csv_is_rejected(self, server) -> None:
        with pytest.raises(Exception, match="not a csv"):
            await server.call_tool(
                "get_rows_from_csv_document", {"document_id": "LEGAL!1"}
            )


class TestRecents:
    async def test_documents_come_back_newest_first(self, server) -> None:
        recent = await call(server, "get_recent_documents")
        assert [entry["id"] for entry in recent["data"]] == [
            "LEGAL!1.2",
            "LEGAL!4.1",
            "LEGAL!3.1",
            "LEGAL!2.1",
        ]
        assert recent["total_count"] == 4
        assert recent["next_page"] is None

    async def test_opening_a_document_promotes_it(self, server) -> None:
        await call(server, "download_document", document_id="LEGAL!2")
        recent = await call(server, "get_recent_documents")
        assert [entry["id"] for entry in recent["data"]][:2] == [
            "LEGAL!2.1",
            "LEGAL!1.2",
        ]

    async def test_workspaces_follow_the_documents(self, server) -> None:
        recent = await call(server, "get_recent_workspaces")
        assert [entry["name"] for entry in recent["data"]] == ["legal", "clients"]
        await call(server, "get_container_children", container_id="LEGAL!W2")
        promoted = await call(server, "get_recent_workspaces")
        assert [entry["name"] for entry in promoted["data"]] == ["clients", "legal"]

    async def test_recents_are_the_seat_own_work(self, server, monkeypatch) -> None:
        """The library is firm-wide, but "recent" is personal: Ana sees the
        documents she wrote, not the ones her partner wrote."""

        monkeypatch.setenv("WORKBENCH_SEAT", "per-ana")
        recent = await call(server, "get_recent_documents")
        # Ana's version 1 is what makes the playbook hers; the profile is
        # still the document as it stands, head version and all.
        assert [entry["id"] for entry in recent["data"]] == ["LEGAL!3.1", "LEGAL!1.2"]
        await call(server, "download_document", document_id="LEGAL!4")
        assert [
            entry["id"]
            for entry in (await call(server, "get_recent_documents"))["data"]
        ] == ["LEGAL!4.1", "LEGAL!3.1", "LEGAL!1.2"]
        monkeypatch.delenv("WORKBENCH_SEAT")
        assert (await call(server, "get_recent_documents"))["total_count"] == 4


class TestActions:
    async def test_the_panel_starts_empty_and_records_opens(self, server) -> None:
        assert (await call(server, "list_actions"))["data"] == []
        await call(server, "search", query="nda")
        assert (await call(server, "list_actions"))["data"] == [], (
            "searching is not an action"
        )
        await call(server, "get_document_profile", document_id="LEGAL!1")
        await call(server, "get_workspace_profile", workspace_id="LEGAL!W2")
        actions = await call(server, "list_actions")
        assert [entry["action"] for entry in actions["data"]] == [
            "get_workspace_profile",
            "get_document_profile",
        ], "most recent first"
        assert [entry["target_id"] for entry in actions["data"]] == [
            "LEGAL!W2",
            "LEGAL!1.2",
        ]
        assert actions["data"][0]["target_type"] == "workspace"

    async def test_actions_carry_status_undo_and_a_date(self, server) -> None:
        await call(server, "fetch", id="LEGAL!3")
        [action] = (await call(server, "list_actions"))["data"]
        assert action["id"] == "act-000001"
        assert action["status"] == "completed"
        assert action["can_undo"] is False
        assert action["action_date"] == "2026-03-12T07:11:40Z"
        assert action["user_id"] is None

    async def test_actions_are_the_seat_own(self, server, monkeypatch) -> None:
        monkeypatch.setenv("WORKBENCH_SEAT", "per-ana")
        await call(server, "download_document", document_id="LEGAL!1")
        [action] = (await call(server, "list_actions"))["data"]
        assert action["user_id"] == "per-ana"
        monkeypatch.setenv("WORKBENCH_SEAT", "per-ben")
        assert (await call(server, "list_actions"))["data"] == []


class TestFetch:
    async def test_fetch_returns_a_document_with_its_text(self, server) -> None:
        fetched = await call(server, "fetch", id="LEGAL!1.1")
        assert fetched["content"] == "Standard NDA fallback positions."
        assert fetched["wstype"] == "document"
        assert fetched["version"] == 1

    async def test_fetch_returns_a_workspace_profile(self, server) -> None:
        fetched = await call(server, "fetch", id="LEGAL!W1")
        assert fetched == {
            "id": "LEGAL!W1",
            "name": "legal",
            "wstype": "workspace",
            "document_count": 2,
        }

    async def test_fetch_rejects_an_unknown_id(self, server) -> None:
        with pytest.raises(Exception, match="LEGAL!9.1"):
            await server.call_tool("fetch", {"id": "LEGAL!9.1"})


class TestTemplates:
    async def test_templates_carry_the_folders_a_matter_uses(self, server) -> None:
        templates = await call(server, "get_workspace_templates", library_name="LEGAL")
        assert templates["data"] == [
            {
                "id": "LEGAL!T1",
                "name": "legal",
                "database": "LEGAL",
                "wstype": "workspace_template",
                "folders": ["letters", "playbooks"],
            },
            {
                "id": "LEGAL!T2",
                "name": "clients",
                "database": "LEGAL",
                "wstype": "workspace_template",
                "folders": ["acme"],
            },
        ]
        assert templates["total_count"] == 2

    async def test_an_unknown_library_is_rejected(self, server) -> None:
        with pytest.raises(Exception, match="ACTIVE"):
            await server.call_tool(
                "get_workspace_templates", {"library_name": "ACTIVE"}
            )


class TestPaginationCaps:
    """100 results a page, 500 across all pages, 1000 versions — the official
    caps, with no caller-chosen page size anywhere."""

    async def test_search_pages_at_a_hundred_and_stops_at_five_hundred(
        self, bulk_server
    ) -> None:
        first = await call(bulk_server, "search", query="clause")
        assert len(first["results"]) == 100
        assert (first["total_count"], first["next_page"]) == (500, 2)
        last = await call(bulk_server, "search", query="clause", page=5)
        assert len(last["results"]) == 100
        assert last["next_page"] is None
        assert first["results"][0]["id"] != last["results"][0]["id"]
        beyond = await call(bulk_server, "search", query="clause", page=6)
        assert beyond["results"] == []

    async def test_search_takes_no_page_size(self, bulk_server) -> None:
        [tool] = [t for t in await bulk_server.list_tools() if t.name == "search"]
        assert set(tool.input_schema["properties"]) == {"query", "page"}

    async def test_children_and_recents_share_the_caps(self, bulk_server) -> None:
        children = await call(
            bulk_server, "get_container_children", container_id="LEGAL!W1"
        )
        assert (len(children["data"]), children["total_count"]) == (100, 500)
        recent = await call(bulk_server, "get_recent_documents", page=2)
        assert (len(recent["data"]), recent["next_page"]) == (100, 3)

    async def test_versions_cap_is_a_thousand(self, bulk_server) -> None:
        [tool] = [
            t
            for t in await bulk_server.list_tools()
            if t.name == "get_document_versions"
        ]
        assert set(tool.input_schema["properties"]) == {"document_id"}
        versions = await call(
            bulk_server, "get_document_versions", document_id="LEGAL!1"
        )
        assert len(versions["data"]) == 1

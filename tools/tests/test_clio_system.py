"""The Clio system: projection, Clio integer id spaces, and the v4-shaped
read surface with its ``{"data": ...}`` envelope."""

import json
from pathlib import Path

import pytest
from projection_fixtures import coherent_events

from workbench.core.events import Event, EventPayload
from workbench.core.events.people import (
    OrganizationRecordPayload,
    PersonRecordPayload,
)
from workbench.core.events.tickets import (
    FieldChange,
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from workbench.core.events.work import TimeLoggedPayload
from workbench.tools.clio import SYSTEM
from workbench.tools.coherence import check_coherence
from workbench.tools.framework import build_server, project_system

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")

NOTE_BODY = "Redlined the indemnification clause; waiting on their counsel."


def clio_events() -> list[Event]:
    events = coherent_events()
    extensions: list[tuple[int, str, EventPayload]] = [
        (
            800,
            "gm",
            OrganizationRecordPayload(
                kind="org.record",
                org_id="org-blue-harbor",
                name="Blue Harbor Logistics",
                category="client",
            ),
        ),
        (
            800,
            "gm",
            PersonRecordPayload(
                kind="person.record",
                person_id="per-nina-brooks",
                name="Nina Brooks",
                email_address="nina@blueharbor.example.com",
                title="Operations Director",
                department="External",
                manager=None,
                affiliation="external",
                timezone="America/New_York",
                organization="org-blue-harbor",
            ),
        ),
        (
            800,
            "gm",
            PersonRecordPayload(
                kind="person.record",
                person_id="per-omar-diallo",
                name="Omar Diallo",
                email_address="omar@example.com",
                title="Billing Coordinator",
                department="Operations",
                manager=None,
                affiliation="internal",
                timezone="America/Los_Angeles",
            ),
        ),
        (
            1000,
            "meredith",
            TicketCreatedPayload(
                kind="ticket.created",
                ticket_id="tkt-000002",
                actor="per-meredith-chao",
                title="Blue Harbor carrier agreement",
                description="Negotiate the master carrier agreement.",
                requester="per-nina-brooks",
                assignee="per-meredith-chao",
                status="open",
                priority="high",
                ticket_type="contract-negotiation",
                client_ref="org-blue-harbor",
                fields=(),
            ),
        ),
        (
            1500,
            "daniel",
            TicketCommentedPayload(
                kind="ticket.commented",
                ticket_id="tkt-000001",
                actor="per-daniel-reyes",
                body=NOTE_BODY,
            ),
        ),
        (
            2000,
            "meredith",
            TimeLoggedPayload(
                kind="work.time.logged",
                person_id="per-meredith-chao",
                ticket_id="tkt-000002",
                minutes=90,
                note="Drafted the carrier agreement term sheet.",
            ),
        ),
        (
            90000,
            "meredith",
            TicketUpdatedPayload(
                kind="ticket.updated",
                ticket_id="tkt-000002",
                actor="per-meredith-chao",
                changes=(FieldChange(field="status", old="open", new="closed"),),
            ),
        ),
    ]
    base = len(events)
    for offset, (time, source, payload) in enumerate(extensions):
        events.append(
            Event(
                seq=base + offset,
                time=time,
                tag=payload.kind,
                source=source,
                payload=payload,
            )
        )
    return events


@pytest.fixture
def server(tmp_path: Path):
    db_path = tmp_path / "clio.db"
    project_system(SYSTEM, clio_events(), db_path)
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> dict:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def test_clio_projection_is_coherent(tmp_path: Path) -> None:
    state = tmp_path / "state"
    project_system(SYSTEM, clio_events(), state / "clio.db")
    assert check_coherence(state, (SYSTEM,)) == ()


async def test_matter_numbering_and_display_number(server) -> None:
    envelope = await call(server, "list_matters")
    assert set(envelope) == {"data", "meta"}
    assert envelope["meta"] == {"paging": {}}
    matters = envelope["data"]
    assert [m["id"] for m in matters] == [1, 2]
    assert [m["number"] for m in matters] == [1, 2]
    assert matters[0]["display_number"] == "00001-Alvarez"
    assert matters[1]["display_number"] == "00002-BlueHarborLogistics"
    assert matters[0]["etag"] == '"m1"'


async def test_status_folds_to_closed_with_close_date(server) -> None:
    matters = (await call(server, "list_matters"))["data"]
    assert matters[0]["status"] == "In-review"
    assert matters[0]["close_date"] is None
    assert matters[1]["status"] == "Closed"
    assert matters[1]["open_date"] == "2026-03-12"
    assert matters[1]["close_date"] == "2026-03-13"


async def test_list_matters_filters(server) -> None:
    closed = (await call(server, "list_matters", {"status": "closed"}))["data"]
    assert [m["number"] for m in closed] == [2]
    assert (await call(server, "list_matters", {"status": "open"}))["data"] == []

    by_display = (await call(server, "list_matters", {"query": "blueharbor"}))["data"]
    assert [m["number"] for m in by_display] == [2]
    by_client_name = (await call(server, "list_matters", {"query": "Blue Harbor"}))[
        "data"
    ]
    assert [m["number"] for m in by_client_name] == [2]
    by_description = (await call(server, "list_matters", {"query": "Review NDA"}))[
        "data"
    ]
    assert [m["number"] for m in by_description] == [1]

    by_client = (await call(server, "list_matters", {"client_id": 1}))["data"]
    assert [m["number"] for m in by_client] == [2]
    limited = (await call(server, "list_matters", {"limit": 1}))["data"]
    assert [m["number"] for m in limited] == [1]


async def test_get_matter_detail(server) -> None:
    matter = (await call(server, "get_matter", {"id": 2}))["data"]
    assert matter["client"] == {
        "id": 1,
        "name": "Blue Harbor Logistics",
        "type": "Company",
    }
    assert matter["responsible_attorney"] == {"id": 3, "name": "Meredith Chao"}
    assert matter["originating_attorney"] == {"id": 2, "name": "Nina Brooks"}
    assert matter["practice_area"] == {"name": "contract-negotiation"}
    assert matter["notes_count"] == 0
    assert matter["activities_count"] == 1

    first = (await call(server, "get_matter", {"id": 1}))["data"]
    assert first["client"] is None
    assert first["notes_count"] == 1
    assert first["activities_count"] == 0


async def test_unknown_matter_raises(server) -> None:
    with pytest.raises(Exception, match="99"):
        await server.call_tool("get_matter", {"id": 99})
    with pytest.raises(Exception, match="99"):
        await server.call_tool("list_matter_contacts", {"matter_id": 99})


async def test_activities_quantities_in_seconds(server) -> None:
    [activity] = (await call(server, "list_activities"))["data"]
    assert activity["type"] == "TimeEntry"
    assert activity["quantity"] == 5400
    assert activity["quantity_in_hours"] == 1.5
    assert activity["date"] == "2026-03-12"
    assert activity["matter"] == {
        "id": 2,
        "display_number": "00002-BlueHarborLogistics",
    }
    assert activity["user"] == {"id": 3, "name": "Meredith Chao"}

    scoped = (await call(server, "list_activities", {"matter_id": 2}))["data"]
    assert len(scoped) == 1
    assert (await call(server, "list_activities", {"matter_id": 1}))["data"] == []
    by_user = (await call(server, "list_activities", {"user_id": 3}))["data"]
    assert len(by_user) == 1


async def test_activities_page_with_offset_and_capped_limit(server) -> None:
    envelope = await call(server, "list_activities")
    assert envelope["meta"]["paging"] == {"total_entries": 1}
    empty = await call(server, "list_activities", {"offset": 1})
    assert empty["data"] == []
    capped = await call(server, "list_activities", {"limit": 5000})
    assert len(capped["data"]) == 1
    first = await call(server, "list_activities", {"limit": -3})
    assert len(first["data"]) == 1


async def test_notes_from_ticket_comments(server) -> None:
    [note] = (await call(server, "list_notes"))["data"]
    assert note["type"] == "Matter"
    assert note["detail"] == NOTE_BODY
    assert note["subject"] == NOTE_BODY[:60]
    assert note["date"] == "2026-03-12"
    assert note["matter"]["id"] == 1
    assert note["author"] == {"id": 1, "name": "Daniel Reyes"}

    scoped = (await call(server, "list_notes", {"matter_id": 1}))["data"]
    assert len(scoped) == 1
    assert (await call(server, "list_notes", {"matter_id": 2}))["data"] == []


async def test_contacts_orgs_then_externals(server) -> None:
    contacts = (await call(server, "list_contacts"))["data"]
    assert [(c["id"], c["name"], c["type"]) for c in contacts] == [
        (1, "Blue Harbor Logistics", "Company"),
        (2, "Nina Brooks", "Person"),
    ]
    assert contacts[0]["is_client"] is True
    assert contacts[0]["primary_email_address"] is None
    assert contacts[1]["is_client"] is False
    assert contacts[1]["primary_email_address"] == "nina@blueharbor.example.com"

    companies = (await call(server, "list_contacts", {"type": "Company"}))["data"]
    assert [c["name"] for c in companies] == ["Blue Harbor Logistics"]
    hits = (await call(server, "list_contacts", {"query": "nina"}))["data"]
    assert [c["name"] for c in hits] == ["Nina Brooks"]


async def test_matter_contacts(server) -> None:
    contacts = (await call(server, "list_matter_contacts", {"matter_id": 2}))["data"]
    assert [(c["id"], c["name"], c["relationship_name"]) for c in contacts] == [
        (1, "Blue Harbor Logistics", "Client"),
        (2, "Nina Brooks", "Participant"),
    ]
    assert contacts[0]["type"] == "Company"
    assert contacts[0]["is_client"] is True
    assert contacts[1]["type"] == "Person"
    assert contacts[1]["is_client"] is False

    internal_only = (await call(server, "list_matter_contacts", {"matter_id": 1}))[
        "data"
    ]
    assert internal_only == []


async def test_users_subscription_type(server) -> None:
    users = (await call(server, "list_users"))["data"]
    assert [u["id"] for u in users] == [1, 2, 3, 4, 5]
    by_name = {u["name"]: u for u in users}
    assert by_name["Meredith Chao"]["subscription_type"] == "Attorney"
    assert by_name["Omar Diallo"]["subscription_type"] == "NonAttorney"
    assert by_name["Omar Diallo"]["first_name"] == "Omar"
    assert by_name["Omar Diallo"]["last_name"] == "Diallo"
    assert all(u["enabled"] is True for u in users)
    assert (await call(server, "list_users", {"enabled": False}))["data"] == []


async def test_who_am_i_reads_seat_env(server, monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_SEAT", "per-meredith-chao")
    seated = (await call(server, "who_am_i"))["data"]
    assert seated["id"] == 3
    assert seated["name"] == "Meredith Chao"
    assert "seat_unset" not in seated

    monkeypatch.delenv("WORKBENCH_SEAT")
    unseated = (await call(server, "who_am_i"))["data"]
    assert unseated["id"] == 1
    assert unseated["name"] == "Daniel Reyes"
    assert unseated["seat_unset"] is True


CLIO_TOOL_ARGUMENTS = {
    "list_matters": {},
    "get_matter": {"id": 1},
    "list_matter_contacts": {"matter_id": 2},
    "list_contacts": {},
    "list_activities": {},
    "list_notes": {},
    "list_users": {},
    "who_am_i": {},
}


async def test_data_envelope_everywhere(server) -> None:
    for name, arguments in CLIO_TOOL_ARGUMENTS.items():
        envelope = await call(server, name, arguments)
        assert "data" in envelope, name
        if isinstance(envelope["data"], list):
            assert set(envelope["meta"]) == {"paging"}, name


async def test_no_write_verbs_and_no_offstage_leakage(server) -> None:
    tools = await server.list_tools()
    assert {t.name for t in tools} >= set(CLIO_TOOL_ARGUMENTS)
    for tool in tools:
        assert not any(
            verb in tool.name
            for verb in ("send", "create", "update", "delete", "write", "post")
        ), f"clio exposes a write tool in the read-only phase: {tool.name}"
        arguments = CLIO_TOOL_ARGUMENTS.get(tool.name, {})
        result = await server.call_tool(tool.name, arguments)
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        for marker in OFFSTAGE_MARKERS:
            assert marker not in text, f"clio.{tool.name} leaked {marker!r}"

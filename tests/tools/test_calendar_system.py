"""The calendar system: Google Calendar's official MCP read surface over
projected calendar events."""

import json
import sqlite3
from pathlib import Path

import pytest
from projection_fixtures import coherent_events

from workbench.core.events import Event, EventPayload
from workbench.core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarEventUpdatedPayload,
    CalendarResponsePayload,
)
from workbench.core.events.tickets import FieldChange
from workbench.tools.calendar import SYSTEM
from workbench.tools.coherence import check_coherence
from workbench.tools.framework import build_server, project_system

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")

KICKOFF, CLIENT_CALL = "cal-000001", "cal-000002"
DANIEL = "daniel@example.com"
JESS = "jess@example.com"
MEREDITH = "meredith@example.com"
TOM = "tom@example.com"


def calendar_events() -> list[Event]:
    events = coherent_events()
    extra: list[tuple[int, str, EventPayload]] = [
        (
            1000,
            "daniel",
            CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=KICKOFF,
                organizer="per-daniel-reyes",
                title="NDA kickoff",
                start=36000,
                end=39600,
                attendees=("per-daniel-reyes", "per-meredith-chao", "per-tom-okafor"),
                description="Walk the fallback positions.",
            ),
        ),
        (
            1100,
            "meredith",
            CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=CLIENT_CALL,
                organizer="per-meredith-chao",
                title="Acme client call",
                start=122400,
                end=126000,
                attendees=("per-meredith-chao", "per-jess-alvarez"),
                description="Status on the Acme engagement.",
            ),
        ),
        (
            2000,
            "tom",
            CalendarResponsePayload(
                kind="calendar.response",
                calendar_event_id=KICKOFF,
                responder="per-tom-okafor",
                response="decline",
            ),
        ),
        (
            2100,
            "jess",
            CalendarResponsePayload(
                kind="calendar.response",
                calendar_event_id=CLIENT_CALL,
                responder="per-jess-alvarez",
                response="accept",
            ),
        ),
        (
            3000,
            "daniel",
            CalendarEventUpdatedPayload(
                kind="calendar.event.updated",
                calendar_event_id=KICKOFF,
                actor="per-daniel-reyes",
                changes=(
                    FieldChange(
                        field="status",
                        old="scheduled",
                        new="vacated - continued per clerk notice",
                    ),
                    FieldChange(field="title", old="NDA kickoff", new="NDA kickoff II"),
                ),
            ),
        ),
    ]
    base = len(events)
    events += [
        Event(
            seq=base + offset,
            time=time,
            tag=payload.kind,
            source=source,
            payload=payload,
        )
        for offset, (time, source, payload) in enumerate(extra)
    ]
    return events


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "calendar.db"
    project_system(SYSTEM, calendar_events(), path)
    return path


@pytest.fixture
def server(db_path: Path):
    return build_server(SYSTEM, db_path)


async def call(server, name: str, arguments: dict | None = None) -> dict:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


def test_projection_folds_updates_and_responses(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        events = connection.execute(
            "SELECT calendar_event_id, organizer, summary, start_time, end_time, "
            "status FROM calendar_events ORDER BY calendar_event_id"
        ).fetchall()
        attendees = connection.execute(
            "SELECT calendar_event_id, person_id, response_status FROM attendees "
            "ORDER BY calendar_event_id, person_id"
        ).fetchall()
    assert events == [
        (
            KICKOFF,
            "per-daniel-reyes",
            "NDA kickoff II",
            36000,
            39600,
            "vacated - continued per clerk notice",
        ),
        (
            CLIENT_CALL,
            "per-meredith-chao",
            "Acme client call",
            122400,
            126000,
            "confirmed",
        ),
    ]
    assert attendees == [
        (KICKOFF, "per-daniel-reyes", "needsAction"),
        (KICKOFF, "per-meredith-chao", "needsAction"),
        (KICKOFF, "per-tom-okafor", "declined"),
        (CLIENT_CALL, "per-jess-alvarez", "accepted"),
        (CLIENT_CALL, "per-meredith-chao", "needsAction"),
    ]


def test_calendar_projection_is_coherent(tmp_path: Path) -> None:
    state = tmp_path / "state"
    project_system(SYSTEM, calendar_events(), state / "calendar.db")
    assert check_coherence(state, (SYSTEM,)) == ()


async def test_list_events_google_shape(server) -> None:
    payload = await call(server, "list_events")
    assert set(payload) == {"events", "nextPageToken"}
    assert payload["nextPageToken"] is None
    kickoff, client_call = payload["events"]
    assert set(kickoff) == {
        "id",
        "summary",
        "description",
        "status",
        "created",
        "updated",
        "start",
        "end",
        "organizer",
        "attendees",
        "eventType",
    }
    assert kickoff["id"] == KICKOFF
    assert kickoff["summary"] == "NDA kickoff II"
    assert kickoff["description"] == "Walk the fallback positions."
    assert kickoff["start"] == {"dateTime": "2026-03-12T10:00:00-07:00"}
    assert kickoff["end"] == {"dateTime": "2026-03-12T11:00:00-07:00"}
    assert kickoff["organizer"] == {"email": DANIEL, "displayName": "Daniel Reyes"}
    assert kickoff["attendees"] == [
        {
            "email": DANIEL,
            "displayName": "Daniel Reyes",
            "responseStatus": "needsAction",
        },
        {
            "email": MEREDITH,
            "displayName": "Meredith Chao",
            "responseStatus": "needsAction",
        },
        {"email": TOM, "displayName": "Tom Okafor", "responseStatus": "declined"},
    ]
    assert kickoff["status"] == "vacated - continued per clerk notice"
    assert kickoff["eventType"] == "default"
    assert client_call["status"] == "confirmed"
    assert client_call["start"] == {"dateTime": "2026-03-13T10:00:00-07:00"}


async def test_list_events_time_window_and_full_text(server) -> None:
    later = await call(
        server, "list_events", {"startTime": "2026-03-13T00:00:00-07:00"}
    )
    assert [e["id"] for e in later["events"]] == [CLIENT_CALL]
    earlier = await call(
        server, "list_events", {"endTime": "2026-03-13T00:00:00-07:00"}
    )
    assert [e["id"] for e in earlier["events"]] == [KICKOFF]

    by_summary = await call(server, "list_events", {"fullText": "acme"})
    assert [e["id"] for e in by_summary["events"]] == [CLIENT_CALL]
    by_description = await call(server, "list_events", {"fullText": "fallback"})
    assert [e["id"] for e in by_description["events"]] == [KICKOFF]
    by_attendee = await call(server, "list_events", {"fullText": "Tom Okafor"})
    assert [e["id"] for e in by_attendee["events"]] == [KICKOFF]


async def test_list_events_pages(server) -> None:
    first = await call(server, "list_events", {"pageSize": 1})
    assert [e["id"] for e in first["events"]] == [KICKOFF]
    assert first["nextPageToken"] == "1"
    rest = await call(
        server, "list_events", {"pageSize": 1, "pageToken": first["nextPageToken"]}
    )
    assert [e["id"] for e in rest["events"]] == [CLIENT_CALL]
    assert rest["nextPageToken"] is None


async def test_calendar_id_scopes_to_one_person(server) -> None:
    by_email = await call(server, "list_events", {"calendarId": JESS})
    assert [e["id"] for e in by_email["events"]] == [CLIENT_CALL]
    by_person_id = await call(server, "list_events", {"calendarId": "per-tom-okafor"})
    assert [e["id"] for e in by_person_id["events"]] == [KICKOFF]
    with pytest.raises(Exception, match="nobody@example.com"):
        await server.call_tool("list_events", {"calendarId": "nobody@example.com"})


async def test_primary_calendar_follows_the_seat(server, monkeypatch) -> None:
    monkeypatch.setenv("WORKBENCH_SEAT", "per-jess-alvarez")
    mine = await call(server, "list_events")
    assert [e["id"] for e in mine["events"]] == [CLIENT_CALL]
    explicit = await call(server, "list_events", {"calendarId": "primary"})
    assert [e["id"] for e in explicit["events"]] == [CLIENT_CALL]

    calendars = await call(server, "list_calendars")
    primary = [c for c in calendars["calendars"] if c["primary"]]
    assert [c["id"] for c in primary] == [JESS]

    monkeypatch.delenv("WORKBENCH_SEAT")
    everything = await call(server, "list_events")
    assert [e["id"] for e in everything["events"]] == [KICKOFF, CLIENT_CALL]


async def test_list_calendars(server) -> None:
    payload = await call(server, "list_calendars")
    assert set(payload) == {"calendars", "nextPageToken"}
    assert [c["id"] for c in payload["calendars"]] == [DANIEL, JESS, MEREDITH, TOM]
    assert payload["calendars"][0] == {
        "id": DANIEL,
        "summary": "Daniel Reyes",
        "primary": False,
        "accessRole": "reader",
    }


async def test_get_event(server) -> None:
    event = await call(server, "get_event", {"eventId": CLIENT_CALL})
    assert event["id"] == CLIENT_CALL
    assert event["summary"] == "Acme client call"
    assert [a["responseStatus"] for a in event["attendees"]] == [
        "accepted",
        "needsAction",
    ]
    with pytest.raises(Exception, match="cal-999999"):
        await server.call_tool("get_event", {"eventId": "cal-999999"})


CALENDAR_TOOL_ARGUMENTS = {
    "list_events": {},
    "get_event": {"eventId": KICKOFF},
    "list_calendars": {},
}


async def test_surface_is_read_only_and_leaks_nothing(server) -> None:
    tools = await server.list_tools()
    assert sorted(tool.name for tool in tools) == sorted(CALENDAR_TOOL_ARGUMENTS)
    for tool in tools:
        assert not any(
            verb in tool.name
            for verb in ("send", "create", "update", "delete", "write", "post")
        ), f"calendar exposes a write tool in the read-only phase: {tool.name}"
        result = await server.call_tool(tool.name, CALENDAR_TOOL_ARGUMENTS[tool.name])
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        for marker in OFFSTAGE_MARKERS:
            assert marker not in text, f"calendar.{tool.name} leaked {marker!r}"

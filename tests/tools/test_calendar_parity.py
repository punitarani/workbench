"""Calendar surface parity: the official nine tools and their write semantics."""

import json
from pathlib import Path

import pytest

from workbench.core.events import Event
from workbench.core.events.calendar import CalendarEventScheduledPayload
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.tools.calendar import SYSTEM
from workbench.tools.framework import build_server, project_system

# The official Google Calendar MCP server as captured 2026-08-14.
OFFICIAL_TOOLS = frozenset(
    {
        "list_events",
        "get_event",
        "list_calendars",
        "search_events",
        "suggest_time",
        "create_event",
        "update_event",
        "delete_event",
        "respond_to_event",
    }
)
HOUR = 3600


def _events() -> list[Event]:
    events: list[Event] = [
        Event(
            seq=0,
            event_id="evt-000000",
            time=0,
            tag="sim.run.started",
            source="gm",
            payload=SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-calendar-parity",
                seed_root=3,
                workplace_id="calder",
                config_hash="0" * 64,
                schema_version=1,
                epoch="2026-01-05T00:00:00-08:00",
                timezone="America/Los_Angeles",
            ),
        )
    ]
    seq = 0
    for person_id, name, email in (
        ("per-ana", "Ana Reyes", "ana@calder.example"),
        ("per-ben", "Ben Ito", "ben@calder.example"),
    ):
        seq += 1
        events.append(
            Event(
                seq=seq,
                event_id=f"evt-{seq:06d}",
                time=0,
                tag="person.record",
                source="gm",
                payload=PersonRecordPayload(
                    kind="person.record",
                    person_id=person_id,
                    name=name,
                    email_address=email,
                    title="Accountant",
                    department="Tax",
                    affiliation="internal",
                    manager=None,
                    timezone="America/Los_Angeles",
                ),
            )
        )
    seq += 1
    events.append(
        Event(
            seq=seq,
            event_id=f"evt-{seq:06d}",
            time=9 * HOUR,
            tag="calendar.event.scheduled",
            source="per-ana",
            payload=CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id="cal-000001",
                organizer="per-ana",
                title="Tax group huddle",
                start=10 * HOUR,
                end=11 * HOUR,
                attendees=["per-ana", "per-ben"],
                description="Weekly queue review.",
            ),
        )
    )
    return events


@pytest.fixture
def server(tmp_path: Path):
    db_path = tmp_path / "calendar.db"
    project_system(SYSTEM, _events(), db_path)
    return build_server(SYSTEM, db_path)


async def call(server, name: str, **arguments) -> dict:
    result = await server.call_tool(name, arguments)
    assert not result.is_error, result
    [payload] = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
    return payload


async def test_tool_inventory_matches_the_official_surface(server) -> None:
    listed = {tool.name for tool in await server.list_tools()}
    assert listed == OFFICIAL_TOOLS


class TestListingDrift:
    async def test_order_by_accepts_the_official_vocabulary(self, server) -> None:
        for value in ("default", "startTime", "startTimeDesc", "lastModified"):
            payload = await call(server, "list_events", orderBy=value)
            assert payload["events"]

    async def test_response_carries_timezone_and_access_role(self, server) -> None:
        payload = await call(server, "list_events")
        assert payload["timeZone"]
        assert payload["accessRole"] in ("owner", "reader")

    async def test_event_type_filter(self, server) -> None:
        assert (await call(server, "list_events", eventType=["DEFAULT"]))["events"]
        assert not (await call(server, "list_events", eventType=["BIRTHDAY"]))["events"]

    async def test_search_events(self, server) -> None:
        found = await call(server, "search_events", query="huddle")
        assert [event["id"] for event in found["events"]] == ["cal-000001"]
        assert not (await call(server, "search_events", query="zzz"))["events"]


class TestRsvp:
    async def test_respond_records_the_answer(self, server) -> None:
        """The tool whose absence froze every v1 invitation at needsAction."""

        before = await call(server, "get_event", eventId="cal-000001")
        assert {a["responseStatus"] for a in before["attendees"]} == {"needsAction"}
        after = await call(
            server,
            "respond_to_event",
            eventId="cal-000001",
            responseStatus="accepted",
            calendarId="ben@calder.example",
        )
        answers = {a["email"]: a["responseStatus"] for a in after["attendees"]}
        assert answers["ben@calder.example"] == "accepted"
        assert answers["ana@calder.example"] == "needsAction"

    async def test_declining_is_recorded_too(self, server) -> None:
        after = await call(
            server,
            "respond_to_event",
            eventId="cal-000001",
            responseStatus="declined",
            calendarId="ben@calder.example",
        )
        answers = {a["email"]: a["responseStatus"] for a in after["attendees"]}
        assert answers["ben@calder.example"] == "declined"


class TestWrites:
    async def test_create_event_with_attendees_and_recurrence(self, server) -> None:
        created = await call(
            server,
            "create_event",
            summary="Monthly close review",
            startTime="2026-01-06T14:00:00-08:00",
            endTime="2026-01-06T15:00:00-08:00",
            calendarId="ana@calder.example",
            attendees=[{"email": "ben@calder.example"}],
            recurrenceData=["RRULE:FREQ=MONTHLY;BYMONTHDAY=6"],
        )
        assert created["summary"] == "Monthly close review"
        assert created["recurrence"] == ["RRULE:FREQ=MONTHLY;BYMONTHDAY=6"]
        organizer = [
            a for a in created["attendees"] if a["email"] == "ana@calder.example"
        ]
        assert organizer[0]["responseStatus"] == "accepted", (
            "the organizer accepts their own event"
        )
        listed = await call(server, "list_events")
        assert created["id"] in [event["id"] for event in listed["events"]]

    async def test_create_rejects_a_backwards_window(self, server) -> None:
        with pytest.raises(Exception):  # noqa: B017 - MCP wraps as ToolError
            await server.call_tool(
                "create_event",
                {
                    "summary": "Impossible",
                    "startTime": "2026-01-06T15:00:00-08:00",
                    "endTime": "2026-01-06T14:00:00-08:00",
                },
            )

    async def test_update_preserves_duration_when_only_start_moves(
        self, server
    ) -> None:
        updated = await call(
            server,
            "update_event",
            eventId="cal-000001",
            startTime="2026-01-05T14:00:00-08:00",
        )
        assert updated["start"]["dateTime"].startswith("2026-01-05T14:00")
        assert updated["end"]["dateTime"].startswith("2026-01-05T15:00")

    async def test_update_adds_and_removes_attendees_as_deltas(self, server) -> None:
        removed = await call(
            server,
            "update_event",
            eventId="cal-000001",
            removedAttendeeEmails=["ben@calder.example"],
        )
        assert [a["email"] for a in removed["attendees"]] == ["ana@calder.example"]
        restored = await call(
            server,
            "update_event",
            eventId="cal-000001",
            addedAttendees=[{"email": "ben@calder.example"}],
        )
        assert len(restored["attendees"]) == 2

    async def test_delete_cancels_rather_than_erases(self, server) -> None:
        cancelled = await call(server, "delete_event", eventId="cal-000001")
        assert cancelled["status"] == "cancelled"
        still_there = await call(server, "get_event", eventId="cal-000001")
        assert still_there["status"] == "cancelled"


class TestSuggestTime:
    async def test_avoids_a_busy_block(self, server) -> None:
        slots = await call(
            server,
            "suggest_time",
            attendeeEmails=["ana@calder.example"],
            startTime="2026-01-05T09:00:00-08:00",
            endTime="2026-01-05T17:00:00-08:00",
            durationMinutes=60,
        )
        starts = [slot["start"]["dateTime"] for slot in slots["timeSlots"]]
        assert starts, "there is free time on this day"
        assert not any(start.startswith("2026-01-05T10:00") for start in starts), (
            "10:00-11:00 is taken by the huddle"
        )

    async def test_excludes_weekends_by_default(self, server) -> None:
        slots = await call(
            server,
            "suggest_time",
            attendeeEmails=["ana@calder.example"],
            # 2026-01-10 is a Saturday.
            startTime="2026-01-10T09:00:00-08:00",
            endTime="2026-01-10T17:00:00-08:00",
        )
        assert slots["timeSlots"] == []

"""The end-of-day timesheet turn: a day of time in one call."""

import pytest

from workbench.core.actions import TimesheetActionSpec
from workbench.core.events import Event
from workbench.core.events.control import SimTimesheetPayload
from workbench.core.footprint import RULES, footprint_of
from workbench.core.intents import TimesheetEntry, TimesheetIntent
from workbench.simulation.gm.grounded import DayPlan, GroundedGm, IntentRejection


def _gm(tickets: dict[str, tuple[str, str]]) -> GroundedGm:
    from workbench.simulation.gm.grounded import TicketVocabulary

    gm = GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    gm.set_bill_rates({"per-ana": 27500})
    for ticket_id, (title, assignee) in tickets.items():
        gm.world.tickets[ticket_id] = {
            "title": title,
            "description": title,
            "assignee": assignee,
            "status": "Open",
            "priority": "Normal",
        }
    return gm


def _event() -> Event:
    return Event(
        seq=1,
        event_id="evt-000001",
        time=0,
        tag="sim.timesheet",
        source="gm",
        payload=SimTimesheetPayload(
            kind="sim.timesheet", entity="ana", day="2026-01-05"
        ),
    )


class TestGrounding:
    def test_a_day_of_entries_becomes_a_day_of_events(self) -> None:
        gm = _gm({"tkt-000001": ("Kestrel close", "per-ana")})
        intent = TimesheetIntent(
            entries=(
                TimesheetEntry(ticket_ref="tkt-000001", minutes=37, note="CAM tie-out"),
                TimesheetEntry(
                    ticket_ref="tkt-000001",
                    minutes=45,
                    note="Internal training",
                    billable=False,
                    category="cpe",
                ),
            )
        )
        drafts = gm._ground_timesheet("ana", "per-ana", intent, _event(), 0)
        assert [d.tag for d in drafts] == ["work.time.logged", "work.time.logged"]
        assert [d.payload.minutes for d in drafts] == [37, 45]
        assert [d.payload.billable for d in drafts] == [True, False]
        # The rate comes from the persona's profile, never from the model.
        assert {d.payload.rate_cents for d in drafts} == {27500}

    def test_unknown_engagements_are_dropped_with_a_note(self) -> None:
        gm = _gm({"tkt-000001": ("Kestrel close", "per-ana")})
        intent = TimesheetIntent(
            entries=(
                TimesheetEntry(ticket_ref="tkt-000001", minutes=30, note="real"),
                TimesheetEntry(ticket_ref="tkt-999999", minutes=30, note="invented"),
            )
        )
        drafts = gm._ground_timesheet("ana", "per-ana", intent, _event(), 0)
        tags = [d.tag for d in drafts]
        assert tags == ["work.time.logged", "sim.gm.note"]
        assert "tkt-999999" in drafts[-1].payload.note
        assert drafts[-1].payload.entity == "ana", "the note routes back to its author"

    def test_a_wholly_invented_timesheet_is_rejected(self) -> None:
        gm = _gm({"tkt-000001": ("Kestrel close", "per-ana")})
        intent = TimesheetIntent(
            entries=(
                TimesheetEntry(ticket_ref="tkt-999999", minutes=30, note="invented"),
            )
        )
        with pytest.raises(IntentRejection) as caught:
            gm._ground_timesheet("ana", "per-ana", intent, _event(), 0)
        assert "tkt-999999" in caught.value.reason

    def test_an_empty_timesheet_grounds_to_nothing(self) -> None:
        gm = _gm({"tkt-000001": ("Kestrel close", "per-ana")})
        drafts = gm._ground_timesheet(
            "ana", "per-ana", TimesheetIntent(entries=()), _event(), 0
        )
        assert drafts == ()


class TestEntryBounds:
    def test_minutes_are_bounded_to_a_plausible_entry(self) -> None:
        # Six minutes is the classic minimum increment; ten hours is a
        # long day on one engagement and a hard ceiling for one line.
        with pytest.raises(ValueError):
            TimesheetEntry(ticket_ref="tkt-1", minutes=5, note="too short")
        with pytest.raises(ValueError):
            TimesheetEntry(ticket_ref="tkt-1", minutes=601, note="too long")

    def test_category_defaults_to_client_work(self) -> None:
        entry = TimesheetEntry(ticket_ref="tkt-1", minutes=30, note="x")
        assert entry.category == "client" and entry.billable is True


class TestScheduling:
    def test_the_cohort_is_off_by_default(self) -> None:
        assert DayPlan.model_fields["timesheets"].default is False, (
            "a v1 recording has to replay byte-identically, so the new "
            "cohort cannot mint unless a spec asks for it"
        )

    def test_the_action_spec_carries_the_persona_engagements(self) -> None:
        spec = TimesheetActionSpec(
            day="2026-01-05", engagements=("tkt-000001 Kestrel close",)
        )
        assert spec.kind == "timesheet"
        assert "Kestrel close" in spec.engagements[0]

    def test_the_turn_has_a_footprint_rule(self) -> None:
        assert "sim.timesheet" in RULES
        footprint = footprint_of(
            SimTimesheetPayload(kind="sim.timesheet", entity="ana", day="2026-01-05")
        )
        other = footprint_of(
            SimTimesheetPayload(kind="sim.timesheet", entity="ben", day="2026-01-05")
        )
        assert not footprint.conflicts(other), (
            "two people writing up their own time do not contend, so the cohort batches"
        )

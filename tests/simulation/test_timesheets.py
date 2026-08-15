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


class TestTimeflow:
    def test_every_intent_kind_has_a_duration_rule(self) -> None:
        """The gap that killed the first v2 mini-epoch.

        A new intent without a rule fell through the match as None and blew
        up later inside delivery quantization, in a traceback that named
        neither the intent nor the rule table.
        """

        import inspect
        import typing

        from workbench.core.intents import ActionIntent
        from workbench.simulation.gm import timeflow

        source = inspect.getsource(timeflow.intent_duration)
        members = typing.get_args(typing.get_args(ActionIntent)[0])
        assert len(members) > 10, "the intent union should not have shrunk"
        missing = [
            member.__name__
            for member in members
            if f"case {member.__name__}()" not in source
        ]
        assert not missing, f"intents with no duration rule: {missing}"

    def test_an_unruled_intent_fails_loudly(self) -> None:
        from workbench.simulation.gm.timeflow import intent_duration

        class Unruled:
            kind = "unruled"

        with pytest.raises(ValueError, match="no duration rule"):
            intent_duration(Unruled())

    def test_a_timesheet_costs_time_proportional_to_its_lines(self) -> None:
        from workbench.simulation.gm.timeflow import intent_duration

        short = TimesheetIntent(
            entries=(TimesheetEntry(ticket_ref="tkt-1", minutes=30, note="x"),)
        )
        long = TimesheetIntent(
            entries=tuple(
                TimesheetEntry(ticket_ref="tkt-1", minutes=30, note="x")
                for _ in range(8)
            )
        )
        assert intent_duration(short) < intent_duration(long)


class TestCognitionContract:
    def test_every_dispatched_turn_binds_an_lm(self) -> None:
        """The bug that made the first flagged mini-epoch produce nothing.

        A turn dispatched straight from ``get_action_attempt`` owns its own
        LM context. Without one the predictor call raises, the degradation
        path meant for unparseable output swallows it, and the turn quietly
        produces nothing — 16 timesheet turns made zero LM calls and logged
        zero hours. Helpers called *inside* an established context are fine;
        these entry points are not.
        """

        import inspect

        from workbench.simulation.persona.actor import ProfessionalActorAct

        dispatched = ("_timesheet", "_reflect", "_plan", "_meeting_turn")
        offenders = [
            name
            for name in dispatched
            if "dspy.context("
            not in inspect.getsource(getattr(ProfessionalActorAct, name))
        ]
        assert not offenders, f"dispatched turns with no LM bound: {offenders}"

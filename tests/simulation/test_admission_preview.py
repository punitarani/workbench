"""Batch admission can only serialize what it can see.

``observers_for`` is the pure preview the engine uses to decide whether two
queued events may run in the same batch. Its contract is to be a *superset*
of what ``route`` and ``next_acting`` will name. When a payload kind is
missing from it, the preview says "concerns nobody", two events for the same
person are admitted together, and the entity phase machine raises
``illegal phase transition PRE_ACT -> PRE_ACT`` mid-run.

That happened twice: ``work.time.logged`` (a timesheet turn emits a whole
day at once) and ``sim.meeting.turn``. This test compares the three match
statements so the next one fails here instead of an hour into a recording.
"""

import inspect
import re

from simulation.gm.grounded import GroundedGm


def _cases(source: str) -> set[str]:
    """Payload classes named by ``case X()`` arms, including grouped arms."""

    return set(re.findall(r"([A-Za-z]+Payload)\(\)", source))


def test_observers_for_covers_everything_routing_names() -> None:
    routed = _cases(inspect.getsource(GroundedGm.route)) | _cases(
        inspect.getsource(GroundedGm.next_acting)
    )
    previewed = _cases(inspect.getsource(GroundedGm.observers_for))
    missing = sorted(routed - previewed)
    assert not missing, (
        "these payload kinds are routed to entities but invisible to batch "
        f"admission, so two of them can act one entity at once: {missing}"
    )


def test_the_preview_is_documented_as_a_superset() -> None:
    """The superset property is what makes an over-broad preview safe."""

    doc = inspect.getdoc(GroundedGm.observers_for) or ""
    assert "superset" in doc.lower()


def test_time_entries_name_their_author() -> None:
    from core.events.work import TimeLoggedPayload

    gm = GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=__import__(
            "simulation.gm.grounded", fromlist=["TicketVocabulary"]
        ).TicketVocabulary(statuses=("Open",), priorities=("N",), ticket_types=("e",)),
    )
    payload = TimeLoggedPayload(
        kind="work.time.logged",
        person_id="per-ana",
        ticket_id="tkt-000001",
        minutes=30,
        note="n",
        rate_cents=None,
        billable=True,
    )
    assert gm.observers_for(payload) == ("ana",)


def test_meeting_turns_name_their_speaker() -> None:
    from core.events.meetings import SimMeetingTurnPayload

    gm = GroundedGm(
        entity_for_person={"per-ana": "ana"},
        ticket_vocabulary=__import__(
            "simulation.gm.grounded", fromlist=["TicketVocabulary"]
        ).TicketVocabulary(statuses=("Open",), priorities=("N",), ticket_types=("e",)),
    )
    payload = SimMeetingTurnPayload(
        kind="sim.meeting.turn",
        meeting_id="mtg-000001",
        speaker="ana",
        attendees=("ana", "ben"),
        turn_index=0,
    )
    assert gm.observers_for(payload) == ("ana",)


class TestMalformedDraftsDegrade:
    """A model that fills a draft badly must not end the run.

    Two runs died this way: an empty recipient list, then a missing
    summary. Patching fields one at a time is how the second happened, so
    the guard is at the parse boundary instead — any validation failure in
    a draft becomes a note the persona writes to itself, visible in the
    log and remembered, while transport, budget, and cassette failures
    still raise.
    """

    def test_the_boundary_catches_validation_errors(self) -> None:
        import inspect

        from simulation.persona.actor import ProfessionalActorAct

        source = inspect.getsource(ProfessionalActorAct.get_action_attempt)
        assert "except ValidationError" in source
        assert "self._route(" in source

    def test_loud_failures_are_still_loud(self) -> None:
        """Only content degrades; the loud-failure contract is intact."""

        import inspect

        from simulation.persona import actor

        source = inspect.getsource(actor)
        assert "CassetteMissError" in source
        assert "LMBudgetExceededError" in source
        assert "LMTransportError" in source

    def test_the_note_names_the_missing_field(self) -> None:
        from pydantic import BaseModel, ValidationError

        from simulation.persona.actor import _first_missing

        class Draft(BaseModel):
            summary: str

        try:
            Draft()
        except ValidationError as error:
            described = _first_missing(error)
        assert "summary" in described

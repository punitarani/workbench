"""A transcript may not contain someone who was not in the room.

`_ground_meeting_speak` carries two refusals and **nothing in this suite
referenced `MeetingSpeakIntent` at all** until this file. Every transcript
turn in every recording goes through that function — 510 transcripts in the
v7 record so far — and both of its guards could be deleted with the whole
suite still green.

What they prevent is not a crash. `_ground_meeting_speak` appends the turn
to `progress.turns` and writes the meeting back, so without the attendee
check a persona speaks in a room they never entered, the words land in the
transcript, and the projection serves them beside everyone else's. Nothing
downstream distinguishes them: the transcript is the record.

That matters more here than in most engines, because a task in this dataset
grades what was said in a meeting and by whom. A speaker who was not there
is not a fidelity blemish, it is a wrong answer key.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.meetings import SimMeetingConvenePayload
from core.intents import MeetingSpeakIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary


def _gm() -> GroundedGm:
    return GroundedGm(
        entity_for_person={"per-ana": "ana", "per-bo": "bo", "per-cy": "cy"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )


def _event(seq: int = 1) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=seq * 60,
        tag="sim.meeting.convene",
        source="gm",
        caused_by=None,
        payload=SimMeetingConvenePayload(
            kind="sim.meeting.convene",
            meeting_id="mtg-000001",
            calendar_event_id="cal-000001",
            title="Docket call",
            description="the week's deadlines",
            attendees=("ana", "bo"),
            duration_seconds=1800,
        ),
    )


def _convened() -> GroundedGm:
    gm = _gm()
    gm.world.apply(_event())
    return gm


def _speak(ref: str = "mtg-000001") -> MeetingSpeakIntent:
    return MeetingSpeakIntent(
        kind="meeting_speak",
        meeting_ref=ref,
        text="I'll have it by Thursday.",
        yields=False,
    )


def test_an_attendee_may_speak() -> None:
    """Guard the guard: if nothing can speak, the refusals below prove nothing."""

    gm = _convened()
    drafts = gm._ground_meeting_speak("ana", _speak(), _event(2), 0)
    assert drafts
    assert gm.world.meetings["mtg-000001"].turns


def test_someone_not_in_the_room_is_refused() -> None:
    gm = _convened()
    with pytest.raises(IntentRejection, match="not in"):
        gm._ground_meeting_speak("cy", _speak(), _event(2), 0)


def test_the_refused_turn_does_not_reach_the_transcript() -> None:
    """The consequence, which the refusal alone does not state.

    A rejection that still appended would leave the words in the record and
    only complain about them.
    """

    gm = _convened()
    with pytest.raises(IntentRejection):
        gm._ground_meeting_speak("cy", _speak(), _event(2), 0)
    assert gm.world.meetings["mtg-000001"].turns == ()


def test_a_meeting_that_is_not_open_is_refused() -> None:
    gm = _convened()
    with pytest.raises(IntentRejection, match="no open meeting"):
        gm._ground_meeting_speak("ana", _speak("mtg-999999"), _event(2), 0)


def test_the_refusal_names_the_meeting_it_could_not_find() -> None:
    """An operator reading a rejection log needs the ref, not the fact.

    `sim.gm.note` records these, and "no open meeting" without the id is
    unactionable in a run with hundreds of them.
    """

    gm = _convened()
    with pytest.raises(IntentRejection) as raised:
        gm._ground_meeting_speak("ana", _speak("mtg-999999"), _event(2), 0)
    assert "mtg-999999" in str(raised.value)

"""C5: meetings convene, turns alternate with private knowledge, and the
transcript — the payload nothing ever constructed before — finally lands."""

from pathlib import Path

from mini_workplace import make_spec
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.run import run_workplace
from simulation.workplace.spec import PersonSpec, SeedCalendarEvent

SPEAK = (
    "[[ ## utterance ## ]]\n"
    '{"text": "Quick status: the redline is out the door.", "yields": true}\n\n'
    "[[ ## completed ## ]]"
)


class MeetingAwareLM:
    def __init__(self) -> None:
        self._speak = SequenceLM([SPEAK])
        self._idle = SequenceLM([DECIDE_IDLE_FALLBACK])

    async def complete(self, request):
        prompt = request.messages[-1].content
        if "[[ ## utterance ## ]]" in prompt:
            return await self._speak.complete(request)
        return await self._idle.complete(request)


def _two_persona_spec():
    from mini_workplace import ann_params

    bob = PersonSpec(
        person_id="per-bob-osei",
        name="Bob Osei",
        email_address="bob@mini.example",
        title="Counsel",
        department="Legal",
        manager=None,
        affiliation="internal",
        persona=ann_params().model_copy(
            update={"person_id": "per-bob-osei", "name": "Bob Osei"}
        ),
    )
    spec = make_spec(
        seed_calendar=(
            SeedCalendarEvent(
                organizer="per-ann-liu",
                title="Morning sync",
                start_clock="10:00",
                end_clock="10:15",
                attendees=("per-ann-liu", "per-bob-osei"),
                description="Status and blockers.",
            ),
        ),
    )
    return spec.model_copy(update={"people": (*spec.people, bob)})


async def test_seed_calendar_meeting_produces_transcript(tmp_path: Path) -> None:
    result = await run_workplace(
        _two_persona_spec(),
        seed=Seed(root=42),
        out_dir=tmp_path / "run",
        inner_lm=MeetingAwareLM(),
        model="test/model",
    )
    assert result.reason in ("quiescent", "end_time")
    events = read_events(tmp_path / "run" / "world.jsonl")
    assert validate_events(events).ok

    convenes = [e for e in events if e.tag == "sim.meeting.convene"]
    turns = [e for e in events if e.tag == "sim.meeting.turn"]
    transcripts = [e for e in events if e.tag == "meeting.transcript"]
    assert len(convenes) == 1, "the calendar event convened"
    assert len(transcripts) == 1, "the meeting produced a transcript"
    assert len(turns) == len(transcripts[0].payload.turns), (
        "one turn event per utterance"
    )
    payload = transcripts[0].payload
    assert set(payload.attendees) == {"per-ann-liu", "per-bob-osei"}
    assert all(
        turn.text == "Quick status: the redline is out the door."
        for turn in payload.turns
    )
    assert len(payload.turns) == 2, "both spoke once, both yielded"
    assert int(payload.ended) > int(payload.started)

    # Wake suppression: no persona acted on a wake landing inside the
    # meeting window (between convene and transcript).
    convene_time = int(convenes[0].time)
    transcript_time = int(transcripts[0].time)
    for event in events:
        if event.tag == "sim.wake" and convene_time < int(event.time) < transcript_time:
            wake_actions = [
                other
                for other in events
                if other.caused_by == event.event_id and other.tag != "sim.gm.note"
            ]
            assert wake_actions == [], "mid-meeting wakes grant no turns"

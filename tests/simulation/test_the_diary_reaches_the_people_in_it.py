"""A meeting nobody observes is a meeting nobody remembers.

`memory_stream` has handlers waiting for both halves of the diary —
"Meeting scheduled: {title}" at importance 5, "Meeting held with N turns"
at importance 8 — and `GroundedGm.route` delivered neither, so in a firm
whose days are meetings, no persona remembered a single one. Only the
genesis seed calendar was ever visible, and that is because genesis is
observed wholesale rather than routed.

The same gap made RSVPs loop. `_pending_all` clears an invitation when it
sees the person's own response; the response was routed to nobody, so it
never arrived, so the invitation stayed pending forever. Measured across
two recorded days: **203 of 278 responses were redundant**, one person
answering one invitation fifteen times. The loop consumed the turns that
would otherwise have been chat, which is the only reason it was noticed.

**These tests exist because the previous ones tested the wrong half.**
`test_invitations_reach_their_recipient` fed a `calendar.response` event
straight into working memory and asserted the invitation cleared. It
passed, and the world still looped, because the filter was never the
problem — delivery was. So every test here goes through `route`, which is
the thing that was broken.
"""

from core.events import Event
from core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarResponsePayload,
)
from core.events.meetings import MeetingTranscriptPayload
from core.events.people import PersonRecordPayload
from simulation.gm.grounded import GroundedGm, TicketVocabulary

PEOPLE = (
    ("per-ana", "Ana Reyes"),
    ("per-cecile", "Cecile Marchand"),
    ("per-dev", "Dev Kaur"),
)


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={pid: pid.removeprefix("per-") for pid, _ in PEOPLE},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    for seq, (person_id, name) in enumerate(PEOPLE, start=1):
        gm.world.apply(
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
                    email_address=f"{name.split()[0].lower()}@example.test",
                    title="Associate",
                    department="Litigation",
                    manager=None,
                    affiliation="internal",
                    timezone="UTC",
                ),
            )
        )
    return gm


def _event(payload, seq: int = 90) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=1000,
        tag=payload.kind,
        source="gm",
        payload=payload,
    )


async def test_an_invitation_reaches_everyone_invited() -> None:
    gm = _gm()
    payload = CalendarEventScheduledPayload(
        kind="calendar.event.scheduled",
        calendar_event_id="cal-000001",
        organizer="per-ana",
        title="Vantage redline walkthrough",
        start=200_000,
        end=203_600,
        attendees=("per-ana", "per-cecile", "per-dev"),
        description="Walk the redlines together.",
    )
    assert set(await gm.route(_event(payload))) == {"ana", "cecile", "dev"}


async def _booked(gm, event_id: str = "cal-000001", organizer: str = "per-ana"):
    """Put a real meeting in the world, so the organizer is known."""

    await gm.route(
        _event(
            CalendarEventScheduledPayload(
                kind="calendar.event.scheduled",
                calendar_event_id=event_id,
                organizer=organizer,
                title="Vantage redline walkthrough",
                start=200_000,
                end=203_600,
                attendees=(organizer, "per-cecile", "per-dev"),
                description="Walk the redlines together.",
            ),
            seq=80,
        )
    )


async def test_a_person_observes_their_own_rsvp() -> None:
    """The loop that made 203 of 278 responses redundant.

    An actor who never sees their own answer gives it again, exactly as the
    ticket and document cases in `route` already say in their comment.
    """

    gm = _gm()
    await _booked(gm)
    payload = CalendarResponsePayload(
        kind="calendar.response",
        calendar_event_id="cal-000001",
        responder="per-cecile",
        response="decline",
    )
    assert "cecile" in await gm.route(_event(payload))


async def test_the_organizer_hears_the_answer() -> None:
    """A decline nobody hears is not a decline.

    Without this the firm records the answer and the person who booked the
    meeting never learns it, so nothing is ever moved and no task can ask
    what was rescheduled or why. Measured in a sample of 278 responses:
    29 declines, none of which reached an organizer.
    """

    gm = _gm()
    await _booked(gm, organizer="per-ana")
    payload = CalendarResponsePayload(
        kind="calendar.response",
        calendar_event_id="cal-000001",
        responder="per-cecile",
        response="decline",
    )
    assert set(await gm.route(_event(payload))) == {"cecile", "ana"}


async def test_an_answer_to_a_forgotten_meeting_reaches_its_author() -> None:
    """No organizer on record must degrade, not crash."""

    gm = _gm()
    payload = CalendarResponsePayload(
        kind="calendar.response",
        calendar_event_id="cal-999999",
        responder="per-cecile",
        response="accept",
    )
    assert await gm.route(_event(payload)) == ("cecile",)


async def test_a_transcript_reaches_everyone_who_was_there() -> None:
    """Including the people who never spoke — they were still in the room."""

    gm = _gm()
    payload = MeetingTranscriptPayload(
        kind="meeting.transcript",
        meeting_id="mtg-000001",
        calendar_event_id="cal-000001",
        attendees=("per-ana", "per-cecile", "per-dev"),
        started=1000,
        ended=2000,
        turns=(),
    )
    assert set(await gm.route(_event(payload))) == {"ana", "cecile", "dev"}


async def test_the_batch_preview_still_covers_routing() -> None:
    """`observers_for` is a documented superset of `route`.

    Adding a case to one and not the other lets two events that preview as
    nobody's business land in a single batch and act one entity twice. The
    tree already has a test for the general property; this pins the three
    cases that were just added, because that general test reads source with
    a regex and a regex is a poor guard for the thing it is guarding.
    """

    gm = _gm()
    for payload in (
        CalendarEventScheduledPayload(
            kind="calendar.event.scheduled",
            calendar_event_id="cal-000001",
            organizer="per-ana",
            title="t",
            start=200_000,
            end=203_600,
            attendees=("per-ana", "per-cecile"),
            description="d",
        ),
        CalendarResponsePayload(
            kind="calendar.response",
            calendar_event_id="cal-000001",
            responder="per-cecile",
            response="accept",
        ),
        MeetingTranscriptPayload(
            kind="meeting.transcript",
            meeting_id="mtg-000001",
            calendar_event_id="cal-000001",
            attendees=("per-ana",),
            started=1,
            ended=2,
            turns=(),
        ),
    ):
        routed = set(await gm.route(_event(payload)))
        previewed = set(gm.observers_for(payload))
        assert routed <= previewed, (
            f"{type(payload).__name__}: route says {routed}, preview says "
            f"{previewed} — the preview must be a superset"
        )
        assert routed, f"{type(payload).__name__} reaches nobody"


async def test_someone_outside_the_firm_is_not_routed_to() -> None:
    """Attendees can include clients and opposing counsel, who have no seat."""

    gm = _gm()
    payload = CalendarEventScheduledPayload(
        kind="calendar.event.scheduled",
        calendar_event_id="cal-000002",
        organizer="per-ana",
        title="Client call",
        start=200_000,
        end=203_600,
        attendees=("per-ana", "per-nobody-at-all"),
        description="d",
    )
    assert set(await gm.route(_event(payload))) == {"ana"}


async def test_the_organizer_map_survives_a_resume() -> None:
    """A seventeen-hour recording resumes from a checkpoint.

    `calendar_organizers` lives in world state, which is serialised at
    every one. A resume that dropped it would keep routing RSVPs to the
    responder and stop routing them to the organizer from that point on —
    a world where declines reach somebody for forty days and nobody
    afterwards, with nothing in the record marking the seam.

    This is the mutation the other tests in this file missed: removing the
    restore line left all of them green.
    """

    gm = _gm()
    await _booked(gm, event_id="cal-000001", organizer="per-ana")

    restored = _gm()
    restored.set_state(gm.get_state())
    assert restored.world.calendar_organizers["cal-000001"] == "per-ana"

    payload = CalendarResponsePayload(
        kind="calendar.response",
        calendar_event_id="cal-000001",
        responder="per-cecile",
        response="decline",
    )
    assert set(await restored.route(_event(payload, seq=91))) == {"cecile", "ana"}

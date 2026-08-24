"""A reply's recipients are in the thread it replies to.

The referee refused any email whose draft named no recipient, and the
check ran before the thread was even resolved. Measured over 43 recorded
days: **290 refused against 469 delivered — 38.2% of every attempted
email**, across 27 senders, half of every rejection in the run. Two thirds
of the refusals carried a `thread_ref`, so the recipients were sitting in
the thread the persona was replying to.

The damage was not only volume. Of the threads that lost a reply **83%
contained a question**, and **48.5% of every question-bearing thread lost
at least one**. A firm that looked like it ignored half the questions put
to it was a firm whose answers the referee had refused — and a task built
on "which questions went unanswered" would have been measuring the engine.

The design was not careless: `EmailDraft.to` defaults to empty on purpose,
so a model that omits recipients meets an instructive rejection instead of
failing schema parsing and taking the run down. That is right about
robustness. What was never measured was the yield, and both can be had.

Same lesson as `CalendarScheduleSpec` asking a model for raw seconds: do
not ask for what is derivable, derive it.
"""

from core.events import Event
from core.events.control import SimWakePayload
from core.events.email import EmailMessagePayload
from core.events.people import PersonRecordPayload
from core.intents import EmailDraft, EmailIntent
from core.simtime import SimDuration
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary

PEOPLE = (
    ("per-ana", "Ana Reyes"),
    ("per-cecile", "Cecile Marchand"),
    ("per-dev", "Dev Kaur"),
)
THREAD = "thr-000001"


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


def _opening(gm: GroundedGm) -> None:
    gm.world.apply(
        Event(
            seq=50,
            event_id="evt-000050",
            time=100,
            tag="email.message",
            source="ana",
            payload=EmailMessagePayload(
                kind="email.message",
                message_id="msg-000001",
                thread_id=THREAD,
                in_reply_to=None,
                sender="per-ana",
                to=("per-cecile",),
                cc=("per-dev",),
                subject="Vantage NDA",
                body="Can you look at the fallback positions?",
                attachments=(),
            ),
        )
    )


def _reply(thread_ref: str | None, to: tuple[str, ...] = ()) -> EmailIntent:
    return EmailIntent(
        thread_ref=thread_ref,
        reply_to_ref=None,
        draft=EmailDraft(
            to=to,
            cc=(),
            subject="Re: Vantage NDA",
            body="Looking now.",
            summary="Said I would look.",
        ),
    )


def _event() -> Event:
    """The event the grounding is caused by. Only its id is used."""

    return Event(
        seq=90,
        event_id="evt-000090",
        time=200,
        tag="sim.wake",
        source="gm",
        payload=SimWakePayload(kind="sim.wake", entity="cecile"),
    )


def test_a_reply_naming_nobody_is_addressed_from_the_thread() -> None:
    gm = _gm()
    _opening(gm)
    drafts = gm._ground_email(
        "cecile", "per-cecile", _reply(THREAD), _event(), delay=SimDuration(0)
    )
    sent = next(d.payload for d in drafts if d.tag == "email.message")
    # Everyone in the thread except the person replying — reply-all, which
    # is what a work thread does, and nobody replies to themselves.
    assert set(sent.to) == {"per-ana", "per-dev"}
    assert "per-cecile" not in sent.to


def test_an_explicit_recipient_still_wins() -> None:
    """Deriving is the fallback, not an override."""

    gm = _gm()
    _opening(gm)
    drafts = gm._ground_email(
        "cecile",
        "per-cecile",
        _reply(THREAD, to=("Ana Reyes",)),
        _event(),
        delay=SimDuration(0),
    )
    sent = next(d.payload for d in drafts if d.tag == "email.message")
    assert sent.to == ("per-ana",)


def test_a_new_thread_naming_nobody_is_still_refused() -> None:
    """Nothing to derive from, so it remains the persona's job."""

    gm = _gm()
    _opening(gm)
    try:
        gm._ground_email(
            "cecile", "per-cecile", _reply(None), _event(), delay=SimDuration(0)
        )
    except IntentRejection as refused:
        assert "at least one recipient" in refused.reason
    else:
        raise AssertionError("a new thread with no recipient must still be refused")


def test_the_thread_roster_survives_a_resume() -> None:
    """It lives in world state, which is serialised at every checkpoint.

    A resume that dropped it would start refusing replies again partway
    through a recording, with nothing marking the seam.
    """

    gm = _gm()
    _opening(gm)
    restored = _gm()
    restored.set_state(gm.get_state())
    assert restored.world.thread_participants[THREAD] == {
        "per-ana",
        "per-cecile",
        "per-dev",
    }
    drafts = restored._ground_email(
        "cecile", "per-cecile", _reply(THREAD), _event(), delay=SimDuration(0)
    )
    sent = next(d.payload for d in drafts if d.tag == "email.message")
    assert set(sent.to) == {"per-ana", "per-dev"}

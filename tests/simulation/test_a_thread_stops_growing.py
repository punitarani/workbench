"""A mail thread that never ends is a firm that never decides anything.

`_ground_email` refuses a reply to a thread already carrying twelve
messages, and the comment above the guard says what it is for: *"a real
thread this long has become a meeting or a task. The rejection is feedback
the persona remembers."*

Nothing tested it. Deleting the guard left 620 tests passing, and so did
raising the threshold from twelve to a hundred and twenty — which is the
mutation that matters, because a cap that is present but wrong looks
exactly like a cap that works.

It shapes the corpus rather than preventing a crash. `email.thread_depth_max`
is a measured fidelity band, reading 13 on the record this was written
against; without the cap a thread grows for as long as two personas keep
replying, and the tasks that read mail threads inherit whatever that
produces.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.email import EmailMessagePayload
from core.intents import EmailDraft, EmailIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary

CAP = 12


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={"per-ana": "ana", "per-bo": "bo"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    for index, (person, name) in enumerate(
        (("per-ana", "Ana Reyes"), ("per-bo", "Bo Idris")), start=1
    ):
        gm.world.apply(
            Event(
                seq=index,
                event_id=f"evt-{index:06d}",
                time=index,
                tag="person.record",
                source="gm",
                caused_by=None,
                payload=_person(person, name),
            )
        )
    return gm


def _person(person_id: str, name: str):
    from core.events.people import PersonRecordPayload

    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{person_id.removeprefix('per-')}@example.com",
        title="Associate",
        department="Litigation",
        affiliation="internal",
        manager=None,
        timezone="America/Los_Angeles",
    )


_MINTED = iter(range(10_000))


def _fill(gm: GroundedGm, count: int, thread: str = "thr-000001") -> None:
    """`count` messages already in one thread, applied the way the runtime does.

    Message ids come from a module-level counter rather than the loop
    index. Reusing `msg-000000` across calls overwrote one key in
    `world.threads` instead of adding rows, so the many-threads test below
    built a world holding a single message and passed while proving
    nothing -- caught by mutating the per-thread filter away and finding
    that test still green.
    """

    for _ in range(count):
        index = next(_MINTED)
        gm.world.apply(
            Event(
                seq=1000 + index,
                event_id=f"evt-{1000 + index:06d}",
                time=1000 + index,
                tag="email.message",
                source="gm",
                caused_by=None,
                payload=EmailMessagePayload(
                    kind="email.message",
                    message_id=f"msg-{index:06d}",
                    thread_id=thread,
                    in_reply_to=None,
                    sender="per-ana",
                    to=("per-bo",),
                    cc=(),
                    subject="Covenant language",
                    body="A further thought.",
                    attachments=(),
                ),
            )
        )


def _reply(thread: str = "thr-000001") -> EmailIntent:
    return EmailIntent(
        kind="email",
        thread_ref=thread,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Bo Idris",),
            cc=(),
            subject="Re: Covenant language",
            body="One more thing.",
            summary="a reply",
            attachment_refs=(),
        ),
        attach_document_refs=(),
    )


def _event() -> Event:
    """The wake that occasioned the intent.

    `Event` validates that its tag matches its payload's kind, so this
    cannot be a wake tag carrying a person record -- a check worth having,
    and one this fixture tripped over first.
    """

    from core.events.control import SimWakePayload

    return Event(
        seq=999,
        event_id="evt-000999",
        time=999,
        tag="sim.wake",
        source="gm",
        caused_by=None,
        payload=SimWakePayload(kind="sim.wake", entity="ana"),
    )


def test_a_short_thread_accepts_a_reply() -> None:
    """Guard the guard: if no reply is ever accepted, the refusal is vacuous."""

    gm = _gm()
    _fill(gm, CAP - 1)
    assert gm._ground_email("ana", "per-ana", _reply(), _event(), 0)


def test_a_thread_at_the_cap_is_refused() -> None:
    gm = _gm()
    _fill(gm, CAP)
    with pytest.raises(IntentRejection, match="already carries"):
        gm._ground_email("ana", "per-ana", _reply(), _event(), 0)


def test_the_refusal_says_how_long_and_what_to_do_instead() -> None:
    """A rejection is the persona's only feedback, and it is remembered.

    "too long" teaches nothing; naming the count and the alternatives is
    what turns a refusal into a decision the firm makes.
    """

    gm = _gm()
    _fill(gm, CAP + 3)
    with pytest.raises(IntentRejection) as raised:
        gm._ground_email("ana", "per-ana", _reply(), _event(), 0)
    message = str(raised.value)
    assert str(CAP + 3) in message
    assert "schedule a meeting" in message


def test_the_cap_counts_one_thread_not_all_mail() -> None:
    """Twelve messages spread over twelve threads is an ordinary morning.

    The count sums `world.threads` filtered to this thread; summing the
    whole mapping would refuse a firm for being busy.
    """

    gm = _gm()
    for index in range(CAP + 5):
        _fill(gm, 1, thread=f"thr-{index:06d}")
    assert gm._ground_email("ana", "per-ana", _reply("thr-000000"), _event(), 0)


def _in_thread(gm: GroundedGm, thread: str = "thr-000001") -> str:
    """One message already in `thread`, and its id."""

    _fill(gm, 1, thread=thread)
    return max(gm.world.threads, key=lambda ref: gm.world.threads[ref] == thread)


def test_a_reply_to_a_message_that_does_not_exist_is_refused() -> None:
    """`in_reply_to` becomes a column the projection serves.

    A reply naming a message this world never sent produces a mail row
    pointing at nothing, and coherence reports it as dangling — at
    materialize time, long after the persona could have been told.
    """

    gm = _gm()
    _fill(gm, 1)
    intent = _reply().model_copy(update={"reply_to_ref": "msg-999999"})
    with pytest.raises(IntentRejection, match="unknown message"):
        gm._ground_email("ana", "per-ana", intent, _event(), 0)


def test_a_reply_pointing_into_another_thread_is_refused() -> None:
    """The subtler half, and the one a dangling check cannot see.

    Both ids resolve; they simply belong to different conversations. The
    row is coherent and the thread structure is wrong, which is exactly
    what `email.thread_depth` measures and what a task reading threads
    walks.
    """

    gm = _gm()
    elsewhere = _in_thread(gm, "thr-000002")
    _fill(gm, 1, thread="thr-000001")
    intent = _reply("thr-000001").model_copy(update={"reply_to_ref": elsewhere})
    with pytest.raises(IntentRejection, match="outside thread"):
        gm._ground_email("ana", "per-ana", intent, _event(), 0)


def test_a_reply_inside_its_own_thread_is_accepted() -> None:
    """Guard the guard: the two refusals above must not refuse everything."""

    gm = _gm()
    parent = _in_thread(gm, "thr-000001")
    intent = _reply("thr-000001").model_copy(update={"reply_to_ref": parent})
    assert gm._ground_email("ana", "per-ana", intent, _event(), 0)


def test_attaching_a_document_that_does_not_exist_is_refused() -> None:
    """An attachment is a reference the file room has to honour.

    Coherence catches the dangling row later — "attaches doc-999999, which
    no document is" — but that fails a build rather than teaching the
    persona, and the persona is the one who can fix it.
    """

    gm = _gm()
    _fill(gm, 1)
    intent = _reply().model_copy(update={"attach_document_refs": ("doc-999999",)})
    with pytest.raises(IntentRejection, match="unknown document"):
        gm._ground_email("ana", "per-ana", intent, _event(), 0)

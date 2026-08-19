"""Footprints: what an event touches, for conflict-free batch admission.

The union test is the guard rail — every payload kind in the registry
must carry an explicit footprint rule, so adding an event kind without
deciding its concurrency story fails CI.
"""

from core.events.chat import ChatMessagePayload
from core.events.control import SimGmNotePayload, SimWakePayload
from core.events.email import EmailMessagePayload
from core.events.payloads import TAG_REGISTRY
from core.events.people import PersonRecordPayload
from core.footprint import RULES, footprint_of


def _email(thread: str, sender: str, to: tuple[str, ...]) -> EmailMessagePayload:
    return EmailMessagePayload(
        kind="email.message",
        message_id=f"msg-{thread}",
        thread_id=thread,
        in_reply_to=None,
        sender=sender,
        to=to,
        cc=(),
        subject="s",
        body="b",
        attachments=(),
    )


def test_every_registered_payload_kind_has_a_rule() -> None:
    assert set(RULES) == set(TAG_REGISTRY)


def test_same_thread_emails_conflict_and_disjoint_ones_do_not() -> None:
    a = footprint_of(_email("thr-1", "per-a", ("per-b",)))
    b = footprint_of(_email("thr-1", "per-c", ("per-d",)))
    c = footprint_of(_email("thr-2", "per-e", ("per-f",)))
    assert a.conflicts(b), "same thread must serialize"
    assert not a.conflicts(c), "fully disjoint emails may overlap"


def test_shared_sender_conflicts() -> None:
    a = footprint_of(_email("thr-1", "per-x", ("per-a",)))
    b = footprint_of(_email("thr-2", "per-x", ("per-b",)))
    assert a.conflicts(b)


def test_wakes_conflict_only_on_the_same_entity() -> None:
    ann = footprint_of(SimWakePayload(kind="sim.wake", entity="ann"))
    bob = footprint_of(SimWakePayload(kind="sim.wake", entity="bob"))
    assert not ann.conflicts(bob)
    assert ann.conflicts(footprint_of(SimWakePayload(kind="sim.wake", entity="ann")))


def test_cast_changes_are_barriers() -> None:
    record = footprint_of(
        PersonRecordPayload(
            kind="person.record",
            person_id="per-new",
            name="New Person",
            email_address="new@x.example",
            title="t",
            department="d",
            manager=None,
            affiliation="external",
            timezone="UTC",
        )
    )
    assert record.barrier
    note = footprint_of(SimGmNotePayload(kind="sim.gm.note", note="n"))
    assert record.conflicts(note), "barriers conflict with everything"


def test_notes_are_free() -> None:
    note = footprint_of(SimGmNotePayload(kind="sim.gm.note", note="n"))
    chat = footprint_of(
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-1",
            conversation_id="cnv-1",
            reply_to=None,
            sender="per-a",
            body="hi",
        )
    )
    assert not note.conflicts(chat)

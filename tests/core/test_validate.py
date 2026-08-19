from worldlog_fixtures import coherent_events

from core.events import Event
from core.events.chat import ChatMessagePayload
from core.events.documents import DocumentRevisedPayload
from core.events.email import Attachment, EmailMessagePayload
from core.events.tickets import FieldChange, TicketUpdatedPayload
from core.worldlog.validate import validate_events


def _email(seq: int, time: int, **overrides) -> Event:
    defaults = dict(
        kind="email.message",
        message_id=f"msg-{seq:06d}",
        thread_id="thr-000001",
        in_reply_to=None,
        sender="per-jess-alvarez",
        to=("per-tom-okafor",),
        cc=(),
        subject="s",
        body="b",
        attachments=(),
    )
    defaults.update(overrides)
    payload = EmailMessagePayload(**defaults)
    return Event(seq=seq, time=time, tag=payload.kind, source="x", payload=payload)


def _append(base: list[Event], payload, time: int = 10_000) -> list[Event]:
    seq = len(base)
    return [
        *base,
        Event(seq=seq, time=time, tag=payload.kind, source="x", payload=payload),
    ]


def codes(events: list[Event]) -> set[str]:
    return {f.code for f in validate_events(events).findings}


def test_coherent_fixture_is_clean() -> None:
    report = validate_events(coherent_events())
    assert report.ok, report.findings


def test_first_event_must_be_run_started() -> None:
    events = coherent_events()[1:]
    rebased = [
        Event(
            seq=i,
            time=e.time,
            tag=e.tag,
            source=e.source,
            caused_by=e.caused_by,
            payload=e.payload,
        )
        for i, e in enumerate(events)
    ]
    assert "missing_run_started" in codes(rebased)


def test_seq_gap_detected() -> None:
    events = coherent_events()
    gapped = events[:-1] + [
        Event(
            seq=events[-1].seq + 5,
            time=events[-1].time,
            tag=events[-1].tag,
            source=events[-1].source,
            payload=events[-1].payload,
        )
    ]
    assert "seq_gap" in codes(gapped)


def test_time_regression_detected() -> None:
    events = coherent_events()
    regressed = events[:-1] + [
        Event(
            seq=events[-1].seq,
            time=0,
            tag=events[-1].tag,
            source=events[-1].source,
            payload=events[-1].payload,
        )
    ]
    assert "time_regression" in codes(regressed)


def test_unknown_person_detected() -> None:
    events = _append(
        coherent_events(),
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-000099",
            conversation_id="cnv-000001",
            reply_to=None,
            sender="per-nobody",
            body="hi",
        ),
    )
    assert "unknown_person" in codes(events)


def test_non_member_chat_sender_detected() -> None:
    events = _append(
        coherent_events(),
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-000098",
            conversation_id="cnv-000001",
            reply_to=None,
            sender="per-jess-alvarez",
            body="hi",
        ),
    )
    assert "non_member_sender" in codes(events)


def test_unknown_conversation_detected() -> None:
    events = _append(
        coherent_events(),
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-000097",
            conversation_id="cnv-000999",
            reply_to=None,
            sender="per-daniel-reyes",
            body="hi",
        ),
    )
    assert "unknown_conversation" in codes(events)


def test_document_revision_gap_detected() -> None:
    events = _append(
        coherent_events(),
        DocumentRevisedPayload(
            kind="document.revised",
            document_id="doc-000001",
            revision=5,
            author="per-daniel-reyes",
            content="v5",
            change_summary="jump",
        ),
    )
    assert "revision_gap" in codes(events)


def test_unknown_ticket_detected() -> None:
    events = _append(
        coherent_events(),
        TicketUpdatedPayload(
            kind="ticket.updated",
            ticket_id="tkt-000999",
            actor="per-daniel-reyes",
            changes=(FieldChange(field="status", old="open", new="closed"),),
        ),
    )
    assert "unknown_ticket" in codes(events)


def test_stale_field_change_detected() -> None:
    events = _append(
        coherent_events(),
        TicketUpdatedPayload(
            kind="ticket.updated",
            ticket_id="tkt-000001",
            actor="per-daniel-reyes",
            changes=(FieldChange(field="status", old="open", new="closed"),),
        ),
    )
    assert "stale_field_change" in codes(events)


def test_reply_thread_mismatch_detected() -> None:
    events = coherent_events()
    bad_reply = _email(
        len(events),
        10_000,
        message_id="msg-000099",
        thread_id="thr-000002",
        in_reply_to="msg-000001",
        sender="per-tom-okafor",
        to=("per-jess-alvarez",),
    )
    assert "thread_mismatch" in codes([*events, bad_reply])


def test_unknown_attachment_document_detected() -> None:
    events = coherent_events()
    bad = _email(
        len(events),
        10_000,
        message_id="msg-000098",
        attachments=(
            Attachment(
                filename="x.md", media_type="text/markdown", document_id="doc-000999"
            ),
        ),
    )
    assert "unknown_document" in codes([*events, bad])


def test_duplicate_message_id_detected() -> None:
    events = coherent_events()
    duplicate = _email(len(events), 10_000, message_id="msg-000001")
    assert "duplicate_id" in codes([*events, duplicate])

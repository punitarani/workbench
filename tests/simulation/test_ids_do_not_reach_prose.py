"""Internal ids are plumbing. They must not appear in what people wrote.

Personas are shown ids because they need them — an attachment field takes
a `doc-` id, a reply takes a `chm-` id. Having seen one, they write it
into the sentence too. Measured on a six-month world: 26.1% of 5,894
messages carried at least one, 2,090 of them `doc-` ids, almost always
in the shape "please see doc-000042 attached".

Two things are wrong with that. It is not how anyone writes, and it is a
shortcut — an agent asked which matters a document touched can grep the
id rather than read anything, so a task meant to measure comprehension
measures string matching instead.

The referee rewrites the id to the name of the thing it points at, which
is what the author meant. The tests below drive the real grounding
methods; nothing here reimplements the substitution.
"""

from core.events import Event
from core.events.control import SimDeliverablePayload
from core.events.chat import ChatConversationCreatedPayload
from core.events.people import PersonRecordPayload
from core.intents import (
    ChatDraft,
    ChatIntent,
    DocumentCreateSpec,
    DocumentEditIntent,
    EmailDraft,
    EmailIntent,
    TicketCreateSpec,
    TicketIntent,
)
from simulation.gm.grounded import GroundedGm, TicketVocabulary

PEOPLE = (("per-ana", "Ana Reyes"), ("per-cecile", "Cecile Marchand"))


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
    gm.world.apply(
        Event(
            seq=50,
            event_id="evt-000050",
            time=0,
            tag="chat.conversation.created",
            source="gm",
            payload=ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id="cnv-000001",
                conversation_type="channel",
                name="litigation-group",
                members=tuple(pid for pid, _ in PEOPLE),
            ),
        )
    )
    return gm


def _event(seq: int = 100) -> Event:
    return Event(
        seq=seq,
        event_id=f"evt-{seq:06d}",
        time=0,
        tag="sim.deliverable",
        source="gm",
        payload=SimDeliverablePayload(
            kind="sim.deliverable", entity="ana", day="2026-01-05"
        ),
    )


def _commit(gm: GroundedGm, drafts, seq: int) -> None:
    for offset, draft in enumerate(drafts):
        gm.world.apply(
            Event(
                seq=seq + offset,
                event_id=f"evt-{seq + offset:06d}",
                time=0,
                tag=draft.tag,
                source="gm",
                payload=draft.payload,
            )
        )


def _a_document(gm: GroundedGm) -> str:
    drafts = gm._ground_document(
        "ana",
        "per-ana",
        DocumentEditIntent(
            document_ref=None,
            create=DocumentCreateSpec(
                title="Closing checklist",
                path="engagements/sandhurst/closing-checklist.xlsx",
                content="a note",
                content_format="markdown",
            ),
        ),
        _event(),
        0,
    )
    _commit(gm, drafts, 200)
    return drafts[0].payload.document_id


def _a_ticket(gm: GroundedGm) -> str:
    drafts = gm._ground_ticket(
        "ana",
        "per-ana",
        TicketIntent(
            ticket_ref=None,
            create=TicketCreateSpec(
                title="Sandhurst platform acquisition",
                description="Buy-side diligence.",
                requester_ref="Ana Reyes",
                assignee_ref="Ana Reyes",
                status="Open",
                priority="Normal",
                ticket_type="engagement",
            ),
        ),
        _event(),
        0,
    )
    _commit(gm, drafts, 300)
    return drafts[0].payload.ticket_id


def _send_email(gm: GroundedGm, subject: str, body: str, attach=()):
    return gm._ground_email(
        "ana",
        "per-ana",
        EmailIntent(
            thread_ref=None,
            reply_to_ref=None,
            draft=EmailDraft(
                to=("Cecile Marchand",),
                subject=subject,
                body=body,
                summary="s",
                attachment_refs=tuple(attach),
            ),
        ),
        _event(400),
        0,
    )


def test_a_document_id_becomes_the_filename() -> None:
    gm = _gm()
    document_id = _a_document(gm)
    drafts = _send_email(gm, "Diligence", f"Please see {document_id} attached.")
    body = drafts[0].payload.body
    assert document_id not in body
    assert "closing-checklist.xlsx" in body, body


def test_a_ticket_id_becomes_the_matter_name() -> None:
    gm = _gm()
    ticket_id = _a_ticket(gm)
    drafts = _send_email(gm, "Status", f"Billing question on {ticket_id}.")
    body = drafts[0].payload.body
    assert ticket_id not in body
    assert "Sandhurst platform acquisition" in body, body


def test_the_subject_line_is_cleaned_too() -> None:
    """A subject is prose a person reads in a list. It leaked as often as
    the body did."""

    gm = _gm()
    document_id = _a_document(gm)
    drafts = _send_email(gm, f"Re: {document_id}", "Body.")
    assert document_id not in drafts[0].payload.subject


def test_chat_bodies_are_cleaned() -> None:
    gm = _gm()
    document_id = _a_document(gm)
    drafts = gm._ground_chat(
        "ana",
        "per-ana",
        ChatIntent(
            conversation_ref="cnv-000001",
            reply_to_ref=None,
            draft=ChatDraft(body=f"sent {document_id} over", summary="s"),
        ),
        _event(500),
        0,
    )
    assert document_id not in drafts[0].payload.body


def test_the_attachment_field_keeps_the_id() -> None:
    """The structured link is the whole point — only prose is rewritten.

    Without this, a fix that scrubbed the payload wholesale would pass
    every assertion above while quietly severing every attachment.
    """

    gm = _gm()
    document_id = _a_document(gm)
    drafts = _send_email(gm, "Diligence", "Attached.", attach=(document_id,))
    (attachment,) = drafts[0].payload.attachments
    assert attachment.document_id == document_id


def test_an_id_that_names_nothing_is_left_alone() -> None:
    """Deleting text the referee cannot resolve would corrupt a sentence
    to hide a rarer problem. Leave it: it is visible, and it is honest."""

    gm = _gm()
    drafts = _send_email(gm, "Query", "About doc-999999, any update?")
    assert "doc-999999" in drafts[0].payload.body


def test_ordinary_prose_is_untouched() -> None:
    """The pattern is `xxx-NNNNNN`. Nothing that merely looks like a
    hyphenated word should move."""

    gm = _gm()
    body = "The 2026-0114 matter and the pre-2026 filings are unaffected."
    drafts = _send_email(gm, "Subject", body)
    assert drafts[0].payload.body == body

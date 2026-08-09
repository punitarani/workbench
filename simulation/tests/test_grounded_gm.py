from worldlog_fixtures import coherent_events

from workbench.core.actions import FreeAction, IntentAction, IntentActionSpec
from workbench.core.events.tickets import FieldChange
from workbench.core.intents import (
    ChatDraft,
    ChatIntent,
    DocumentEdit,
    DocumentEditIntent,
    EmailDraft,
    EmailIntent,
    IdleIntent,
    TicketIntent,
)
from workbench.simulation.gm.grounded import GroundedGm, TicketVocabulary
from workbench.simulation.gm.timeflow import intent_duration

ENTITY_FOR_PERSON = {
    "per-meredith-chao": "meredith",
    "per-daniel-reyes": "daniel",
    "per-tom-okafor": "tom",
    "per-jess-alvarez": "jess",
}

VOCAB = TicketVocabulary(
    statuses=("open", "in-review", "closed"),
    priorities=("low", "normal", "high"),
    ticket_types=("nda-review", "general"),
)


def make_gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person=ENTITY_FOR_PERSON,
        ticket_vocabulary=VOCAB,
        response_delay_seconds=120,
    )
    gm.rebuild(coherent_events())
    return gm


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Act.")


def last_event():
    return coherent_events()[-1]


async def test_email_intent_resolves_names_and_threads() -> None:
    gm = make_gm()
    intent = EmailIntent(
        thread_ref="thr-000001",
        reply_to_ref="msg-000002",
        draft=EmailDraft(
            to=("Jess Alvarez",),
            cc=("Meredith Chao",),
            subject="Re: NDA review",
            body="Redlines attached.",
            summary="Sent redlines.",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert len(decision.drafts) == 1
    draft = decision.drafts[0]
    payload = draft.payload
    assert payload.kind == "email.message"
    assert payload.sender == "per-daniel-reyes"
    assert payload.to == ("per-jess-alvarez",)
    assert payload.cc == ("per-meredith-chao",)
    assert payload.thread_id == "thr-000001"
    assert payload.in_reply_to == "msg-000002"
    assert int(draft.delay) == intent_duration(intent)


async def test_email_to_unknown_person_is_rejected() -> None:
    gm = make_gm()
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Zorp the Unknowable",),
            subject="hello",
            body="?",
            summary="?",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert len(decision.drafts) == 1
    assert decision.drafts[0].payload.kind == "sim.gm.note"
    assert "Zorp" in decision.drafts[0].payload.rejected_intent


async def test_new_thread_is_minted_when_no_ref() -> None:
    gm = make_gm()
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Tom Okafor",), subject="New matter", body="x", summary="s"
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.thread_id.startswith("thr-")
    assert payload.thread_id != "thr-000001"


async def test_chat_from_non_member_is_rejected() -> None:
    gm = make_gm()
    intent = ChatIntent(
        conversation_ref="#legal",
        reply_to_ref=None,
        draft=ChatDraft(body="hi", summary="s"),
    )
    decision = await gm.resolve(
        "jess", IntentAction(intent=intent), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_chat_by_channel_name_resolves() -> None:
    gm = make_gm()
    intent = ChatIntent(
        conversation_ref="#legal",
        reply_to_ref=None,
        draft=ChatDraft(body="update posted", summary="s"),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "chat.message"
    assert payload.conversation_id == "cnv-000001"
    assert payload.sender == "per-daniel-reyes"


async def test_stale_ticket_change_is_rejected() -> None:
    gm = make_gm()
    intent = TicketIntent(
        ticket_ref="tkt-000001",
        changes=(FieldChange(field="status", old="open", new="closed"),),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_valid_ticket_change_and_unknown_status_rejected() -> None:
    gm = make_gm()
    good = TicketIntent(
        ticket_ref="tkt-000001",
        changes=(FieldChange(field="status", old="in-review", new="closed"),),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=good), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "ticket.updated"

    bad_status = TicketIntent(
        ticket_ref="tkt-000001",
        changes=(FieldChange(field="status", old="in-review", new="abandoned"),),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=bad_status), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_document_edit_increments_revision() -> None:
    gm = make_gm()
    intent = DocumentEditIntent(
        document_ref="doc-000001",
        edit=DocumentEdit(new_content="v3", change_summary="More edits."),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "document.revised"
    assert payload.revision == 3


async def test_idle_produces_nothing() -> None:
    gm = make_gm()
    decision = await gm.resolve(
        "daniel",
        IntentAction(intent=IdleIntent(until_minutes=30)),
        spec(),
        last_event(),
    )
    assert decision.drafts == ()


async def test_free_action_is_rejected_with_note() -> None:
    gm = make_gm()
    decision = await gm.resolve(
        "daniel", FreeAction(text="wanders off"), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_routing_and_next_acting() -> None:
    gm = make_gm()
    events = coherent_events()
    email = events[7]  # msg-000001: jess -> tom, cc meredith
    assert await gm.route(email) == ("tom", "meredith")
    acting = await gm.next_acting(email)
    assert acting.entities == ("tom",)

    chat = events[10]  # daniel in #legal
    routed = await gm.route(chat)
    assert set(routed) == {"meredith", "tom"}

    run_started = events[0]
    assert await gm.route(run_started) == ()


def test_intent_durations_are_pure() -> None:
    intent = ChatIntent(
        conversation_ref="#legal",
        reply_to_ref=None,
        draft=ChatDraft(body="hello there", summary="s"),
    )
    assert intent_duration(intent) == intent_duration(intent)
    assert intent_duration(intent) > 0

from worldlog_fixtures import coherent_events

from core.actions import FreeAction, IntentAction, IntentActionSpec
from core.events.tickets import FieldChange
from core.intents import (
    ChatDraft,
    ChatIntent,
    DocumentEdit,
    DocumentEditIntent,
    EmailDraft,
    EmailIntent,
    IdleIntent,
    TicketIntent,
)
from simulation.gm.grounded import GroundedGm, TicketVocabulary
from simulation.gm.timeflow import intent_duration

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
    assert await gm.route(email) == ("jess", "tom", "meredith")
    acting = await gm.next_acting(email)
    assert acting.entities == ("tom",)

    chat = events[10]  # daniel in #legal
    routed = await gm.route(chat)
    assert set(routed) == {"daniel", "meredith", "tom"}

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


async def test_email_address_resolves_to_person() -> None:
    gm = make_gm()
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("jess@example.com",),
            subject="hi",
            body="x",
            summary="s",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "email.message"
    assert payload.to == ("per-jess-alvarez",)


async def test_wake_gives_its_entity_a_turn() -> None:
    from core.events import Event
    from core.events.control import SimWakePayload

    gm = make_gm()
    payload = SimWakePayload(kind="sim.wake", entity="daniel")
    wake = Event(seq=99, time=50_000, tag=payload.kind, source="gm", payload=payload)
    assert await gm.route(wake) == ("daniel",), (
        "the persona observes its own wake so its clock advances"
    )
    decision = await gm.next_acting(wake)
    assert decision.entities == ("daniel",)


async def test_deep_reply_chains_stop_granting_turns() -> None:
    from core.events import Event
    from core.events.email import EmailMessagePayload

    gm = make_gm()
    parent_id = None
    decision = None
    for depth in range(5):
        payload = EmailMessagePayload(
            kind="email.message",
            message_id=f"msg-9000{depth:02d}",
            thread_id="thr-900001",
            in_reply_to=parent_id,
            sender="per-jess-alvarez" if depth % 2 == 0 else "per-daniel-reyes",
            to=("per-daniel-reyes",) if depth % 2 == 0 else ("per-jess-alvarez",),
            cc=(),
            subject="ping",
            body="pong",
            attachments=(),
        )
        event = Event(
            seq=800 + depth,
            time=50_000 + depth * 100,
            tag=payload.kind,
            source="x",
            payload=payload,
        )
        await gm.route(event)
        decision = await gm.next_acting(event)
        if depth < 3:
            assert decision.entities, f"depth {depth} should still grant a turn"
        parent_id = payload.message_id
    assert decision is not None
    assert decision.entities == (), (
        "the fourth reply ends automatic turn-granting; wakes can revive it"
    )


async def test_consecutive_document_edits_get_distinct_revisions() -> None:
    gm = make_gm()
    intent = DocumentEditIntent(
        document_ref="doc-000001",
        edit=DocumentEdit(new_content="v3", change_summary="First pass."),
    )
    first = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    second = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert first.drafts[0].payload.revision == 3
    assert second.drafts[0].payload.revision == 4, (
        "resolve-time heads must account for scheduled-but-unapplied revisions"
    )


async def test_actor_observes_own_ticket_and_document_events() -> None:
    from core.events import Event
    from core.events.tickets import TicketCreatedPayload

    gm = make_gm()
    payload = TicketCreatedPayload(
        kind="ticket.created",
        ticket_id="tkt-000900",
        actor="per-tom-okafor",
        title="Review NDA",
        description="d",
        requester="per-jess-alvarez",
        assignee="per-daniel-reyes",
        status="open",
        priority="normal",
        ticket_type="nda-review",
        fields=(),
    )
    event = Event(seq=900, time=60_000, tag=payload.kind, source="tom", payload=payload)
    observers = await gm.route(event)
    assert "tom" in observers, (
        "the actor must see their own record-type events or they redo them"
    )


async def test_senders_observe_their_own_messages() -> None:
    from core.events import Event
    from core.events.email import EmailMessagePayload

    gm = make_gm()
    payload = EmailMessagePayload(
        kind="email.message",
        message_id="msg-901000",
        thread_id="thr-901000",
        in_reply_to=None,
        sender="per-daniel-reyes",
        to=("per-jess-alvarez",),
        cc=(),
        subject="Redlines",
        body="Attached.",
        attachments=(),
    )
    event = Event(
        seq=910, time=61_000, tag=payload.kind, source="daniel", payload=payload
    )
    observers = await gm.route(event)
    assert "daniel" in observers, "senders keep their own sent mail in memory"
    assert "jess" in observers
    decision = await gm.next_acting(event)
    assert "daniel" not in decision.entities, "seeing your mail is not a turn"


async def test_reaction_intent_grounds_to_reaction_event() -> None:
    from core.intents import ReactionIntent

    gm = make_gm()
    intent = ReactionIntent(chat_message_ref="chm-000001", emoji="thumbsup")
    decision = await gm.resolve(
        "meredith", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "chat.reaction.added"
    assert payload.chat_message_id == "chm-000001"
    assert payload.person_id == "per-meredith-chao"
    assert payload.emoji == "thumbsup"


async def test_reaction_to_unknown_message_is_rejected() -> None:
    from core.intents import ReactionIntent

    gm = make_gm()
    intent = ReactionIntent(chat_message_ref="chm-999999", emoji="eyes")
    decision = await gm.resolve(
        "meredith", IntentAction(intent=intent), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_time_log_intent_uses_persona_rate() -> None:
    from core.intents import TimeLogIntent

    gm = make_gm()
    gm.set_bill_rates({"per-daniel-reyes": 44_500})
    intent = TimeLogIntent(
        ticket_ref="tkt-000001", minutes=90, note="NDA redline.", billable=True
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "work.time.logged"
    assert payload.person_id == "per-daniel-reyes"
    assert payload.rate_cents == 44_500
    assert payload.amount_cents == 66_750


async def test_time_log_against_unknown_ticket_rejected() -> None:
    from core.intents import TimeLogIntent

    gm = make_gm()
    intent = TimeLogIntent(ticket_ref="tkt-999999", minutes=30, note="x")
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_calendar_schedule_grounds_to_scheduled_event() -> None:
    from core.intents import CalendarIntent, CalendarScheduleSpec

    gm = make_gm()
    intent = CalendarIntent(
        schedule=CalendarScheduleSpec(
            title="NDA sync",
            day_offset=0,
            start_clock="13:53",
            end_clock="14:23",
            attendee_refs=("Meredith Chao", "Tom Okafor"),
            description="Walk through the redline.",
        )
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    payload = decision.drafts[0].payload
    assert payload.kind == "calendar.event.scheduled"
    assert payload.organizer == "per-daniel-reyes"
    assert set(payload.attendees) == {
        "per-daniel-reyes",
        "per-meredith-chao",
        "per-tom-okafor",
    }
    assert payload.calendar_event_id.startswith("cal-")
    # The referee did the clock arithmetic, not the persona: 13:53 on the
    # day the grounding event falls in.
    assert payload.start % 86_400 == 13 * 3600 + 53 * 60
    assert payload.end - payload.start == 30 * 60


async def test_a_meeting_outside_working_hours_is_refused() -> None:
    """Two of seven persona-scheduled meetings in one recorded day were
    under two thousand seconds past midnight. A meeting at 00:20 is not a
    meeting."""

    from core.intents import CalendarIntent, CalendarScheduleSpec

    gm = make_gm()
    intent = CalendarIntent(
        schedule=CalendarScheduleSpec(
            title="Small hours sync",
            day_offset=0,
            start_clock="00:20",
            end_clock="01:00",
            attendee_refs=("Meredith Chao",),
            description="No.",
        )
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note"


async def test_a_unix_timestamp_cannot_be_expressed_at_all() -> None:
    """The shape that produced a meeting in June 2080. There is no longer
    a field it fits in."""

    import pytest as _pytest
    from pydantic import ValidationError

    from core.intents import CalendarScheduleSpec

    with _pytest.raises(ValidationError):
        CalendarScheduleSpec(
            title="Advisory call",
            day_offset=1_717_609_200,
            start_clock="10:00",
            end_clock="11:00",
            attendee_refs=("Meredith Chao",),
            description="x",
        )


async def test_email_to_plausible_unknown_mints_a_person() -> None:
    gm = make_gm()
    gm.set_emergent_cap(5)
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("pverma@acmesupplies.example",),
            subject="Vendor question",
            body="Quick question about your NDA terms.",
            summary="Asked Acme a question.",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    kinds = [d.payload.kind for d in decision.drafts]
    assert kinds == ["person.record", "email.message"], kinds
    record = decision.drafts[0].payload
    email = decision.drafts[1].payload
    assert record.affiliation == "external"
    assert record.email_address == "pverma@acmesupplies.example"
    assert email.to == (record.person_id,)
    assert decision.drafts[0].delay <= decision.drafts[1].delay


async def test_named_unknown_mints_deterministically() -> None:
    gm_a, gm_b = make_gm(), make_gm()
    for gm in (gm_a, gm_b):
        gm.set_emergent_cap(5)
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Priya Verma",),
            subject="s",
            body="b",
            summary="s",
        ),
    )
    first = await gm_a.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    second = await gm_b.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert (
        first.drafts[0].payload.model_dump_json()
        == second.drafts[0].payload.model_dump_json()
    )
    assert first.drafts[0].payload.name == "Priya Verma"


async def test_emergent_minting_respects_cap_and_garbage() -> None:
    gm = make_gm()
    gm.set_emergent_cap(0)
    plausible = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(to=("Priya Verma",), subject="s", body="b", summary="s"),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=plausible), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note", "cap 0 disables minting"

    gm.set_emergent_cap(5)
    garbage = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(to=("qwerty",), subject="s", body="b", summary="s"),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=garbage), spec(), last_event()
    )
    assert decision.drafts[0].payload.kind == "sim.gm.note", (
        "a single lowercase token is not a plausible person"
    )

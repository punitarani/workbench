import pydantic
import pytest
from payload_samples import sample_payloads

from core.actions import (
    ActRequest,
    ActResponse,
    ChoiceAction,
    ChoiceActionSpec,
    FreeAction,
    FreeActionSpec,
    IntentAction,
    IntentActionSpec,
    NextActingDecision,
    ResolutionDecision,
    TerminateDecision,
)
from core.events import Event, EventDraft
from core.intents import (
    ChatDraft,
    ChatIntent,
    EmailDraft,
    EmailIntent,
    FreeformIntent,
    IdleIntent,
)


def test_choice_spec_requires_two_options() -> None:
    with pytest.raises(pydantic.ValidationError):
        ChoiceActionSpec(call_to_action="pick", options=("only",))


def test_intent_union_discriminates() -> None:
    intent = EmailIntent(
        thread_ref=None,
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Tom Okafor",),
            subject="NDA",
            body="Please review.",
            summary="Asked Tom to review the NDA.",
        ),
    )
    action = IntentAction(intent=intent)
    round_tripped = IntentAction.model_validate_json(action.model_dump_json())
    assert isinstance(round_tripped.intent, EmailIntent)
    assert round_tripped.intent.draft.to == ("Tom Okafor",)


def test_chat_and_idle_and_freeform_intents() -> None:
    ChatIntent(
        conversation_ref="#legal",
        reply_to_ref=None,
        draft=ChatDraft(body="on it", summary="Acknowledged."),
    )
    IdleIntent(until_minutes=30)
    FreeformIntent(text="wanders to the kitchen")


def test_act_request_round_trips_with_observations() -> None:
    payload = sample_payloads()["chat.message"]
    event = Event(seq=3, time=120, tag=payload.kind, source="gm", payload=payload)
    request = ActRequest(
        entity="daniel",
        spec=FreeActionSpec(call_to_action="What do you say?", tag="chat.message"),
        observations=(event,),
        time=120,
    )
    restored = ActRequest.model_validate_json(request.model_dump_json())
    assert restored.observations[0].seq == 3
    assert isinstance(restored.spec, FreeActionSpec)


def test_act_response_holds_any_action_variant() -> None:
    assert ActResponse(action=FreeAction(text="hello")).action.text == "hello"
    choice = ActResponse(action=ChoiceAction(index=1, option="b"))
    assert choice.action.option == "b"


def test_gm_decisions() -> None:
    assert NextActingDecision(entities=("daniel", "tom")).entities == ("daniel", "tom")
    decision = TerminateDecision(terminate=False, reason="queue not empty")
    assert decision.terminate is False
    draft = EventDraft(
        tag="chat.message",
        source="daniel",
        payload=sample_payloads()["chat.message"],
    )
    assert ResolutionDecision(drafts=(draft,)).drafts[0].tag == "chat.message"


def test_intent_action_spec_exists() -> None:
    spec = IntentActionSpec(call_to_action="Decide and produce your next action.")
    assert spec.kind == "intent"

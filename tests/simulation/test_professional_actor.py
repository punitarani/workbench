"""ProfessionalActor routing: decide -> draft -> typed IntentAction."""

from persona_fixtures import DANIEL, observed_events

from workbench.core.actions import IntentAction, IntentActionSpec
from workbench.core.intents import ChatIntent, EmailIntent, IdleIntent
from workbench.core.seed import Seed
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.lm.protocol import LMRequest, LMResponse, TokenUsage
from workbench.simulation.persona.actor import ProfessionalActorAct
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


class SequenceLM:
    """Returns canned completions in call order."""

    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.calls = 0

    async def complete(self, request: LMRequest) -> LMResponse:
        text = self._texts[self.calls]
        self.calls += 1
        return LMResponse(
            text=text, usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
        )


DECIDE_REPLY_EMAIL = (
    "[[ ## choice ## ]]\n"
    '{"action": "reply_email", "target_ref": "thr-000001", '
    '"intent": "Acknowledge and promise redlines by Thursday", '
    '"reason": "Direct request from sales"}\n\n'
    "[[ ## completed ## ]]"
)

DRAFT_EMAIL = (
    "[[ ## draft ## ]]\n"
    '{"to": ["Jess Alvarez"], "cc": [], '
    '"subject": "Re: Vendor NDA - need your eyes", '
    '"body": "On it. Redlines by Thursday.", '
    '"summary": "Promised Jess redlines by Thursday."}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_POST_CHAT = (
    "[[ ## choice ## ]]\n"
    '{"action": "post_chat", "target_ref": "cnv-000001", '
    '"intent": "Confirm I saw the email", "reason": "Quick ack"}\n\n'
    "[[ ## completed ## ]]"
)

DRAFT_CHAT = (
    "[[ ## draft ## ]]\n"
    '{"body": "yep, on it", "summary": "Acknowledged Jess in #legal."}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_IDLE = (
    "[[ ## choice ## ]]\n"
    '{"action": "idle", "target_ref": null, '
    '"intent": "Nothing pending", "reason": "Inbox clear"}\n\n'
    "[[ ## completed ## ]]"
)


async def make_actor(texts: list[str]) -> tuple[ProfessionalActorAct, SequenceLM]:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    inner = SequenceLM(texts)
    lm = WorkbenchLM(
        inner,
        model="deepseek/deepseek-v4-flash-0731",
        seed=Seed(root=42),
        path=("entity", "daniel"),
        max_tokens=1024,
    )
    actor = ProfessionalActorAct(params=DANIEL, working_memory=memory, lm=lm)
    return actor, inner


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Decide and produce your next action.")


async def test_reply_email_route() -> None:
    actor, inner = await make_actor([DECIDE_REPLY_EMAIL, DRAFT_EMAIL])
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action, IntentAction)
    assert isinstance(action.intent, EmailIntent)
    assert action.intent.thread_ref == "thr-000001"
    assert action.intent.reply_to_ref == "msg-000001", "reply targets thread head"
    assert action.intent.draft.summary == "Promised Jess redlines by Thursday."
    assert inner.calls == 2


async def test_post_chat_route() -> None:
    actor, _ = await make_actor([DECIDE_POST_CHAT, DRAFT_CHAT])
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, ChatIntent)
    assert action.intent.conversation_ref == "cnv-000001"
    assert action.intent.draft.body == "yep, on it"


async def test_idle_route_needs_no_drafter() -> None:
    actor, inner = await make_actor([DECIDE_IDLE])
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, IdleIntent)
    assert inner.calls == 1


DECIDE_REPLY_BY_MSG_ID = (
    "[[ ## choice ## ]]\n"
    '{"action": "reply_email", "target_ref": "msg-000001", '
    '"intent": "Acknowledge", "reason": "Direct request"}\n\n'
    "[[ ## completed ## ]]"
)


async def test_message_id_target_ref_resolves_to_thread() -> None:
    actor, _ = await make_actor([DECIDE_REPLY_BY_MSG_ID, DRAFT_EMAIL])
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, EmailIntent)
    assert action.intent.thread_ref == "thr-000001", (
        "a message-id ref must resolve to its thread"
    )
    assert action.intent.reply_to_ref == "msg-000001"


DECIDE_CREATE_TICKET = (
    "[[ ## choice ## ]]\n"
    '{"action": "create_ticket", "target_ref": null, '
    '"intent": "Open an NDA review matter", "reason": "New inbound NDA"}\n\n'
    "[[ ## completed ## ]]"
)

DRAFT_TICKET = (
    "[[ ## ticket ## ]]\n"
    '{"title": "Review Vantage NDA", "description": "Inbound NDA from vendor.", '
    '"requester_ref": "Jess Alvarez", "assignee_ref": "Daniel Reyes", '
    '"status": "open", "priority": "normal", "ticket_type": "nda-review"}\n\n'
    "[[ ## completed ## ]]"
)


async def test_create_ticket_route() -> None:
    from workbench.core.intents import TicketIntent

    actor, inner = await make_actor([DECIDE_CREATE_TICKET, DRAFT_TICKET])
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, TicketIntent)
    assert action.intent.ticket_ref is None
    assert action.intent.create is not None
    assert action.intent.create.ticket_type == "nda-review"
    assert action.intent.create.requester_ref == "Jess Alvarez"
    assert inner.calls == 2


async def test_ticket_situation_names_real_people() -> None:
    from workbench.core.intents import TicketIntent

    captured: list = []

    class CapturingLM:
        def __init__(self, texts):
            self._texts = texts
            self.calls = 0

        async def complete(self, request):
            from workbench.simulation.lm.protocol import LMResponse, TokenUsage

            captured.append(request)
            text = self._texts[self.calls]
            self.calls += 1
            return LMResponse(
                text=text, usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
            )

    from persona_fixtures import DANIEL, observed_events

    from workbench.core.seed import Seed
    from workbench.simulation.lm.dspy_lm import WorkbenchLM
    from workbench.simulation.persona.actor import ProfessionalActorAct
    from workbench.simulation.persona.working_memory import WorkingMemoryComponent

    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    inner = CapturingLM([DECIDE_CREATE_TICKET, DRAFT_TICKET])
    lm = WorkbenchLM(
        inner,
        model="deepseek/deepseek-v4-flash-0731",
        seed=Seed(root=42),
        path=("entity", "daniel"),
        max_tokens=1024,
    )
    actor = ProfessionalActorAct(params=DANIEL, working_memory=memory, lm=lm)
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, TicketIntent)
    ticket_prompt = "\n".join(m.content for m in captured[1].messages)
    assert "Jess Alvarez" in ticket_prompt, (
        "the ticket drafter must see real people to name as requester"
    )

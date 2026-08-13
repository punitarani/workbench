"""Opt-in extra verbs: react_chat, log_time, schedule_meeting.

Personas without extra_verbs keep the exact recorded decide prompt — the
extended vocabulary must never leak into their calls.
"""

from persona_fixtures import DANIEL, observed_events

from workbench.core.actions import IntentAction, IntentActionSpec
from workbench.core.intents import CalendarIntent, ReactionIntent, TimeLogIntent
from workbench.core.seed import Seed
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.persona.actor import ProfessionalActorAct
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


class CapturingLM:
    def __init__(self, texts: list[str]) -> None:
        self._texts = texts
        self.requests: list = []

    async def complete(self, request):
        from workbench.simulation.lm.protocol import LMResponse, TokenUsage

        self.requests.append(request)
        text = self._texts[len(self.requests) - 1]
        return LMResponse(
            text=text, usage=TokenUsage(prompt_tokens=1, completion_tokens=1)
        )


DECIDE_REACT = (
    "[[ ## choice ## ]]\n"
    '{"action": "react_chat", "target_ref": "chm-000001", '
    '"intent": "Acknowledge without noise", "reason": "No reply needed", '
    '"emoji": "\\ud83d\\udc4d", "minutes": null}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_LOG_TIME = (
    "[[ ## choice ## ]]\n"
    '{"action": "log_time", "target_ref": "tck-000001", '
    '"intent": "NDA redline pass", "reason": "Work completed", '
    '"emoji": null, "minutes": 45}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_MEETING = (
    "[[ ## choice ## ]]\n"
    '{"action": "schedule_meeting", "target_ref": null, '
    '"intent": "Walk through the redlines", "reason": "Email is stalling", '
    '"emoji": null, "minutes": null}\n\n'
    "[[ ## completed ## ]]"
)

DRAFT_MEETING = (
    "[[ ## meeting ## ]]\n"
    '{"title": "NDA redline walkthrough", "start": 50400, "end": 52200, '
    '"attendee_refs": ["Jess Alvarez"], '
    '"description": "Review the Vantage redlines together."}\n\n'
    "[[ ## completed ## ]]"
)

DECIDE_IDLE = (
    "[[ ## choice ## ]]\n"
    '{"action": "idle", "target_ref": null, '
    '"intent": "Nothing pending", "reason": "Inbox clear"}\n\n'
    "[[ ## completed ## ]]"
)


async def make_actor(
    texts: list[str], *, extra_verbs: tuple[str, ...] = ()
) -> tuple[ProfessionalActorAct, CapturingLM]:
    params = DANIEL.model_copy(update={"extra_verbs": extra_verbs})
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    inner = CapturingLM(texts)
    lm = WorkbenchLM(
        inner,
        model="deepseek/deepseek-v4-flash-0731",
        seed=Seed(root=42),
        path=("entity", "daniel"),
        max_tokens=1024,
    )
    return ProfessionalActorAct(params=params, working_memory=memory, lm=lm), inner


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Decide and produce your next action.")


async def test_react_chat_route_needs_no_drafter() -> None:
    actor, inner = await make_actor([DECIDE_REACT], extra_verbs=("react_chat",))
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action, IntentAction)
    assert isinstance(action.intent, ReactionIntent)
    assert action.intent.chat_message_ref == "chm-000001"
    assert action.intent.emoji == "\U0001f44d"
    assert len(inner.requests) == 1


async def test_log_time_route_carries_no_rate() -> None:
    actor, inner = await make_actor([DECIDE_LOG_TIME], extra_verbs=("log_time",))
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, TimeLogIntent)
    assert action.intent.ticket_ref == "tck-000001"
    assert action.intent.minutes == 45
    assert action.intent.note == "NDA redline pass"
    assert len(inner.requests) == 1


async def test_schedule_meeting_routes_through_drafter() -> None:
    actor, inner = await make_actor(
        [DECIDE_MEETING, DRAFT_MEETING], extra_verbs=("schedule_meeting",)
    )
    action = await actor.get_action_attempt((), spec())
    assert isinstance(action.intent, CalendarIntent)
    assert action.intent.schedule is not None
    assert action.intent.schedule.attendee_refs == ("Jess Alvarez",)
    assert int(action.intent.schedule.start) == 50400
    assert len(inner.requests) == 2


async def test_default_personas_never_see_the_extended_vocabulary() -> None:
    actor, inner = await make_actor([DECIDE_IDLE])
    await actor.get_action_attempt((), spec())
    prompt = "\n".join(m.content for m in inner.requests[0].messages)
    for verb in ("react_chat", "log_time", "schedule_meeting"):
        assert verb not in prompt, f"{verb} leaked into the recorded decide prompt"


async def test_extended_personas_see_only_their_verbs_as_enabled() -> None:
    actor, inner = await make_actor([DECIDE_REACT], extra_verbs=("react_chat",))
    await actor.get_action_attempt((), spec())
    prompt = "\n".join(m.content for m in inner.requests[0].messages)
    assert "react_chat" in prompt
    assert "enabled_extras" in prompt, "the permitted-extras field must render"

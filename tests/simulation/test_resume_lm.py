"""Resume correctness for LM-backed personas and the grounded GM.

These are the defects the toy-scenario split-run test cannot see: the toy has
no WorkbenchLM (no seed counter) and a trivial GM state.
"""

from persona_fixtures import DANIEL, observed_events

from core.actions import IntentAction, IntentActionSpec
from core.intents import EmailDraft, EmailIntent
from core.seed import Seed
from simulation.entity.entity import ComposedEntity
from simulation.gm.grounded import GroundedGm, TicketVocabulary
from simulation.lm.dspy_lm import WorkbenchLM
from simulation.lm.protocol import LMRequest, LMResponse, TokenUsage
from simulation.persona.actor import ProfessionalActorAct
from simulation.persona.working_memory import WorkingMemoryComponent

DECIDE_IDLE = (
    "[[ ## choice ## ]]\n"
    '{"action": "idle", "target_ref": null, '
    '"intent": "Nothing pending", "reason": "Inbox clear"}\n\n'
    "[[ ## completed ## ]]"
)


class SeedSpy:
    def __init__(self) -> None:
        self.seeds: list[int] = []

    async def complete(self, request: LMRequest) -> LMResponse:
        self.seeds.append(request.seed)
        return LMResponse(
            text=DECIDE_IDLE,
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
        )


def make_entity(spy: SeedSpy) -> ComposedEntity:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    lm = WorkbenchLM(
        spy,
        model="test/model",
        seed=Seed(root=42),
        path=("entity", "daniel-reyes"),
    )
    return ComposedEntity(
        name="daniel-reyes",
        components=(memory,),
        act_component=ProfessionalActorAct(params=DANIEL, working_memory=memory, lm=lm),
    )


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Decide your next action.")


async def test_lm_call_counter_survives_snapshot_restore() -> None:
    straight_spy = SeedSpy()
    straight = make_entity(straight_spy)
    await straight.act(spec())
    await straight.act(spec())
    assert straight_spy.seeds[0] != straight_spy.seeds[1]

    interrupted_spy = SeedSpy()
    interrupted = make_entity(interrupted_spy)
    await interrupted.act(spec())
    snap = interrupted.snapshot()

    resumed_spy = SeedSpy()
    resumed = make_entity(resumed_spy)
    resumed.restore(snap)
    await resumed.act(spec())

    assert resumed_spy.seeds[0] == straight_spy.seeds[1], (
        "a resumed persona must continue its call sequence, not restart it"
    )


VOCAB = TicketVocabulary(
    statuses=("open", "in-review", "closed"),
    priorities=("low", "normal", "high"),
    ticket_types=("nda-review", "general"),
)

ENTITY_FOR_PERSON = {
    "per-daniel-reyes": "daniel-reyes",
    "per-jess-alvarez": "jess-alvarez",
}


async def test_gm_world_state_survives_snapshot_restore() -> None:
    gm = GroundedGm(entity_for_person=ENTITY_FOR_PERSON, ticket_vocabulary=VOCAB)
    for event in observed_events():
        await gm.route(event)

    intent = EmailIntent(
        thread_ref="thr-000001",
        reply_to_ref="msg-000001",
        draft=EmailDraft(
            to=("Jess Alvarez",),
            subject="Re: Vendor NDA - need your eyes",
            body="On it.",
            summary="Acknowledged.",
        ),
    )
    last = observed_events()[-1]

    captured = gm.get_state()
    direct = await gm.resolve("daniel-reyes", IntentAction(intent=intent), spec(), last)
    assert direct.drafts[0].payload.kind == "email.message"

    fresh = GroundedGm(entity_for_person=ENTITY_FOR_PERSON, ticket_vocabulary=VOCAB)
    fresh.set_state(captured)
    restored = await fresh.resolve(
        "daniel-reyes", IntentAction(intent=intent), spec(), last
    )
    assert restored.drafts[0].payload.kind == "email.message", (
        "a restored GM must still resolve threads and people it once knew: "
        f"{restored.drafts[0].payload}"
    )
    assert (
        restored.drafts[0].payload.model_dump_json()
        == direct.drafts[0].payload.model_dump_json()
    )

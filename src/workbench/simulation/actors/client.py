"""Client actors: the outside world as cheap LLM entities.

A client is a real entity — routed, granted turns, footprinted — but
slim: one signature, a working-memory component for thread context, and
no wakes. It acts twice over: a ``sim.cue`` (seeded by the director)
prompts a fresh inbound message; a direct email from the firm grants a
reply turn through the ordinary ``next_acting`` machinery, braked by the
same depth cap as everyone else.
"""

import dspy
from pydantic import BaseModel, ConfigDict

from workbench.core.actions import (
    ActionSpec,
    CueActionSpec,
    EntityAction,
    IntentAction,
)
from workbench.core.intents import EmailDraft, EmailIntent, IdleIntent
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.errors import (
    CassetteMissError,
    LMBudgetExceededError,
    LMTransportError,
)
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.persona.rendering import render_thread
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


class ClientActorParams(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    person_id: str
    name: str
    organization: str
    role: str
    # How they write and what they chronically care about.
    temperament: str
    # The firm-side people they usually write to, by full name.
    contacts: tuple[str, ...]
    concerns: tuple[str, ...] = ()


class ClientWrite(dspy.Signature):
    """Write the email this person would actually send: their voice,
    their concern, one ask. A client, not a colleague — they do not know
    the firm's internals, they know their business and what they need."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="what moved in their world, or the thread")
    contacts: str = dspy.InputField(desc="who at the firm they usually write to")
    draft: EmailDraft = dspy.OutputField()


class ClientProgram(dspy.Module):
    def __init__(self) -> None:
        super().__init__()
        self.write = dspy.Predict(ClientWrite)


class ClientActorAct:
    """Act component for a client entity."""

    def __init__(
        self,
        *,
        params: ClientActorParams,
        working_memory: WorkingMemoryComponent,
        lm: WorkbenchLM,
    ) -> None:
        self._params = params
        self._memory = working_memory
        self._lm = lm
        self._program = ClientProgram()

    def get_state(self) -> ClientActState:
        return ClientActState(lm_calls=self._lm.calls)

    def set_state(self, state: ClientActState) -> None:
        self._lm.set_calls(state.lm_calls)

    def _identity(self) -> str:
        params = self._params
        concerns = "; ".join(params.concerns) or "keeping the business moving"
        return (
            f"You are {params.name}, {params.role} at {params.organization}. "
            f"{params.temperament} Ongoing concerns: {concerns}."
        )

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        if isinstance(spec, CueActionSpec):
            situation = f"{spec.note} (topic: {spec.topic})"
            thread_ref = None
            reply_to = None
        else:
            pending = self._memory.pending_items()
            mail = [item for item in pending if item.channel == "email"]
            if not mail:
                return IntentAction(intent=IdleIntent(until_minutes=240))
            newest = mail[-1]
            thread_ref = self._memory.resolve_thread_ref(newest.ref) or newest.ref
            reply_to = newest.ref
            situation = render_thread(self._memory.events(), thread_ref)
        try:
            with dspy.context(lm=self._lm):
                prediction = await self._program.write.acall(
                    identity=self._identity(),
                    situation=situation,
                    contacts=", ".join(self._params.contacts),
                )
            draft = prediction.draft
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
            raise
        except Exception:
            # A client who cannot compose today stays quiet; the cue is
            # spent and the world moves on.
            return IntentAction(intent=IdleIntent(until_minutes=240))
        return IntentAction(
            intent=EmailIntent(
                thread_ref=thread_ref,
                reply_to_ref=reply_to,
                draft=draft,
            )
        )


class ClientActState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    lm_calls: int = 0


ClientActorAct.state_model = ClientActState

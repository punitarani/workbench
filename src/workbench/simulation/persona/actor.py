"""The acting component: decide, route to one drafter, emit a typed intent."""

import dspy
from pydantic import BaseModel, ConfigDict

from workbench.core.actions import (
    ActionSpec,
    EntityAction,
    IntentAction,
    ReflectActionSpec,
)
from workbench.core.events.agent import MemoryBullet
from workbench.core.intents import (
    ActionIntent,
    AgentNoteIntent,
    CalendarIntent,
    ChatIntent,
    EmailIntent,
    IdleIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
)
from workbench.core.worldlog.views import email_thread
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.errors import CassetteMissError, LMBudgetExceededError
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.persona.memory_stream import MemoryStreamComponent
from workbench.simulation.persona.params import ProfessionalWorkerParams
from workbench.simulation.persona.programs import (
    ActionChoice,
    ExtendedActionChoice,
    ProfessionalActor,
)
from workbench.simulation.persona.rendering import (
    person_names,
    render_conversation,
    render_identity,
    render_knowledge,
    render_thread,
)
from workbench.simulation.persona.retrieval import (
    RetrievalQuery,
    render_memories,
    retrieve,
    tokens_of,
)
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


class ActorActState(BaseModel):
    """What the acting component must carry across a resume: the LM call
    counter that drives per-call seed derivation and cassette keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lm_calls: int = 0
    deep_lm_calls: int = 0


class ProfessionalActorAct:
    state_model = ActorActState

    def __init__(
        self,
        *,
        params: ProfessionalWorkerParams,
        working_memory: WorkingMemoryComponent,
        lm: WorkbenchLM,
        actor: ProfessionalActor | None = None,
        workplace_norms: str = "",
        memory_stream: MemoryStreamComponent | None = None,
        deep_lm: WorkbenchLM | None = None,
    ) -> None:
        self._params = params
        self._memory = working_memory
        self._stream = memory_stream
        self._lm = lm
        # Reflection/planning/meeting turns run on the deep model when a
        # second tier is configured; otherwise everything shares one LM.
        self._deep_lm = deep_lm if deep_lm is not None else lm
        self._actor = actor if actor is not None else ProfessionalActor()
        self._workplace_norms = workplace_norms

    def get_state(self) -> ActorActState:
        return ActorActState(lm_calls=self._lm.calls, deep_lm_calls=self._deep_lm.calls)

    def set_state(self, state: ActorActState) -> None:
        self._lm.set_calls(state.lm_calls)
        if self._deep_lm is not self._lm:
            self._deep_lm.set_calls(state.deep_lm_calls)

    def _relevant_memories(self, pending) -> str:
        if self._stream is None:
            return "None yet."
        query = RetrievalQuery(
            refs=frozenset(item.ref for item in pending),
            tokens=tokens_of(*(item.summary for item in pending)),
        )
        now = self._memory.last_time()
        records = retrieve(self._stream.records(), query, now=now)
        return render_memories(records, now=now)

    def _current_plan(self) -> str:
        # Planning turns arrive in a later phase; the field exists so the
        # decide surface is stable from here on.
        return "No plan recorded for today."

    async def _reflect(self, spec: ReflectActionSpec) -> EntityAction:
        identity = render_identity(self._params)
        now = self._memory.last_time()
        midnight = (now // 86_400) * 86_400
        records = self._stream.records() if self._stream is not None else ()
        today = [record for record in records if record.time >= midnight]
        today_activity = (
            "\n".join(
                f"[{(r.time % 86_400) // 3600:02d}:"
                f"{((r.time % 86_400) % 3600) // 60:02d}] {r.gist}"
                for r in today[-40:]
            )
            or "A quiet day."
        )
        open_items = (
            "\n".join(item.summary for item in self._memory.pending_items())
            or "Nothing pending."
        )
        summaries = [record for record in records if record.kind == "summary"]
        prior = "\n".join(record.gist for record in summaries[-5:]) or "None yet."
        try:
            with dspy.context(lm=self._deep_lm):
                prediction = await self._actor.reflect.acall(
                    identity=identity,
                    day=spec.day,
                    today_activity=today_activity,
                    open_items=open_items,
                    prior_summaries=prior,
                )
            bullets = prediction.reflection.bullets
            open_loops = prediction.reflection.open_loops
        except CassetteMissError, LMBudgetExceededError:
            raise
        except Exception:
            # Cognition must never fail a day: an unparseable reflection
            # degrades to a minimal note. Deterministic under replay — the
            # same recorded text fails the same way.
            bullets = (MemoryBullet(text="(reflection unavailable)", importance=2),)
            open_loops = ()
        note_kind = "weekly_summary" if spec.scope == "weekly" else "daily_summary"
        return IntentAction(
            intent=AgentNoteIntent(
                note_kind=note_kind,
                day=spec.day,
                bullets=bullets,
                open_loops=open_loops,
            )
        )

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        if isinstance(spec, ReflectActionSpec):
            return await self._reflect(spec)
        identity = render_identity(self._params)
        situation = "\n".join(block.content for block in blocks if not block.debug_only)
        pending = list(self._memory.pending_items())
        # The ledger of own actions stays bounded: consolidation owns the
        # long horizon, the prompt sees only the recent tail.
        facts = "\n".join(self._memory.facts()[-12:]) or "None yet."
        knowledge = render_knowledge(self._params) or "None."
        memories = self._relevant_memories(pending)
        current_plan = self._current_plan()

        with dspy.context(lm=self._lm):
            if self._params.extra_verbs:
                decision = await self._actor.decide_extended.acall(
                    identity=identity,
                    situation=situation,
                    current_plan=current_plan,
                    relevant_memories=memories,
                    pending=pending,
                    recent_activity=facts,
                    enabled_extras=", ".join(self._params.extra_verbs),
                )
            else:
                decision = await self._actor.decide.acall(
                    identity=identity,
                    situation=situation,
                    current_plan=current_plan,
                    relevant_memories=memories,
                    pending=pending,
                    recent_activity=facts,
                )
            intent = await self._route(
                decision.choice,
                identity=identity,
                facts=facts,
                knowledge=knowledge,
            )
        return IntentAction(intent=intent)

    async def _route(
        self,
        choice: ActionChoice | ExtendedActionChoice,
        *,
        identity: str,
        facts: str,
        knowledge: str,
    ) -> ActionIntent:
        events = self._memory.events()
        match choice.action:
            case "idle":
                return IdleIntent(until_minutes=self._params.check_interval_minutes)
            case "react_chat":
                return ReactionIntent(
                    chat_message_ref=choice.target_ref or "",
                    emoji=choice.emoji or "\U0001f44d",
                )
            case "log_time":
                return TimeLogIntent(
                    ticket_ref=choice.target_ref or "",
                    minutes=choice.minutes or 30,
                    note=choice.intent,
                )
            case "schedule_meeting":
                names = person_names(events)
                people_line = "People: " + "; ".join(sorted(names.values()))
                prediction = await self._actor.draft_meeting.acall(
                    identity=identity,
                    situation=f"{people_line}\n\n{facts}",
                    intent=choice.intent,
                )
                return CalendarIntent(schedule=prediction.meeting)
            case "reply_email" | "send_email":
                thread_ref = choice.target_ref
                if thread_ref is not None:
                    thread_ref = (
                        self._memory.resolve_thread_ref(thread_ref) or thread_ref
                    )
                thread_text = render_thread(events, thread_ref) if thread_ref else ""
                reply_to = None
                if choice.action == "reply_email" and thread_ref:
                    messages = email_thread(events, thread_ref)
                    if messages:
                        reply_to = messages[-1].message_id
                prediction = await self._actor.draft_email.acall(
                    identity=identity,
                    thread=thread_text,
                    intent=choice.intent,
                    established_facts=facts,
                    relevant_knowledge=knowledge,
                )
                return EmailIntent(
                    thread_ref=thread_ref,
                    reply_to_ref=reply_to,
                    draft=prediction.draft,
                )
            case "post_chat":
                conversation_ref = choice.target_ref or ""
                prediction = await self._actor.draft_chat.acall(
                    identity=identity,
                    conversation=render_conversation(events, conversation_ref),
                    intent=choice.intent,
                    established_facts=facts,
                    relevant_knowledge=knowledge,
                )
                return ChatIntent(
                    conversation_ref=conversation_ref,
                    reply_to_ref=None,
                    draft=prediction.draft,
                )
            case "comment_ticket":
                return TicketIntent(
                    ticket_ref=choice.target_ref,
                    comment=choice.intent,
                )
            case "create_ticket":
                names = person_names(events)
                people_line = "People: " + "; ".join(sorted(names.values()))
                pending_lines = "\n".join(
                    f"- {item.channel} {item.ref}: {item.summary}"
                    for item in self._memory.pending_items()
                )
                prediction = await self._actor.draft_ticket.acall(
                    identity=identity,
                    situation=f"{people_line}\n\n{facts}\n\nPending:\n{pending_lines}",
                    intent=choice.intent,
                    workplace_norms=self._workplace_norms,
                )
                return TicketIntent(ticket_ref=None, create=prediction.ticket)
            case "revise_document":
                return await self._route_document(
                    choice, identity=identity, facts=facts, knowledge=knowledge
                )

    async def _route_document(
        self, choice: ActionChoice, *, identity: str, facts: str, knowledge: str
    ) -> ActionIntent:
        from workbench.core.intents import DocumentEditIntent
        from workbench.core.worldlog.views import document_head

        events = self._memory.events()
        document_text = ""
        if choice.target_ref:
            try:
                document_text = document_head(events, choice.target_ref).content
            except KeyError:
                document_text = ""
        prediction = await self._actor.draft_document.acall(
            identity=identity,
            document=document_text,
            intent=choice.intent,
            context=f"{facts}\n\n{knowledge}",
        )
        return DocumentEditIntent(
            document_ref=choice.target_ref,
            edit=prediction.edit,
        )

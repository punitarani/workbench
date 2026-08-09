"""The acting component: decide, route to one drafter, emit a typed intent."""

import dspy

from workbench.core.actions import ActionSpec, EntityAction, IntentAction
from workbench.core.intents import (
    ActionIntent,
    ChatIntent,
    EmailIntent,
    IdleIntent,
    TicketIntent,
)
from workbench.core.worldlog.views import email_thread
from workbench.simulation.entity.context import ContextBlock
from workbench.simulation.lm.dspy_lm import WorkbenchLM
from workbench.simulation.persona.params import ProfessionalWorkerParams
from workbench.simulation.persona.programs import ActionChoice, ProfessionalActor
from workbench.simulation.persona.rendering import (
    person_names,
    render_conversation,
    render_identity,
    render_knowledge,
    render_thread,
)
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


class ProfessionalActorAct:
    def __init__(
        self,
        *,
        params: ProfessionalWorkerParams,
        working_memory: WorkingMemoryComponent,
        lm: WorkbenchLM,
        actor: ProfessionalActor | None = None,
        workplace_norms: str = "",
    ) -> None:
        self._params = params
        self._memory = working_memory
        self._lm = lm
        self._actor = actor if actor is not None else ProfessionalActor()
        self._workplace_norms = workplace_norms

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        identity = render_identity(self._params)
        situation = "\n".join(
            block.content for block in blocks if not block.debug_only
        )
        pending = list(self._memory.pending_items())
        facts = "\n".join(self._memory.facts()) or "None yet."
        knowledge = render_knowledge(self._params) or "None."

        with dspy.context(lm=self._lm):
            decision = await self._actor.decide.acall(
                identity=identity,
                situation=situation,
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
        self, choice: ActionChoice, *, identity: str, facts: str, knowledge: str
    ) -> ActionIntent:
        events = self._memory.events()
        match choice.action:
            case "idle":
                return IdleIntent(until_minutes=self._params.check_interval_minutes)
            case "reply_email" | "send_email":
                thread_ref = choice.target_ref
                if thread_ref is not None:
                    thread_ref = (
                        self._memory.resolve_thread_ref(thread_ref) or thread_ref
                    )
                thread_text = (
                    render_thread(events, thread_ref) if thread_ref else ""
                )
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

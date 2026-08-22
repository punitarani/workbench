"""The acting component: decide, route to one drafter, emit a typed intent."""

import dspy
from dspy.utils.exceptions import AdapterParseError
from pydantic import BaseModel, ConfigDict, ValidationError

from core.actions import (
    ActionSpec,
    DeliverableActionSpec,
    EntityAction,
    IntentAction,
    MeetingTurnActionSpec,
    PlanActionSpec,
    ReflectActionSpec,
    TimesheetActionSpec,
)
from core.events.agent import MemoryBullet, PlanBlock
from core.events.chat import ChatMessagePayload
from core.intents import (
    ActionIntent,
    AgentNoteIntent,
    AgentPlanIntent,
    CalendarIntent,
    CalendarResponseSpec,
    ChatIntent,
    DocumentCreateSpec,
    DocumentEditIntent,
    EmailIntent,
    IdleIntent,
    MeetingSpeakIntent,
    ReactionIntent,
    TicketIntent,
    TimeLogIntent,
    TimesheetEntry,
    TimesheetIntent,
)
from core.worldlog.views import email_thread, ticket_snapshot
from simulation.entity.context import ContextBlock
from simulation.errors import (
    CassetteMissError,
    LMBudgetExceededError,
    LMTransportError,
)
from simulation.lm.dspy_lm import WorkbenchLM
from simulation.persona.memory_stream import MemoryStreamComponent
from simulation.persona.params import ProfessionalWorkerParams
from simulation.persona.programs import (
    ActionChoice,
    ExtendedActionChoice,
    ProfessionalActor,
)
from simulation.persona.rendering import (
    person_names,
    render_conversation,
    render_identity,
    render_knowledge,
    render_thread,
)
from simulation.persona.retrieval import (
    RetrievalQuery,
    render_memories,
    retrieve,
    tokens_of,
)
from simulation.persona.working_memory import WorkingMemoryComponent

# What a malformed draft can arrive as. `ValidationError` is what pydantic
# raises; `AdapterParseError` is what dspy re-raises it *inside* once its
# own JSON fallback has also failed. A guard written for the inner type
# alone never fires, which is how a run died on a model that writes
# quotation marks: `... as "compliant" until ...` closes the JSON string
# early, the object loses a field, and both adapters give up.
MALFORMED_DRAFT = (ValidationError, AdapterParseError)


# What the person was doing, said the way they would say it. Keyed on the
# actor's verb because that is all the failure knows, but the verb itself
# must never reach a memory: `create_document` is a name this firm's staff
# have no reason to have heard.
_WORK_IN_HAND = {
    "create_document": "the document I was drafting",
    "revise_document": "the mark-up I was making",
    "send_email": "the message I was writing",
    "reply_email": "the reply I was writing",
    "post_chat": "the note I was posting",
    "react_chat": "the note I was posting",
    "create_ticket": "the matter I was opening",
    "update_ticket": "the matter update I was recording",
    "comment_ticket": "the matter note I was adding",
    "log_time": "the time I was recording",
    "schedule_meeting": "the meeting I was booking",
}


def _work_in_hand(action: str) -> str:
    """The in-world name for whatever the actor was part-way through.

    Falls back to a phrase rather than the verb, because an unmapped verb
    is exactly how engine vocabulary would find its way back in: a new
    action added upstream would otherwise start writing its own name into
    personas' memories with nothing failing.
    """

    return _WORK_IN_HAND.get(action, "something I had started")


class ActorActState(BaseModel):
    """What the acting component must carry across a resume: the LM call
    counter that drives per-call seed derivation and cassette keys."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    lm_calls: int = 0
    deep_lm_calls: int = 0


def _first_missing(error: Exception) -> str:
    """The field the model left out, for the note it writes to itself.

    Takes either arm of ``MALFORMED_DRAFT``. Only pydantic's error carries
    a structured field list; dspy's wrapper carries the field name and the
    unparsable text. Calling ``.errors()`` unconditionally would raise
    *inside* the handler and take down the run the handler exists to keep
    alive — a rescue that only works for the failure it was already
    catching.
    """

    errors = getattr(error, "errors", None)
    if callable(errors):
        try:
            for problem in errors():
                location = ".".join(str(part) for part in problem.get("loc", ()))
                return f"{location or 'field'}: {problem.get('msg', 'invalid')}"
        except Exception:
            pass
    field = getattr(error, "field_name", None)
    return f"{field}: unparsable" if field else "invalid draft"


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
            # `retrieval_refs` widens a pending chat item back to its
            # channel. The item itself names a single message, because
            # that is what the persona must target to reply.
            refs=self._memory.retrieval_refs(),
            tokens=tokens_of(*(item.summary for item in pending)),
        )
        now = self._memory.last_time()
        records = retrieve(self._stream.records(), query, now=now)
        return render_memories(records, now=now)

    def _current_plan(self) -> str:
        plan = self._stream.latest_plan() if self._stream is not None else None
        if plan is None:
            return "No plan recorded for today."
        now_clock = self._memory.last_time() % 86_400
        lines = []
        for block in plan.blocks:
            marker = "  <- now" if block.start <= now_clock < block.end else ""
            refs = f" ({', '.join(block.refs)})" if block.refs else ""
            lines.append(
                f"{block.start // 3600:02d}:{(block.start % 3600) // 60:02d}-"
                f"{block.end // 3600:02d}:{(block.end % 3600) // 60:02d} "
                f"{block.focus}{refs}{marker}"
            )
        return "\n".join(lines)

    async def _plan(self, day: str) -> EntityAction:
        identity = render_identity(self._params)
        me = self._params.person_id
        now = self._memory.last_time()
        midnight = (now // 86_400) * 86_400
        calendar = []
        for event in self._memory.events():
            payload = event.payload
            if (
                payload.kind == "calendar.event.scheduled"
                and me in payload.attendees
                and midnight <= int(payload.start) < midnight + 86_400
            ):
                start = int(payload.start) % 86_400
                end = int(payload.end) % 86_400
                calendar.append(
                    f"{start // 3600:02d}:{(start % 3600) // 60:02d}-"
                    f"{end // 3600:02d}:{(end % 3600) // 60:02d} {payload.title}"
                )
        records = self._stream.records() if self._stream is not None else ()
        summaries = [r for r in records if r.kind == "summary"]
        yesterday = "\n".join(r.gist for r in summaries[-8:]) or "No summary on file."
        pending = list(self._memory.pending_items())
        try:
            with dspy.context(lm=self._deep_lm):
                prediction = await self._actor.plan_day.acall(
                    identity=identity,
                    day=day,
                    calendar_today="\n".join(calendar) or "Nothing scheduled.",
                    yesterday=yesterday,
                    relevant_memories=self._relevant_memories(pending),
                )
            blocks = prediction.plan.blocks
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
            raise
        except Exception:
            blocks = (
                PlanBlock(
                    start=9 * 3600,
                    end=17 * 3600,
                    focus="Work the queue and answer pending items",
                ),
            )
        return IntentAction(intent=AgentPlanIntent(day=day, blocks=blocks))

    async def _meeting_turn(self, spec: MeetingTurnActionSpec) -> EntityAction:
        identity = render_identity(self._params)
        meeting = (
            f"{spec.title}\nAgenda: {spec.agenda or 'none stated'}\n"
            f"In the room: {', '.join(spec.attendees)}"
        )
        facts = "\n".join(self._memory.facts()[-12:]) or "None yet."
        knowledge = render_knowledge(self._params) or "None."
        try:
            with dspy.context(lm=self._deep_lm):
                prediction = await self._actor.meeting_turn.acall(
                    identity=identity,
                    meeting=meeting,
                    transcript=spec.transcript,
                    established_facts=facts,
                    relevant_knowledge=knowledge,
                )
            text = prediction.utterance.text
            yields = prediction.utterance.yields
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
            raise
        except Exception:
            text, yields = "(listens)", True
        return IntentAction(
            intent=MeetingSpeakIntent(
                meeting_ref=spec.meeting_id, text=text, yields=yields
            )
        )

    async def _timesheet(self, spec: TimesheetActionSpec) -> EntityAction:
        """A whole day of time in one call.

        Batched deliberately: a professional writes the day up at the end
        of it, and one structured call per person-day is what keeps a
        realistic volume of time entries inside a sane LM budget.
        """

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
        engagements = "\n".join(spec.engagements) or "No engagements assigned."
        stance = (
            "You bill clients. Most of your logged day is chargeable — "
            "about three quarters of it for staff and seniors, less for "
            "managers and partners, whose days carry more review, "
            "supervision, and business development. The rest is real "
            "non-billable work: admin, training, internal meetings. Do not "
            "stretch client work to fill the day, and do not pad the "
            "non-billable side either."
            if spec.bills_clients
            else "You do not bill clients. Everything you log is "
            "non-billable (billable=false) with the category that fits: "
            "admin, internal, training, or business development."
        )
        try:
            # Without a bound LM the call raises and the degradation path
            # below eats it, so a whole day of time silently vanishes —
            # which is exactly what the first flagged mini-epoch did.
            with dspy.context(lm=self._lm):
                prediction = await self._actor.log_day.acall(
                    identity=identity,
                    day=spec.day,
                    engagements=engagements,
                    today_activity=today_activity,
                    billing_stance=stance,
                )
            lines = prediction.timesheet.lines
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
            raise
        except Exception:
            # An unparseable timesheet is a day with no time logged, not a
            # failed day — the same degradation contract as the other
            # cognition turns.
            lines = []
        entries = tuple(
            TimesheetEntry(
                ticket_ref=line.ticket_ref,
                minutes=max(6, min(600, int(line.minutes))),
                note=line.note,
                billable=bool(line.billable),
                category=line.category,
            )
            for line in lines
        )
        return IntentAction(intent=TimesheetIntent(entries=entries))

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
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
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

    @staticmethod
    def _create_spec(authored) -> DocumentCreateSpec:
        """Turn one filled body into the create spec the GM grounds.

        The body that is present decides the format, so the two can never
        disagree — which is the failure the string-content version kept
        producing.
        """

        for attribute, content_format in (
            ("workbook", "spreadsheet"),
            ("document", "formatted"),
            ("deck", "slides"),
        ):
            body = getattr(authored, attribute, None)
            if body is not None:
                return DocumentCreateSpec(
                    title=authored.title,
                    path=authored.path,
                    content=body.model_dump_json(),
                    content_format=content_format,
                )
        return DocumentCreateSpec(
            title=authored.title,
            path=authored.path,
            content=authored.note or "",
            content_format="markdown",
        )

    async def _deliverable(self, spec: DeliverableActionSpec) -> EntityAction:
        """Produce one piece of work product against a real engagement.

        Scheduled rather than opportunistic. Left to the decide loop,
        authoring lost every time to answering mail, and ten workdays of a
        seventeen-person audit practice produced no work product at all.
        """

        identity = render_identity(self._params)
        now = self._memory.last_time()
        midnight = (now // 86_400) * 86_400
        records = self._stream.records() if self._stream is not None else ()
        today = [record for record in records if record.time >= midnight]
        context = (
            "\n".join(f"- {record.gist}" for record in today[-24:])
            or "Nothing yet today."
        )
        engagements = "\n".join(spec.engagements) or "No engagements assigned."

        # Carrying existing work forward is as much of a day as starting
        # something new, and it is the only way a document ever reaches a
        # second version.
        if spec.revise_document_id and spec.revise_document_text:
            try:
                intent = (
                    "Review a colleague's work product. Read it as the "
                    "reviewer of record: leave review notes where the "
                    "evidence is thin, tighten conclusions the testing "
                    "does not support, and sign off what stands. Keep "
                    "their work; you are marking it up, not rewriting it."
                    if spec.as_review
                    else "Work this deliverable forward: clear review "
                    "points, extend the testing, or bring it up to "
                    "date with what the engagement now knows."
                )
                with dspy.context(lm=self._lm):
                    revision = await self._actor.draft_document.acall(
                        identity=identity,
                        document=spec.revise_document_text,
                        intent=intent,
                        context=context,
                    )
            except CassetteMissError, LMBudgetExceededError, LMTransportError:
                raise
            except Exception:
                return IntentAction(
                    intent=IdleIntent(until_minutes=self._params.check_interval_minutes)
                )
            return IntentAction(
                intent=DocumentEditIntent(
                    document_ref=spec.revise_document_id, edit=revision.edit
                )
            )

        try:
            # Bind the LM: an unbound call raises, the degradation path below
            # swallows it, and the day's work product disappears without a
            # trace — the failure this engine has already shipped once.
            with dspy.context(lm=self._lm):
                prediction = await self._actor.author_document.acall(
                    identity=identity,
                    intent=(
                        f"{spec.call_to_action} Engagements you are on:\n{engagements}"
                    ),
                    context=context,
                )
        except CassetteMissError, LMBudgetExceededError, LMTransportError:
            raise
        except Exception:
            # Nothing to produce is a quiet day, not a failed one.
            return IntentAction(
                intent=IdleIntent(until_minutes=self._params.check_interval_minutes)
            )
        return IntentAction(
            intent=DocumentEditIntent(
                document_ref=None, create=self._create_spec(prediction.document)
            )
        )

    async def get_action_attempt(
        self, blocks: tuple[ContextBlock, ...], spec: ActionSpec
    ) -> EntityAction:
        if isinstance(spec, TimesheetActionSpec):
            return await self._timesheet(spec)
        if isinstance(spec, DeliverableActionSpec):
            return await self._deliverable(spec)
        if isinstance(spec, ReflectActionSpec):
            return await self._reflect(spec)
        if isinstance(spec, PlanActionSpec):
            return await self._plan(spec.day)
        if isinstance(spec, MeetingTurnActionSpec):
            return await self._meeting_turn(spec)
        if (
            self._stream is not None
            and self._stream.replan_pending()
            and (today := self._memory.current_day()) is not None
        ):
            # Urgent arrivals outside the plan: replanning consumes this
            # wake; work resumes on the next one.
            return await self._plan(today)
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
            try:
                decision = await self._decide(
                    identity=identity,
                    situation=situation,
                    current_plan=current_plan,
                    memories=memories,
                    pending=pending,
                    facts=facts,
                )
            except MALFORMED_DRAFT:
                # The *decide* call was outside this guard, which made the
                # guard half a fix: a draft the model filled in badly was
                # survivable and a decision it filled in badly was not.
                # Four independent malformations escape here — a verb
                # outside the enum, a missing required field, a quotation
                # mark that costs one, prose with no JSON at all — and each
                # took down the run.
                #
                # Same contract as a malformed draft: the persona does
                # nothing this turn, the world records the absence, and
                # transport, budget and cassette failures still raise.
                return IntentAction(
                    intent=IdleIntent(until_minutes=self._params.check_interval_minutes)
                )
            try:
                intent = await self._route(
                    decision.choice,
                    identity=identity,
                    facts=facts,
                    knowledge=knowledge,
                )
            except MALFORMED_DRAFT as error:
                intent = self._malformed_draft_note(decision, error, spec)
        return IntentAction(intent=intent)

    async def _decide(
        self,
        *,
        identity: str,
        situation: str,
        current_plan: str,
        memories: str,
        pending: list,
        facts: str,
    ):
        """One decision, by whichever decide program this persona uses."""

        if self._params.extra_verbs:
            return await self._actor.decide_extended.acall(
                identity=identity,
                situation=situation,
                current_plan=current_plan,
                relevant_memories=memories,
                pending=pending,
                recent_activity=facts,
                enabled_extras=", ".join(self._params.extra_verbs),
            )
        return await self._actor.decide.acall(
            identity=identity,
            situation=situation,
            current_plan=current_plan,
            relevant_memories=memories,
            pending=pending,
            recent_activity=facts,
        )

    def _malformed_draft_note(
        self, decision, error: Exception, spec
    ) -> AgentNoteIntent:
        """A draft the model filled in badly becomes the persona's own note.

        Survivable, and remembered in the words a person would use.
        Transport, budget and cassette failures still raise; only content
        degrades.

        This note used to read "I started to create_document and left the
        draft malformed (create: Input should be a valid dictionary or
        instance of DocumentCreateSpec)" — an engine verb and a pydantic
        error, written into a lawyer's memory at importance 8 and retrieved
        forever after. The personas believed it. Over thirty recorded days
        they built a shared account of a document-management outage that
        did not exist: 4.8% of time-entry narratives mentioned reworking
        "malformed" drafts, a Slack thread chased "the malformed-input bug"
        across two people and a ticket number, and somebody opened a matter
        note to document the platform's failures. None of it happened.

        So the rule this method now keeps: **the engine's own failures are
        never world data.** What the person remembers is that the work did
        not go out, in the vocabulary of the work. What the engine needs to
        say about itself belongs in the run log, where an operator reads it
        and no persona ever will.
        """

        return AgentNoteIntent(
            note_kind="note",
            day=spec.day if isinstance(spec, PlanActionSpec) else "",
            bullets=(
                MemoryBullet(
                    text=(
                        f"I left {_work_in_hand(decision.choice.action)} "
                        "unfinished and it never went out; pick it up again "
                        "and see it through."
                    ),
                    importance=8,
                ),
            ),
            open_loops=(),
            # For the run log and the operator reading it. This string is
            # what made the one-line `_create_spec` omission findable at
            # all -- 415 identical "create: Input should be a valid
            # dictionary or instance of DocumentCreateSpec" in thirty days
            # named the bug outright. Keep it; just keep it away from the
            # persona.
            engine_detail=(f"{decision.choice.action}: {_first_missing(error)}"),
        )

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
            case "respond_invite":
                if choice.target_ref is None or choice.response is None:
                    return IdleIntent(until_minutes=self._params.check_interval_minutes)
                return CalendarIntent(
                    respond=CalendarResponseSpec(
                        calendar_event_ref=choice.target_ref,
                        response=choice.response,
                    )
                )
            case "update_ticket":
                if choice.target_ref is None:
                    return IdleIntent(until_minutes=self._params.check_interval_minutes)
                try:
                    snapshot = ticket_snapshot(events, choice.target_ref)
                except KeyError:
                    # An invented id is the GM's to reject and teach; here it
                    # simply means there is nothing to update.
                    return IdleIntent(until_minutes=self._params.check_interval_minutes)
                # The GM rejects a change whose `old` does not match reality,
                # so state reality rather than asking the model to recall it.
                current = (
                    f"status={snapshot.status}; priority={snapshot.priority}; "
                    f"type={snapshot.ticket_type}; title={snapshot.title}"
                )
                prediction = await self._actor.update_ticket.acall(
                    identity=identity,
                    ticket=current,
                    intent=choice.intent,
                    vocabulary=self._params.ticket_vocabulary,
                )
                return TicketIntent(
                    ticket_ref=choice.target_ref, changes=tuple(prediction.changes)
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
                known = self._memory.known_documents()
                prediction = await self._actor.draft_email.acall(
                    identity=identity,
                    thread=thread_text,
                    intent=choice.intent,
                    established_facts=facts,
                    relevant_knowledge=knowledge,
                    attachable_documents="; ".join(known) if known else "(none yet)",
                )
                return EmailIntent(
                    thread_ref=thread_ref,
                    reply_to_ref=reply_to,
                    draft=prediction.draft,
                )
            case "post_chat":
                # A chm- target is a reply to that message; anything else
                # is the channel itself. Threading was hardcoded off, so a
                # world of a thousand chat messages contained no thread at
                # all — the same shape as the attachments field that was
                # always empty.
                conversation_ref = choice.target_ref or ""
                reply_to_chat: str | None = None
                if conversation_ref.startswith("chm-"):
                    reply_to_chat = conversation_ref
                    conversation_ref = next(
                        (
                            e.payload.conversation_id
                            for e in reversed(events)
                            if isinstance(e.payload, ChatMessagePayload)
                            and e.payload.chat_message_id == reply_to_chat
                        ),
                        "",
                    )
                prediction = await self._actor.draft_chat.acall(
                    identity=identity,
                    conversation=render_conversation(events, conversation_ref),
                    intent=choice.intent,
                    established_facts=facts,
                    relevant_knowledge=knowledge,
                )
                return ChatIntent(
                    conversation_ref=conversation_ref,
                    reply_to_ref=reply_to_chat,
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
            case "revise_document" | "create_document":
                return await self._route_document(
                    choice, identity=identity, facts=facts, knowledge=knowledge
                )

    async def _route_document(
        self, choice: ActionChoice, *, identity: str, facts: str, knowledge: str
    ) -> ActionIntent:
        from core.intents import DocumentEditIntent
        from core.worldlog.views import document_head

        events = self._memory.events()
        document_text = ""
        if choice.target_ref:
            try:
                document_text = document_head(events, choice.target_ref).content
            except KeyError:
                document_text = ""

        # Authoring and revising are different acts. Without this branch the
        # actor could only ever emit an edit, so a persona who meant to write
        # a workpaper produced a revision of a document that did not exist —
        # which is why the firm's repository held nothing but its templates.
        if choice.action == "create_document" or not document_text:
            prediction = await self._actor.author_document.acall(
                identity=identity,
                intent=choice.intent,
                context=f"{facts}\n\n{knowledge}",
            )
            # Through `_create_spec`, exactly as the scheduled deliverable
            # path does. Passing `prediction.document` straight in typed an
            # `AuthoredDocument` into a field declared `DocumentCreateSpec`
            # and pydantic refused every one: 415 of 417 malformed drafts in
            # thirty recorded days were this line, and 85% of the firm's
            # document authoring never happened. The conversion existed and
            # was correct; this call site simply did not call it.
            return DocumentEditIntent(
                document_ref=None, create=self._create_spec(prediction.document)
            )

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

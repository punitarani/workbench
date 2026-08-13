"""The persona's DSPy programs.

All behavioral instruction text lives in signature docstrings and field
descriptions — exactly the surface GEPA mutates. Rendering supplies data.
"""

from typing import Literal

import dspy
from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events.agent import MemoryBullet, PlanBlock
from workbench.core.intents import (
    CalendarScheduleSpec,
    ChatDraft,
    DocumentEdit,
    EmailDraft,
    TicketCreateSpec,
)
from workbench.simulation.persona.working_memory import PendingItem


class ActionChoice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal[
        "reply_email",
        "send_email",
        "post_chat",
        "create_ticket",
        "comment_ticket",
        "revise_document",
        "idle",
    ]
    target_ref: str | None
    intent: str
    reason: str


class DecideNextAction(dspy.Signature):
    """You are a professional deciding what to do next at work. Choose the
    single most appropriate next action given who you are, your schedule
    pressure, and what is pending. Prefer responding to direct requests over
    housekeeping; respect your role's lane; do not invent work that is not
    supported by the pending items. Never send a message whose only content
    is acknowledgment, thanks, or confirmation of receipt — if a thread
    needs no substantive action from you, idle instead.

    Work the way real professionals do, not everything by email: quick
    internal coordination and status belong in chat; work that should be
    tracked becomes a ticket per your role; producing or revising a document
    is its own action, done in the repository, not described in an email.
    Follow through on commitments listed in your recent activity — if you
    said you would open a matter or deliver a redline and have not, that is
    your next action. Never redo work: if the situation already lists a
    ticket for a request, or your recent activity shows a revision
    delivered, do not create or revise it again — move on or idle."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="current time, schedule, workload")
    current_plan: str = dspy.InputField(
        desc="today's plan with the current block marked; follow it "
        "unless something pending clearly outranks it"
    )
    relevant_memories: str = dspy.InputField(
        desc="what you remember that bears on this moment"
    )
    pending: list[PendingItem] = dspy.InputField()
    recent_activity: str = dspy.InputField(desc="what you did in the last hour")
    choice: ActionChoice = dspy.OutputField()


class ExtendedActionChoice(BaseModel):
    """The core vocabulary plus opt-in light-touch verbs. A separate model
    from ActionChoice on purpose: its schema renders into the decide prompt,
    and personas without extra verbs must keep the recorded prompt exactly."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal[
        "reply_email",
        "send_email",
        "post_chat",
        "react_chat",
        "create_ticket",
        "comment_ticket",
        "log_time",
        "revise_document",
        "schedule_meeting",
        "idle",
    ]
    target_ref: str | None
    intent: str
    reason: str
    # Only meaningful for react_chat / log_time; null otherwise.
    emoji: str | None = None
    minutes: int | None = None


class DecideNextActionExtended(dspy.Signature):
    """You are a professional deciding what to do next at work. Choose the
    single most appropriate next action given who you are, your schedule
    pressure, and what is pending. Prefer responding to direct requests over
    housekeeping; respect your role's lane; do not invent work that is not
    supported by the pending items. Never send a message whose only content
    is acknowledgment, thanks, or confirmation of receipt — if a thread
    needs no substantive action from you, idle instead.

    Work the way real professionals do, not everything by email: quick
    internal coordination and status belong in chat; work that should be
    tracked becomes a ticket per your role; producing or revising a document
    is its own action, done in the repository, not described in an email.
    Follow through on commitments listed in your recent activity — if you
    said you would open a matter or deliver a redline and have not, that is
    your next action. Never redo work: if the situation already lists a
    ticket for a request, or your recent activity shows a revision
    delivered, do not create or revise it again — move on or idle.

    Light-touch verbs may also be available: react_chat adds an emoji to a
    chat message when mere acknowledgment is warranted (set emoji);
    log_time records minutes of completed work against a ticket (set
    minutes); schedule_meeting puts a working session on calendars when
    coordination by message is stalling. Use only the verbs listed in
    enabled_extras."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="current time, schedule, workload")
    current_plan: str = dspy.InputField(
        desc="today's plan with the current block marked; follow it "
        "unless something pending clearly outranks it"
    )
    relevant_memories: str = dspy.InputField(
        desc="what you remember that bears on this moment"
    )
    pending: list[PendingItem] = dspy.InputField()
    recent_activity: str = dspy.InputField(desc="what you did in the last hour")
    enabled_extras: str = dspy.InputField(
        desc="the extra verbs this person may use beyond the core set"
    )
    choice: ExtendedActionChoice = dspy.OutputField()


class DraftEmail(dspy.Signature):
    """Draft this email in this person's authentic voice and email register.
    Ground every claim in the thread history, established facts, and private
    knowledge given; never invent documents, people, meetings, or prior
    statements not present in them. The summary must honestly compress what
    the email commits to."""

    identity: str = dspy.InputField()
    thread: str = dspy.InputField(desc="full rendered thread, oldest first")
    intent: str = dspy.InputField()
    established_facts: str = dspy.InputField(
        desc="things you already said or learned; do not contradict them"
    )
    relevant_knowledge: str = dspy.InputField(
        desc="private knowledge with sharing guidance"
    )
    draft: EmailDraft = dspy.OutputField()


class DraftChatMessage(dspy.Signature):
    """Write a chat message in this person's chat register: shorter and more
    informal than email, consistent with their seniority and the channel's
    audience. Ground it in the conversation and established facts."""

    identity: str = dspy.InputField()
    conversation: str = dspy.InputField(desc="rendered conversation, oldest first")
    intent: str = dspy.InputField()
    established_facts: str = dspy.InputField()
    relevant_knowledge: str = dspy.InputField()
    draft: ChatDraft = dspy.OutputField()


class DraftTicket(dspy.Signature):
    """Open a work-tracking ticket for this request. Use only status,
    priority, and type values from the workplace norms given; name real
    people from the situation as requester and assignee."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="what happened and who is involved")
    intent: str = dspy.InputField()
    workplace_norms: str = dspy.InputField(
        desc="valid ticket statuses, priorities, and types"
    )
    ticket: TicketCreateSpec = dspy.OutputField()


class DraftDocumentEdit(dspy.Signature):
    """Revise the document to accomplish the intent. Return the complete new
    text, preserving everything not implicated by the intent. Ground every
    change in the context given."""

    identity: str = dspy.InputField()
    document: str = dspy.InputField(desc="current full document text")
    intent: str = dspy.InputField()
    context: str = dspy.InputField(desc="facts and knowledge relevant to the edit")
    edit: DocumentEdit = dspy.OutputField()


class DraftMeeting(dspy.Signature):
    """Schedule a working meeting that accomplishes the intent. Keep it
    short, invite only the people the situation implicates, and pick a slot
    inside ordinary working hours near the current time. Times are seconds
    on the simulation clock."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="who is involved and the current time")
    intent: str = dspy.InputField()
    meeting: CalendarScheduleSpec = dspy.OutputField()


class DayPlanSpec(BaseModel):
    """The day in time blocks: what gets focused attention and when."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    blocks: tuple[PlanBlock, ...] = Field(min_length=1, max_length=8)


class PlanDay(dspy.Signature):
    """Lay out your working day in two to six time blocks. Anchor blocks
    to your real calendar first, then place the work your open items and
    memories say matters most. Times are seconds since midnight inside
    working hours; carry the exact world ids (thr-/tkt-/doc-) each block
    concerns."""

    identity: str = dspy.InputField()
    day: str = dspy.InputField(desc="the day being planned")
    calendar_today: str = dspy.InputField(desc="meetings already on your calendar")
    yesterday: str = dspy.InputField(desc="yesterday's summary and open loops")
    relevant_memories: str = dspy.InputField()
    plan: DayPlanSpec = dspy.OutputField()


class DailyReflection(BaseModel):
    """What the day distilled to: bullets future-you needs, with the
    world ids they concern and how much they matter."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bullets: tuple[MemoryBullet, ...] = Field(min_length=1, max_length=8)
    open_loops: tuple[str, ...] = ()


class Reflect(dspy.Signature):
    """Consolidate your working day into a durable note. Write three to
    eight bullets a colleague could act on tomorrow: decisions made,
    commitments given or received, risks noticed, threads left open.
    Rate each bullet's importance 1-10 and carry the exact world ids
    (thr-/tkt-/cnv-/doc-) it concerns. List open loops separately."""

    identity: str = dspy.InputField()
    day: str = dspy.InputField(desc="the day this reflection covers")
    today_activity: str = dspy.InputField(desc="everything you saw and did today")
    open_items: str = dspy.InputField(desc="unanswered items still pending")
    prior_summaries: str = dspy.InputField(desc="your recent daily summaries")
    reflection: DailyReflection = dspy.OutputField()


class ProfessionalActor(dspy.Module):
    """Named predictors; the registry and GEPA address them by attribute."""

    def __init__(self) -> None:
        super().__init__()
        self.decide = dspy.Predict(DecideNextAction)
        self.decide_extended = dspy.Predict(DecideNextActionExtended)
        self.draft_email = dspy.Predict(DraftEmail)
        self.draft_chat = dspy.Predict(DraftChatMessage)
        self.draft_ticket = dspy.Predict(DraftTicket)
        self.draft_document = dspy.Predict(DraftDocumentEdit)
        self.draft_meeting = dspy.Predict(DraftMeeting)
        self.reflect = dspy.Predict(Reflect)
        self.plan_day = dspy.Predict(PlanDay)

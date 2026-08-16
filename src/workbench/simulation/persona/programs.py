"""The persona's DSPy programs.

All behavioral instruction text lives in signature docstrings and field
descriptions — exactly the surface GEPA mutates. Rendering supplies data.
"""

from typing import Literal

import dspy
from pydantic import BaseModel, ConfigDict, Field

from workbench.core.artifacts import (
    FormattedDocument,
    SlideDeck,
    SpreadsheetContent,
)
from workbench.core.events.agent import MemoryBullet, PlanBlock
from workbench.core.events.tickets import FieldChange
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
    delivered, do not create or revise it again — move on or idle.

    target_ref must be a real id of the matching kind — thr-/msg-
    for email threads, cnv- for chat conversations, chm- for chat
    messages, tkt- for tickets, doc- for documents. Use ids you have
    seen; never invent or cross-type one."""

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
        "create_document",
        "revise_document",
        "schedule_meeting",
        "update_ticket",
        "respond_invite",
        "idle",
    ]
    target_ref: str | None
    intent: str
    reason: str
    # Only meaningful for react_chat / log_time / respond_invite; null
    # otherwise.
    emoji: str | None = None
    minutes: int | None = None
    response: Literal["accept", "decline", "tentative"] | None = None


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
    enabled_extras.

    update_ticket moves an engagement's own fields — most often its
    status, when the work has actually reached a new stage. Set
    target_ref to the tkt- id. respond_invite answers a meeting
    invitation you have received (set response to accept, decline, or
    tentative) and takes the cal- id; answer invitations rather than
    leaving colleagues waiting on your availability.

    create_document produces a new deliverable and is how substantive work
    actually lands: a testing workpaper or tie-out, a reconciliation, a
    materiality or planning memo, a management-letter comment, a sampling
    schedule, a client-ready letter, a committee deck. When you have
    committed to produce something, or the work in front of you is the
    making of a document rather than a message about one, create_document
    is the action; leave target_ref null, since the document does not
    exist yet. Use revise_document only for a doc- id you have seen.

    Write the firm's work, not notes about the firm's tools. Documents
    about ticket-naming conventions, file paths, status vocabularies, or
    how to use a system are not deliverables and are never the right
    action — if an id was rejected, simply use a real one next time.

    target_ref must be a real id of the matching kind — thr-/msg-
    for email threads, cnv- for chat conversations, chm- for chat
    messages, tkt- for tickets, doc- for documents. Use ids you have
    seen; never invent or cross-type one."""

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


class AuthoredDocument(BaseModel):
    """A deliverable, with its body in the shape its form requires.

    Exactly one body field is filled, and that choice *is* the format.
    Earlier this was a single string holding the canonical JSON for
    whichever format was declared, and authors reliably wrote prose into a
    field declared `spreadsheet` — every workbook and memo was rejected
    unparsed. Typing the bodies means the model fills a schema instead of
    imitating one.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    path: str = Field(
        description="Where it belongs in the repository, suffix matching "
        "the body: .xlsx, .docx, .pdf, .pptx, or .md"
    )
    workbook: SpreadsheetContent | None = Field(
        default=None, description="Columns of numbers: tie-outs, schedules, aging"
    )
    document: FormattedDocument | None = Field(
        default=None, description="Prose a client or partner reads: memos, letters"
    )
    deck: SlideDeck | None = Field(
        default=None, description="A board or committee presentation"
    )
    note: str | None = Field(
        default=None, description="Plain markdown, for an informal internal note only"
    )


class AuthorDocument(dspy.Signature):
    """Produce the deliverable your intent describes, as a real file.

    Choose the form the work actually takes, and write the content in that
    form's structure:

    - `spreadsheet` for anything that is columns of numbers a colleague
      will foot or filter: trial balances, testing workpapers, census
      reconciliations, sampling schedules, aging.
    - `formatted` for prose a client or partner reads: memos, letters,
      management-letter comments, planning documents. Give it a `.docx`
      path, or `.pdf` when it is issued rather than edited further.
    - `slides` for something presented to a board or committee.
    - `markdown` only for informal internal notes.

    `path` is where it belongs in the firm's repository, with the suffix
    matching the form (.xlsx, .docx, .pdf, .pptx, .md). Content must be
    the real thing — actual numbers, actual names, the substance the
    intent calls for — not a description of what the document would say.

    Markdown is the exception, not the default. Almost nothing a firm
    delivers is a .md file: a tie-out is a workbook, a memo to a partner
    is a document, an audit committee update is a deck. Reach for
    markdown only when the artifact really is an informal internal note
    with no numbers and no reader outside the team.

    Match the form to the work:
      testing workpaper, tie-out, reconciliation, census, aging,
      sampling schedule, trial balance    -> spreadsheet (.xlsx)
      memo, planning document, letter, management-letter comment,
      independence confirmation, review note -> formatted (.docx, or
                                              .pdf when it is issued)
      board or audit-committee update        -> slides (.pptx)
    """

    identity: str = dspy.InputField()
    intent: str = dspy.InputField()
    context: str = dspy.InputField(desc="facts and knowledge the document rests on")
    document: AuthoredDocument = dspy.OutputField()


class UpdateTicket(dspy.Signature):
    """State the field changes this engagement has actually undergone.

    `old` must be the value the ticket carries now, exactly as given; a
    change claiming a stale prior value is rejected. Change only what the
    work genuinely moved — a status that has really advanced, an assignee
    who has really taken it over — and never more than the intent
    supports.
    """

    identity: str = dspy.InputField()
    ticket: str = dspy.InputField(desc="the ticket's current fields")
    intent: str = dspy.InputField()
    vocabulary: str = dspy.InputField(desc="the statuses and priorities this firm uses")
    changes: tuple[FieldChange, ...] = dspy.OutputField()


class DraftMeeting(dspy.Signature):
    """Schedule a working meeting that accomplishes the intent. Keep it
    short, invite only the people the situation implicates, and pick a slot
    inside ordinary working hours near the current time. Times are seconds
    on the simulation clock."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="who is involved and the current time")
    intent: str = dspy.InputField()
    meeting: CalendarScheduleSpec = dspy.OutputField()


class MeetingUtterance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: str
    # Yield when you have said what you came to say; the meeting ends
    # when everyone has yielded or the time budget runs out.
    yields: bool = False


class MeetingTurn(dspy.Signature):
    """Speak one turn in the meeting, in your own voice. Contribute what
    only you know when it helps the room; ask for what you need; keep it
    to a few sentences. Yield once you have nothing further."""

    identity: str = dspy.InputField()
    meeting: str = dspy.InputField(desc="title, agenda, and who is in the room")
    transcript: str = dspy.InputField(desc="the conversation so far")
    established_facts: str = dspy.InputField()
    relevant_knowledge: str = dspy.InputField()
    utterance: MeetingUtterance = dspy.OutputField()


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


class TimesheetLine(BaseModel):
    """One line of a timesheet: an engagement, minutes, and what was done."""

    ticket_ref: str
    minutes: int
    note: str
    billable: bool = True
    category: str = "client"


class DayTimesheet(BaseModel):
    lines: list[TimesheetLine]


class LogDay(dspy.Signature):
    """Write up your time for the day, the way a professional actually
    does it: six to eight lines covering the whole working day, each
    against a real engagement id from your list, with a short note naming
    what you did. Minutes are how long the work took — vary them
    honestly (37, 45, 90, 20), do not round everything to the half hour,
    and do not pad to fill the day. Include your non-billable time too:
    admin, CPE, business development, internal meetings — mark those
    billable=false with the matching category. Only use engagement ids
    that appear in your list."""

    identity: str = dspy.InputField()
    day: str = dspy.InputField(desc="the day being written up")
    engagements: str = dspy.InputField(desc="engagement ids you may log against")
    today_activity: str = dspy.InputField(desc="everything you did today")
    billing_stance: str = dspy.InputField(desc="what is chargeable for your role")
    timesheet: DayTimesheet = dspy.OutputField()


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
        self.author_document = dspy.Predict(AuthorDocument)
        self.update_ticket = dspy.Predict(UpdateTicket)
        self.draft_meeting = dspy.Predict(DraftMeeting)
        self.reflect = dspy.Predict(Reflect)
        self.plan_day = dspy.Predict(PlanDay)
        self.log_day = dspy.Predict(LogDay)
        self.meeting_turn = dspy.Predict(MeetingTurn)

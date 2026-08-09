"""The persona's DSPy programs.

All behavioral instruction text lives in signature docstrings and field
descriptions — exactly the surface GEPA mutates. Rendering supplies data.
"""

from typing import Literal

import dspy
from pydantic import BaseModel, ConfigDict

from workbench.core.intents import ChatDraft, DocumentEdit, EmailDraft
from workbench.simulation.persona.working_memory import PendingItem


class ActionChoice(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    action: Literal[
        "reply_email",
        "send_email",
        "post_chat",
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
    supported by the pending items."""

    identity: str = dspy.InputField()
    situation: str = dspy.InputField(desc="current time, schedule, workload")
    pending: list[PendingItem] = dspy.InputField()
    recent_activity: str = dspy.InputField(desc="what you did in the last hour")
    choice: ActionChoice = dspy.OutputField()


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


class DraftDocumentEdit(dspy.Signature):
    """Revise the document to accomplish the intent. Return the complete new
    text, preserving everything not implicated by the intent. Ground every
    change in the context given."""

    identity: str = dspy.InputField()
    document: str = dspy.InputField(desc="current full document text")
    intent: str = dspy.InputField()
    context: str = dspy.InputField(desc="facts and knowledge relevant to the edit")
    edit: DocumentEdit = dspy.OutputField()


class ProfessionalActor(dspy.Module):
    """Named predictors; the registry and GEPA address them by attribute."""

    def __init__(self) -> None:
        super().__init__()
        self.decide = dspy.Predict(DecideNextAction)
        self.draft_email = dspy.Predict(DraftEmail)
        self.draft_chat = dspy.Predict(DraftChatMessage)
        self.draft_document = dspy.Predict(DraftDocumentEdit)

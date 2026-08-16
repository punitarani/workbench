"""Action specs (what kind of answer is required), entity actions (the answer),
game-master decisions, and the externalization wire contract."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events import Event, EventDraft
from workbench.core.ids import EntityName
from workbench.core.intents import ActionIntent
from workbench.core.simtime import SimTime


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FreeActionSpec(_Model):
    kind: Literal["free"] = "free"
    call_to_action: str
    tag: str


class ChoiceActionSpec(_Model):
    kind: Literal["choice"] = "choice"
    call_to_action: str
    options: tuple[str, ...] = Field(min_length=2)


class FloatActionSpec(_Model):
    kind: Literal["float"] = "float"
    call_to_action: str
    low: float
    high: float


class PlanActionSpec(_Model):
    """Morning planning turn: the entity lays out its day in time blocks
    before the wake ladder begins."""

    kind: Literal["plan"] = "plan"
    call_to_action: str = "Plan your working day."
    day: str


class CueActionSpec(_Model):
    """An external actor's moment: turn the cue's situation into a real
    message to the firm."""

    kind: Literal["cue"] = "cue"
    call_to_action: str = "Something in your world moved; write to the firm."
    note: str
    topic: str = "general"


class MeetingTurnActionSpec(_Model):
    """Speak in an open meeting: the GM renders the room, the entity
    contributes one utterance with its own knowledge and voice."""

    kind: Literal["meeting_turn"] = "meeting_turn"
    call_to_action: str = "It is your turn to speak in the meeting."
    meeting_id: str
    title: str
    agenda: str = ""
    attendees: tuple[str, ...] = ()
    transcript: str = ""
    turn_index: int = 0


class ReflectActionSpec(_Model):
    """End-of-day reflection turn: the entity consolidates its day into a
    persistent note instead of choosing a workplace action."""

    kind: Literal["reflect"] = "reflect"
    call_to_action: str = "Reflect on your day and write it down."
    day: str
    scope: Literal["daily", "weekly"] = "daily"


class TimesheetActionSpec(_Model):
    """End-of-day timesheet turn: the entity writes up the whole day's
    time against real engagements instead of choosing a workplace action."""

    kind: Literal["timesheet"] = "timesheet"
    call_to_action: str = "Write up your time for the day."
    day: str
    engagements: tuple[str, ...] = ()
    # Admin, IT, and office roles carry no bill rate: their day is real
    # work and belongs on a timesheet, but none of it is chargeable.
    bills_clients: bool = True


class DeliverableActionSpec(_Model):
    """A turn to produce work product against a real engagement.

    Carries the engagements the person is actually on, so the deliverable
    is about the firm's work rather than whatever happened to be in the
    inbox — which is what authoring produced when it was left to chance.
    """

    kind: Literal["deliverable"] = "deliverable"
    call_to_action: str = (
        "Produce the piece of work product your engagements most need next."
    )
    day: str
    engagements: tuple[str, ...] = ()
    # Work product is reviewed and reworked, not written once. When set,
    # this turn carries an existing document forward instead of starting a
    # new one — without it the repository is all first drafts and no
    # document ever reaches a second version.
    revise_document_id: str | None = None
    revise_document_text: str = ""
    # Whether this turn is a colleague's review rather than the author's
    # own rework. A workpaper is not finished when its author stops
    # typing; in a practice it is finished when someone else has been
    # through it. The first ten-day world contained 34 documents, 101
    # versions, and not one revision by a second pair of hands — so the
    # firm's central control left no trace anyone could audit.
    as_review: bool = False


class IntentActionSpec(_Model):
    kind: Literal["intent"] = "intent"
    call_to_action: str


ActionSpec = Annotated[
    DeliverableActionSpec
    | FreeActionSpec
    | ChoiceActionSpec
    | FloatActionSpec
    | IntentActionSpec
    | ReflectActionSpec
    | PlanActionSpec
    | TimesheetActionSpec
    | MeetingTurnActionSpec
    | CueActionSpec,
    Field(discriminator="kind"),
]


class FreeAction(_Model):
    kind: Literal["free"] = "free"
    text: str


class ChoiceAction(_Model):
    kind: Literal["choice"] = "choice"
    index: int = Field(ge=0)
    option: str


class FloatAction(_Model):
    kind: Literal["float"] = "float"
    value: float


class IntentAction(_Model):
    kind: Literal["intent"] = "intent"
    intent: ActionIntent


EntityAction = Annotated[
    FreeAction | ChoiceAction | FloatAction | IntentAction,
    Field(discriminator="kind"),
]


class NextActingDecision(_Model):
    entities: tuple[EntityName, ...]


class TerminateDecision(_Model):
    terminate: bool
    reason: str


class ResolutionDecision(_Model):
    drafts: tuple[EventDraft, ...]


class ActRequest(_Model):
    """Everything an external process needs to act for one entity."""

    entity: EntityName
    spec: ActionSpec
    observations: tuple[Event, ...]
    time: SimTime


class ActResponse(_Model):
    action: EntityAction

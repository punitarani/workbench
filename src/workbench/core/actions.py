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


class ReflectActionSpec(_Model):
    """End-of-day reflection turn: the entity consolidates its day into a
    persistent note instead of choosing a workplace action."""

    kind: Literal["reflect"] = "reflect"
    call_to_action: str = "Reflect on your day and write it down."
    day: str
    scope: Literal["daily", "weekly"] = "daily"


class IntentActionSpec(_Model):
    kind: Literal["intent"] = "intent"
    call_to_action: str


ActionSpec = Annotated[
    FreeActionSpec
    | ChoiceActionSpec
    | FloatActionSpec
    | IntentActionSpec
    | ReflectActionSpec
    | PlanActionSpec,
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

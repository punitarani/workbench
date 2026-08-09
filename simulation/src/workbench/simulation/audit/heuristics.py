"""Mechanical realism checks over a finished world log.

These are the deterministic teeth of "characters feel accurate and events
cohere". Judge-based metrics arrive with the optimization phase; every check
here is a pure function of the log.
"""

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from workbench.core.events import Event
from workbench.core.events.chat import ChatMessagePayload
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload


class AuditFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    check: str
    seq: int
    detail: str


class LitmusResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phrase: str
    stated_by_holder: bool
    statement_seq: int | None
    reached_artifact: bool
    artifact_seq: int | None

    @property
    def passed(self) -> bool:
        return self.stated_by_holder and self.reached_artifact


def _body_of(event: Event) -> str | None:
    payload = event.payload
    if isinstance(payload, EmailMessagePayload):
        return payload.body
    if isinstance(payload, ChatMessagePayload):
        return payload.body
    return None


def _author_of(event: Event) -> str | None:
    payload = event.payload
    if isinstance(payload, EmailMessagePayload):
        return payload.sender
    if isinstance(payload, ChatMessagePayload):
        return payload.sender
    return None


def unwritten_standard_litmus(
    events: Sequence[Event], *, phrase: str, holder: str
) -> LitmusResult:
    """Proves knowledge flowed person -> conversation -> artifact.

    The phrase must first appear in a message authored by the holder, and
    afterwards in a document revision or a message authored by someone else.
    """
    needle = phrase.casefold()
    statement_seq: int | None = None
    stated_by_holder = False
    artifact_seq: int | None = None

    for event in events:
        body = _body_of(event)
        if body is not None and needle in body.casefold():
            if statement_seq is None:
                statement_seq = event.seq
                stated_by_holder = _author_of(event) == holder
                continue
        if statement_seq is None:
            payload = event.payload
            if (
                isinstance(payload, DocumentCreatedPayload | DocumentRevisedPayload)
                and needle in payload.content.casefold()
            ):
                # Appeared in an artifact before anyone said it: leaked.
                return LitmusResult(
                    phrase=phrase,
                    stated_by_holder=False,
                    statement_seq=None,
                    reached_artifact=True,
                    artifact_seq=event.seq,
                )
            continue
        payload = event.payload
        in_artifact = (
            isinstance(payload, DocumentCreatedPayload | DocumentRevisedPayload)
            and needle in payload.content.casefold()
        )
        body = _body_of(event)
        in_later_message = (
            body is not None
            and needle in body.casefold()
            and _author_of(event) != holder
        )
        if in_artifact or in_later_message:
            artifact_seq = event.seq
            break

    return LitmusResult(
        phrase=phrase,
        stated_by_holder=stated_by_holder,
        statement_seq=statement_seq,
        reached_artifact=artifact_seq is not None,
        artifact_seq=artifact_seq,
    )


_STOP_WORDS = frozenset(
    "the a an and or of to in on for with is are was be this that it as at "
    "by we you i our your".split()
)


def _meaningful_tokens(text: str) -> set[str]:
    return {
        token
        for token in "".join(c.lower() if c.isalnum() else " " for c in text).split()
        if len(token) > 2 and token not in _STOP_WORDS
    }


def replies_address_their_threads(events: Sequence[Event]) -> tuple[AuditFinding, ...]:
    findings: list[AuditFinding] = []
    by_message_id: dict[str, EmailMessagePayload] = {}
    for event in events:
        payload = event.payload
        if not isinstance(payload, EmailMessagePayload):
            continue
        if payload.in_reply_to is not None:
            parent = by_message_id.get(payload.in_reply_to)
            if parent is not None:
                parent_tokens = _meaningful_tokens(parent.subject + " " + parent.body)
                reply_tokens = _meaningful_tokens(payload.subject + " " + payload.body)
                if not parent_tokens & reply_tokens:
                    findings.append(
                        AuditFinding(
                            check="reply_addresses_thread",
                            seq=event.seq,
                            detail=(
                                f"{payload.message_id} shares no meaningful "
                                f"words with its parent {payload.in_reply_to}"
                            ),
                        )
                    )
        by_message_id[payload.message_id] = payload
    return tuple(findings)


def register_matches_channel(events: Sequence[Event]) -> tuple[AuditFinding, ...]:
    """Per person: median chat message is shorter than median email body."""
    emails: dict[str, list[int]] = {}
    chats: dict[str, list[int]] = {}
    for event in events:
        payload = event.payload
        if isinstance(payload, EmailMessagePayload):
            emails.setdefault(payload.sender, []).append(len(payload.body))
        elif isinstance(payload, ChatMessagePayload):
            chats.setdefault(payload.sender, []).append(len(payload.body))

    def median(values: list[int]) -> float:
        ordered = sorted(values)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return float(ordered[middle])
        return (ordered[middle - 1] + ordered[middle]) / 2

    findings: list[AuditFinding] = []
    for person in sorted(set(emails) & set(chats)):
        if median(chats[person]) >= median(emails[person]):
            findings.append(
                AuditFinding(
                    check="register_matches_channel",
                    seq=-1,
                    detail=(
                        f"{person}: median chat length "
                        f"{median(chats[person]):.0f} >= median email length "
                        f"{median(emails[person]):.0f}"
                    ),
                )
            )
    return tuple(findings)


class KnowledgeFlowResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    statement_seq: int | None
    artifact_seq: int | None
    leaked_seq: int | None

    @property
    def passed(self) -> bool:
        return (
            self.statement_seq is not None
            and self.artifact_seq is not None
            and self.leaked_seq is None
        )


def knowledge_flow_litmus(
    events: Sequence[Event],
    *,
    statement_phrase: str,
    artifact_markers: tuple[str, ...],
    holder: str,
) -> KnowledgeFlowResult:
    """Order-flexible proof that knowledge originated with the holder.

    Passes when the holder states the phrase in a message AND a
    holder-authored document carries a marker, in either order. Fails if
    any non-holder expression of either appears before the holder's first.
    """
    needle = statement_phrase.casefold()
    markers = tuple(m.casefold() for m in artifact_markers)
    statement_seq: int | None = None
    artifact_seq: int | None = None
    leaked_seq: int | None = None

    for event in events:
        payload = event.payload
        body = _body_of(event)
        if body is not None and needle in body.casefold():
            if _author_of(event) == holder:
                if statement_seq is None:
                    statement_seq = event.seq
            elif statement_seq is None and artifact_seq is None:
                leaked_seq = event.seq
                break
        if isinstance(payload, DocumentCreatedPayload | DocumentRevisedPayload):
            text = payload.content.casefold()
            if any(marker in text for marker in markers):
                if payload.author == holder:
                    if artifact_seq is None:
                        artifact_seq = event.seq
                elif statement_seq is None and artifact_seq is None:
                    leaked_seq = event.seq
                    break

    return KnowledgeFlowResult(
        statement_seq=statement_seq,
        artifact_seq=artifact_seq,
        leaked_seq=leaked_seq,
    )

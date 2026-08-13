"""Event footprints: the resources an event touches.

The windowed engine admits a batch of same-time events only when their
footprints are pairwise disjoint, so speculative execution can never
observe state another in-flight event writes. Rules err conservative:
a barrier event (cast changes, day boundaries, run control) conflicts
with everything and always executes alone.

Every payload kind in the registry must have a rule here —
``tests/core/test_footprint.py`` enforces the union.
"""

from collections.abc import Callable

from pydantic import BaseModel, ConfigDict

from workbench.core.events._base import Payload

BARRIER_KINDS = frozenset(
    {
        # Cast and world-shape changes: everything downstream may depend.
        "person.record",
        "org.record",
        "chat.conversation.created",
        # Run and day control mint whole schedules.
        "sim.run.started",
        "sim.day.started",
        "sim.day.ended",
        "sim.checkpoint",
        # Meetings fan out to attendees; rare enough to serialize.
        "meeting.transcript",
    }
)


class Footprint(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    resources: frozenset[str] = frozenset()
    barrier: bool = False

    def conflicts(self, other: Footprint) -> bool:
        if self.barrier or other.barrier:
            return True
        return bool(self.resources & other.resources)


def _persons(*person_ids: str | None) -> set[str]:
    return {f"person:{person_id}" for person_id in person_ids if person_id}


def _email(payload) -> Footprint:
    resources = _persons(payload.sender, *payload.to, *payload.cc)
    resources.add(f"thread:{payload.thread_id}")
    for attachment in payload.attachments:
        resources.add(f"document:{attachment.document_id}")
    return Footprint(resources=frozenset(resources))


def _chat_message(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"conversation:{payload.conversation_id}", *_persons(payload.sender)}
        )
    )


def _chat_reaction(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"conversation:{payload.conversation_id}", *_persons(payload.person_id)}
        )
    )


def _document(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"document:{payload.document_id}", *_persons(payload.author)}
        )
    )


def _ticket_created(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {
                f"ticket:{payload.ticket_id}",
                *_persons(payload.actor, payload.requester, payload.assignee),
            }
        )
    )


def _ticket_updated(payload) -> Footprint:
    resources = {f"ticket:{payload.ticket_id}", *_persons(payload.actor)}
    for change in payload.changes:
        if change.field == "assignee":
            resources |= _persons(change.old, change.new)
    return Footprint(resources=frozenset(resources))


def _ticket_commented(payload) -> Footprint:
    return Footprint(
        resources=frozenset({f"ticket:{payload.ticket_id}", *_persons(payload.actor)})
    )


def _time_logged(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"ticket:{payload.ticket_id}", *_persons(payload.person_id)}
        )
    )


def _calendar_scheduled(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {
                f"calendar:{payload.calendar_event_id}",
                *_persons(payload.organizer, *payload.attendees),
            }
        )
    )


def _calendar_updated(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"calendar:{payload.calendar_event_id}", *_persons(payload.actor)}
        )
    )


def _calendar_response(payload) -> Footprint:
    return Footprint(
        resources=frozenset(
            {f"calendar:{payload.calendar_event_id}", *_persons(payload.responder)}
        )
    )


def _wake(payload) -> Footprint:
    return Footprint(resources=frozenset({f"entity:{payload.entity}"}))


def _gm_note(payload) -> Footprint:
    # A note aimed at an entity serializes against that entity's actions;
    # an unaddressed note conflicts with nothing.
    if payload.entity is None:
        return Footprint()
    return Footprint(resources=frozenset({f"entity:{payload.entity}"}))


def _agent_memory(payload) -> Footprint:
    return Footprint(resources=frozenset({f"entity:{payload.entity}"}))


def _agent_plan(payload) -> Footprint:
    return Footprint(resources=frozenset({f"entity:{payload.entity}"}))


def _free(payload) -> Footprint:
    return Footprint()


def _barrier(payload) -> Footprint:
    return Footprint(barrier=True)


RULES: dict[str, Callable[[Payload], Footprint]] = {
    **{kind: _barrier for kind in BARRIER_KINDS},
    "email.message": _email,
    "chat.message": _chat_message,
    "chat.reaction.added": _chat_reaction,
    "document.created": _document,
    "document.revised": _document,
    "ticket.created": _ticket_created,
    "ticket.updated": _ticket_updated,
    "ticket.commented": _ticket_commented,
    "work.time.logged": _time_logged,
    "calendar.event.scheduled": _calendar_scheduled,
    "calendar.event.updated": _calendar_updated,
    "calendar.response": _calendar_response,
    "sim.gm.note": _gm_note,
    "sim.wake": _wake,
    "sim.agent.memory": _agent_memory,
    "sim.agent.plan": _agent_plan,
    "sim.reflection": _wake,
}


def footprint_of(payload: Payload) -> Footprint:
    rule = RULES.get(payload.kind)
    if rule is None:
        # Unknown kinds serialize; the union test keeps this unreachable.
        return Footprint(barrier=True)
    return rule(payload)

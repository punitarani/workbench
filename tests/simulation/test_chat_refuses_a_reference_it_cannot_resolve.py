"""Chat's reference checks, which nothing exercised.

`_ground_chat` and `_ground_reaction` refuse a reply or a reaction naming
a message this world never carried. Both survived deletion with 628 tests
passing — the mirror of the email refusals swept an hour earlier, and
missing for the same reason: every test that touches chat sends a *valid*
message, so the branches that decline never run.

What they protect is the served surface. `reply_to` becomes a column, and
a chat row pointing at a message that does not exist is a thread the
product cannot render — this file's neighbour records that replies once
chained nine deep and the served `thread_ts` named another reply as a
root, "which no real workspace can represent".

`_ground_reaction` also carries a deliberate kindness worth pinning: the
commonest persona slip is naming the *conversation* instead of a message,
and rather than refusing, it reacts to that conversation's latest message.
A test that only checked the refusal would let someone "simplify" that
away.
"""

from __future__ import annotations

import pytest

from core.events import Event
from core.events.chat import ChatConversationCreatedPayload, ChatMessagePayload
from core.events.control import SimWakePayload
from core.events.people import PersonRecordPayload
from core.intents import ChatDraft, ChatIntent, ReactionIntent
from simulation.gm.grounded import GroundedGm, IntentRejection, TicketVocabulary

CHANNEL = "cnv-000001"


def _person(person_id: str, name: str) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{person_id.removeprefix('per-')}@example.com",
        title="Associate",
        department="Litigation",
        affiliation="internal",
        manager=None,
        timezone="America/Los_Angeles",
    )


def _apply(gm: GroundedGm, seq: int, tag: str, payload) -> None:
    gm.world.apply(
        Event(
            seq=seq,
            event_id=f"evt-{seq:06d}",
            time=seq,
            tag=tag,
            source="gm",
            caused_by=None,
            payload=payload,
        )
    )


def _gm() -> GroundedGm:
    gm = GroundedGm(
        entity_for_person={"per-ana": "ana", "per-bo": "bo"},
        ticket_vocabulary=TicketVocabulary(
            statuses=("Open",), priorities=("Normal",), ticket_types=("engagement",)
        ),
    )
    _apply(gm, 1, "person.record", _person("per-ana", "Ana Reyes"))
    _apply(gm, 2, "person.record", _person("per-bo", "Bo Idris"))
    _apply(
        gm,
        3,
        "chat.conversation.created",
        ChatConversationCreatedPayload(
            kind="chat.conversation.created",
            conversation_id=CHANNEL,
            conversation_type="channel",
            name="docket-and-deadlines",
            members=("per-ana", "per-bo"),
            topic="deadlines",
            purpose="the week's dates",
        ),
    )
    _apply(
        gm,
        4,
        "chat.message",
        ChatMessagePayload(
            kind="chat.message",
            chat_message_id="chm-000001",
            conversation_id=CHANNEL,
            reply_to=None,
            sender="per-bo",
            body="Filed this morning.",
        ),
    )
    return gm


def _event() -> Event:
    return Event(
        seq=999,
        event_id="evt-000999",
        time=999,
        tag="sim.wake",
        source="gm",
        caused_by=None,
        payload=SimWakePayload(kind="sim.wake", entity="ana"),
    )


def _say(reply_to: str | None = None) -> ChatIntent:
    return ChatIntent(
        kind="chat",
        conversation_ref=CHANNEL,
        reply_to_ref=reply_to,
        draft=ChatDraft(body="Noted, thanks.", summary="acknowledged"),
    )


def test_a_message_in_a_channel_is_accepted() -> None:
    """Guard the guard: a refusal nothing can pass proves nothing."""

    gm = _gm()
    assert gm._ground_chat("ana", "per-ana", _say(), _event(), 0)


def test_a_reply_to_a_chat_message_that_does_not_exist_is_refused() -> None:
    gm = _gm()
    with pytest.raises(IntentRejection, match="unknown chat message"):
        gm._ground_chat("ana", "per-ana", _say("chm-999999"), _event(), 0)


def test_a_reply_to_a_real_message_is_accepted() -> None:
    gm = _gm()
    assert gm._ground_chat("ana", "per-ana", _say("chm-000001"), _event(), 0)


def test_a_reaction_to_a_message_that_does_not_exist_is_refused() -> None:
    gm = _gm()
    intent = ReactionIntent(
        kind="reaction", chat_message_ref="chm-999999", emoji="eyes"
    )
    with pytest.raises(IntentRejection, match="unknown chat message"):
        gm._ground_reaction("ana", "per-ana", intent, _event(), 0)


def test_naming_the_conversation_reacts_to_its_latest_message() -> None:
    """The deliberate kindness, pinned so nobody simplifies it away.

    The commonest slip is naming the channel rather than a message. That
    is not a refusal, it is a persona being imprecise about a thing the
    world can resolve, and the referee resolves it.
    """

    gm = _gm()
    intent = ReactionIntent(kind="reaction", chat_message_ref=CHANNEL, emoji="eyes")
    drafts = gm._ground_reaction("ana", "per-ana", intent, _event(), 0)
    assert drafts
    assert drafts[0].payload.chat_message_id == "chm-000001"


def _outsider(gm: GroundedGm) -> None:
    """A colleague who exists and is not in this channel."""

    _apply(gm, 5, "person.record", _person("per-cy", "Cy Okafor"))
    # The private mapping, because that is what the referee reads. The
    # public spelling does not exist, and reaching for it is how a fixture
    # ends up asserting against a world the runtime never sees.
    gm._entity_for_person["per-cy"] = "cy"


def test_someone_outside_the_channel_cannot_post_in_it() -> None:
    """The membership check, which the wider suite covers and this file did
    not — found by mutating it away and watching only these five pass.

    A file that names itself for chat's reference checks and leaves one to
    a test three directories away is a file whose green tick means less
    than it looks."""

    gm = _gm()
    _outsider(gm)
    with pytest.raises(IntentRejection, match="not a member"):
        gm._ground_chat("cy", "per-cy", _say(), _event(), 0)


def test_someone_outside_the_channel_cannot_react_in_it() -> None:
    """The same rule on the reaction path, which is a separate guard.

    Two sites, two chances to lose one. A reaction is a row in the served
    surface naming a person and a channel, so an outsider's emoji is a
    record of attendance that never happened.
    """

    gm = _gm()
    _outsider(gm)
    intent = ReactionIntent(
        kind="reaction", chat_message_ref="chm-000001", emoji="eyes"
    )
    with pytest.raises(IntentRejection, match="is not in"):
        gm._ground_reaction("cy", "per-cy", intent, _event(), 0)

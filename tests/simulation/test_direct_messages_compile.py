"""A firm generated from a spec must be able to have private conversations.

The generic compile path hardcoded ``conversation_type="channel"``, so a
world built from a `WorkplaceSpec` had channels and nothing else. The
hand-written workplaces in this tree create DMs; the generated ones could
not, and nothing anywhere said so — an absent conversation type is not an
error, it is simply a table that never gains those rows.

Measured on a six-month, 21-person law firm: 3,177 chat messages, 10
channels, zero direct messages. Everything the firm said to itself, it
said in the open.

The rendering test matters as much as the compile test. A DM carries no
name, so the persona's Situation block listed it as a bare `cnv-000015`
— an id with nothing to distinguish it from any other, which no persona
has a reason to post in.
"""

import pytest
from mini_workplace import make_spec

from core.events import Event
from core.events.chat import ChatConversationCreatedPayload
from core.events.people import PersonRecordPayload
from core.seed import Seed
from core.worldlog.validate import validate_events
from simulation.errors import ConfigError
from simulation.persona.working_memory import WorkingMemoryComponent
from simulation.workplace.compile import compile_workplace
from simulation.workplace.spec import DirectMessageSpec

PAIR = ("per-ann-liu", "per-ravi-dee")


def _conversations(spec):
    compiled = compile_workplace(spec, Seed(root=42))
    return [
        event.payload
        for event in compiled.genesis
        if isinstance(event.payload, ChatConversationCreatedPayload)
    ]


def test_a_declared_dm_becomes_a_dm() -> None:
    payloads = _conversations(
        make_spec(direct_messages=(DirectMessageSpec(members=PAIR),))
    )
    dms = [p for p in payloads if p.conversation_type == "dm"]
    assert len(dms) == 1
    assert dms[0].members == PAIR
    assert dms[0].name is None


def test_channels_are_unaffected() -> None:
    """Every world already in this tree declares channels and no DMs. The
    field defaults to empty, and their compiled output must not move."""

    before = _conversations(make_spec())
    assert [p.conversation_type for p in before] == ["channel"]


def test_the_compiled_log_still_validates() -> None:
    compiled = compile_workplace(
        make_spec(direct_messages=(DirectMessageSpec(members=PAIR),)),
        Seed(root=42),
    )
    report = validate_events(compiled.genesis)
    assert not report.findings, report.findings


def test_an_unknown_member_is_refused_at_compile() -> None:
    """The same guard channels get. A DM naming somebody who does not
    exist is a config error, not a conversation with a ghost."""

    with pytest.raises(ConfigError):
        compile_workplace(
            make_spec(
                direct_messages=(
                    DirectMessageSpec(members=("per-ann-liu", "per-nobody")),
                )
            ),
            Seed(root=42),
        )


def test_a_dm_with_yourself_is_refused() -> None:
    with pytest.raises(ConfigError):
        compile_workplace(
            make_spec(
                direct_messages=(
                    DirectMessageSpec(members=("per-ann-liu", "per-ann-liu")),
                )
            ),
            Seed(root=42),
        )


@pytest.mark.asyncio
async def test_the_persona_is_told_who_the_dm_is_with() -> None:
    """A bare `cnv-` id is not a conversation anyone posts in."""

    compiled = compile_workplace(
        make_spec(direct_messages=(DirectMessageSpec(members=PAIR),)),
        Seed(root=42),
    )
    memory = WorkingMemoryComponent(person_id="per-ann-liu", start_date="2026-03-12")
    memory.set_state(memory.state_model())
    events = [
        Event(
            seq=index,
            event_id=f"evt-{index:06d}",
            time=0,
            tag=event.payload.kind,
            source="gm",
            payload=event.payload,
        )
        for index, event in enumerate(compiled.genesis, start=1)
        if isinstance(
            event.payload, ChatConversationCreatedPayload | PersonRecordPayload
        )
    ]
    for event in events:
        await memory.pre_observe(event)
    block = await memory.pre_act(None)
    line = next(
        line
        for line in block.content.splitlines()
        if line.startswith("Chat conversations you can post in")
    )
    assert "direct message with Ravi Dee" in line, line

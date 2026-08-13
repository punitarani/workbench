"""The interactive seat: an agent occupies a persona's chair mid-run.

The engine and the agent are peer tasks on one loop; the engine parks on
``SeatSession.act`` while the agent decides. The mini workplace runs a full
day with Ann's seat externalized: the agent answers the 09:40 email and
idles through every other turn, and the persona never touches the LM.
"""

import asyncio
from pathlib import Path

import pytest
from mini_workplace import make_spec

from workbench.core.actions import (
    ActRequest,
    FreeAction,
    FreeActionSpec,
    IntentAction,
)
from workbench.core.intents import (
    ChatDraft,
    ChatIntent,
    EmailDraft,
    EmailIntent,
    IdleIntent,
)
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.errors import ConfigError, SeatProtocolError
from workbench.simulation.external.session import SeatSession
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.lm.protocol import LMRequest, LMResponse
from workbench.simulation.run import run_workplace


class CountingLM:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeLM()

    async def complete(self, request: LMRequest) -> LMResponse:
        self.calls += 1
        return await self._inner.complete(request)


def idle() -> IntentAction:
    return IntentAction(intent=IdleIntent(until_minutes=30))


async def test_session_round_trip_and_protocol_errors() -> None:
    session = SeatSession()
    spec = FreeActionSpec(call_to_action="Go.", tag="chat.message")
    request = ActRequest(entity="ann-liu", spec=spec, observations=(), time=0)

    with pytest.raises(SeatProtocolError, match="no pending turn"):
        session.submit(FreeAction(text="early"))

    engine_side = asyncio.ensure_future(session.act(request))
    turn = await session.next_turn()
    assert turn is not None and turn.entity == "ann-liu"
    session.submit(FreeAction(text="ok"))
    response = await engine_side
    assert response.action == FreeAction(text="ok")

    with pytest.raises(SeatProtocolError, match="no pending turn"):
        session.submit(FreeAction(text="again"))

    session.end()
    assert await session.next_turn() is None
    with pytest.raises(SeatProtocolError, match="ended"):
        await session.act(request)


async def test_unknown_seat_name_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="nobody"):
        await run_workplace(
            make_spec(),
            seed=Seed(root=42),
            out_dir=tmp_path / "run",
            inner_lm=FakeLM(),
            model="test/model",
            external_seats={"nobody": SeatSession()},
        )


async def drive_ann(session: SeatSession, log: list[ActRequest]) -> None:
    replied = False
    while (turn := await session.next_turn()) is not None:
        log.append(turn)
        emails = [o for o in turn.observations if o.payload.kind == "email.message"]
        if emails and not replied:
            email = emails[-1].payload
            session.submit(
                IntentAction(
                    intent=EmailIntent(
                        thread_ref=email.thread_id,
                        reply_to_ref=email.message_id,
                        draft=EmailDraft(
                            to=("Ravi Dee",),
                            cc=(),
                            subject="Re: Quick question",
                            body="Confirmed, thanks.",
                            summary="Confirmed receipt to Ravi.",
                        ),
                    )
                )
            )
            replied = True
        else:
            session.submit(idle())


async def test_agent_occupies_seat_for_a_full_day(tmp_path: Path) -> None:
    session = SeatSession()
    turns: list[ActRequest] = []
    agent = asyncio.ensure_future(drive_ann(session, turns))
    lm = CountingLM()

    async with asyncio.timeout(30):
        result = await run_workplace(
            make_spec(),
            seed=Seed(root=42),
            out_dir=tmp_path / "run",
            inner_lm=lm,
            model="test/model",
            external_seats={"ann-liu": session},
        )
        session.end()
        await agent

    assert result.reason == "quiescent"
    assert lm.calls == 0, "an externalized seat never consumes the persona LM"

    events = read_events(tmp_path / "run" / "world.jsonl")
    report = validate_events(events)
    assert report.ok, report.findings

    emails = [e for e in events if e.payload.kind == "email.message"]
    assert len(emails) == 2, "exogenous email plus the agent's reply"
    assert emails[1].payload.sender == "per-ann-liu"
    assert emails[1].payload.in_reply_to == emails[0].payload.message_id
    assert emails[1].caused_by == emails[0].event_id

    assert turns, "the seat received turns"
    genesis_tags = {o.tag for o in turns[0].observations}
    assert "person.record" in genesis_tags, "genesis context reaches the seat"


async def test_seat_intent_is_grounded_not_trusted(tmp_path: Path) -> None:
    """A chat intent naming an unknown conversation is rejected by the GM,
    recorded as a rejection note, and never becomes a chat message."""

    async def rogue(session: SeatSession) -> None:
        first = True
        while await session.next_turn() is not None:
            if first:
                session.submit(
                    IntentAction(
                        intent=ChatIntent(
                            conversation_ref="#does-not-exist",
                            reply_to_ref=None,
                            draft=ChatDraft(body="hello?", summary="hello"),
                        )
                    )
                )
                first = False
            else:
                session.submit(idle())

    session = SeatSession()
    agent = asyncio.ensure_future(rogue(session))
    async with asyncio.timeout(30):
        await run_workplace(
            make_spec(),
            seed=Seed(root=42),
            out_dir=tmp_path / "run",
            inner_lm=FakeLM(),
            model="test/model",
            external_seats={"ann-liu": session},
        )
        session.end()
        await agent

    events = read_events(tmp_path / "run" / "world.jsonl")
    assert not [e for e in events if e.payload.kind == "chat.message"]
    notes = [e for e in events if e.payload.kind == "sim.gm.note"]
    assert any("does-not-exist" in str(n.payload) for n in notes), (
        "the rejection is recorded, never silently dropped"
    )

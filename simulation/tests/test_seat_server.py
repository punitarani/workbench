"""The seat's MCP surface: an agent drives a full day through tool calls.

The leakage contract is absolute: nothing the server returns may carry
engine envelopes (seq, source, causality) or sim.* events — the agent sees
payload data and sim time only.
"""

import asyncio
import json
from pathlib import Path

import pytest
from mini_workplace import make_spec

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.external.seat_server import build_seat_server
from workbench.simulation.external.session import SeatSession
from workbench.simulation.lm.fake import FakeLM
from workbench.simulation.run import run_workplace

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")
ENVELOPE_KEYS = ("seq", "source", "caused_by", "event_id")


async def call(server, name: str, arguments: dict | None = None) -> dict:
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    [content] = [c for c in result.content if hasattr(c, "text")]
    return json.loads(content.text)


async def drive_day_over_mcp(server, transcript: list[dict]) -> None:
    replied = False
    while True:
        turn = await call(server, "await_turn")
        if turn.get("day_over"):
            return
        transcript.append(turn)
        emails = [o for o in turn["observations"] if o.get("kind") == "email.message"]
        if emails and not replied:
            email = emails[-1]
            await call(
                server,
                "send_email",
                {
                    "to": ["Ravi Dee"],
                    "subject": "Re: Quick question",
                    "body": "Confirmed, thanks.",
                    "thread_ref": email["thread_id"],
                    "reply_to_ref": email["message_id"],
                },
            )
            replied = True
        else:
            await call(server, "idle", {"minutes": 30})


async def test_agent_drives_a_day_through_the_seat_server(tmp_path: Path) -> None:
    session = SeatSession()
    server = build_seat_server(session)
    transcript: list[dict] = []
    agent = asyncio.ensure_future(drive_day_over_mcp(server, transcript))

    async with asyncio.timeout(30):
        result = await run_workplace(
            make_spec(),
            seed=Seed(root=42),
            out_dir=tmp_path / "run",
            inner_lm=FakeLM(),
            model="test/model",
            external_seats={"ann-liu": session},
        )
        session.end()
        await agent

    assert result.reason == "quiescent"
    events = read_events(tmp_path / "run" / "world.jsonl")
    assert validate_events(events).ok

    emails = [e for e in events if e.payload.kind == "email.message"]
    assert len(emails) == 2
    assert emails[1].payload.sender == "per-ann-liu"
    assert emails[1].payload.in_reply_to == emails[0].payload.message_id

    assert transcript, "the agent saw turns"
    rendered = json.dumps(transcript)
    for marker in OFFSTAGE_MARKERS:
        assert marker not in rendered, f"seat surface leaked {marker!r}"
    for turn in transcript:
        for observation in turn["observations"]:
            for key in ENVELOPE_KEYS:
                assert key not in observation, f"envelope key {key!r} leaked"


async def test_acting_without_a_turn_is_a_protocol_error() -> None:
    server = build_seat_server(SeatSession())
    with pytest.raises(Exception, match="no pending turn"):
        await server.call_tool("idle", {"minutes": 5})


async def test_await_turn_reports_day_over() -> None:
    session = SeatSession()
    server = build_seat_server(session)
    session.end()
    assert await call(server, "await_turn") == {"day_over": True}

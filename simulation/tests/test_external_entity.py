import sys
from pathlib import Path

import pytest
from toy_scenario import build_engine, make_entities

from workbench.core.actions import ActRequest, ActResponse, FreeAction, FreeActionSpec
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.errors import ScriptExhaustedError
from workbench.simulation.external.entity import ExternalEntity
from workbench.simulation.external.stdio import StdioTransport
from workbench.simulation.external.transport import (
    InProcessTransport,
    ScriptedTransport,
)


async def run_with_bob_externalized(tmp_path: Path, name: str) -> Path:
    log_path = tmp_path / name
    engine, writer = build_engine(log_path)
    internal_bob = make_entities()[1]
    assert internal_bob.name == "bob"
    external_bob = ExternalEntity(
        name="bob", transport=InProcessTransport(internal_bob)
    )
    engine._entities["bob"] = external_bob
    try:
        await engine.run(StopCondition(max_steps=20))
    finally:
        writer.close()
    return log_path


async def test_external_seat_resolves_identically_to_internal(
    tmp_path: Path,
) -> None:
    internal_log = tmp_path / "internal.jsonl"
    engine, writer = build_engine(internal_log)
    try:
        await engine.run(StopCondition(max_steps=20))
    finally:
        writer.close()

    external_log = await run_with_bob_externalized(tmp_path, "external.jsonl")
    assert external_log.read_bytes() == internal_log.read_bytes()


async def test_act_request_carries_buffered_observations() -> None:
    seen: list[ActRequest] = []

    class Capture:
        async def act(self, request: ActRequest) -> ActResponse:
            seen.append(request)
            return ActResponse(action=FreeAction(text="ok"))

    entity = ExternalEntity(name="bob", transport=Capture())
    from toy_scenario import genesis_events

    event = genesis_events()[-1]
    await entity.observe(event)
    spec = FreeActionSpec(call_to_action="Go.", tag="chat.message")
    await entity.act(spec)
    assert len(seen) == 1
    assert seen[0].entity == "bob"
    assert [e.seq for e in seen[0].observations] == [event.seq]

    await entity.act(spec)
    assert seen[1].observations == (), "buffer drains after each act"


async def test_scripted_transport_exhaustion_raises() -> None:
    transport = ScriptedTransport(
        responses=(ActResponse(action=FreeAction(text="only one")),)
    )
    entity = ExternalEntity(name="bob", transport=transport)
    spec = FreeActionSpec(call_to_action="Go.", tag="chat.message")
    action = await entity.act(spec)
    assert isinstance(action, FreeAction)
    with pytest.raises(ScriptExhaustedError):
        await entity.act(spec)


ECHO_SERVER = '''
import sys, json
for line in sys.stdin:
    request = json.loads(line)
    text = "echo:" + request["spec"]["call_to_action"]
    response = {"action": {"kind": "free", "text": text}}
    sys.stdout.write(json.dumps(response) + "\\n")
    sys.stdout.flush()
'''


async def test_stdio_transport_round_trip(tmp_path: Path) -> None:
    server = tmp_path / "echo_server.py"
    server.write_text(ECHO_SERVER)
    transport = StdioTransport(command=(sys.executable, str(server)))
    entity = ExternalEntity(name="bob", transport=transport)
    try:
        spec = FreeActionSpec(call_to_action="Say hi.", tag="chat.message")
        action = await entity.act(spec)
        assert action == FreeAction(text="echo:Say hi.")
    finally:
        await transport.close()

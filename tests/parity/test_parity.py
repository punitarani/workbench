"""Parity against pinned vendor snapshots.

Official MCP surfaces move: Slack grew from 13 tools to 19 during 2026,
Google's live Gmail server serves eight tools whose doc pages 404, and
iManage publishes descriptions rather than schemas. A test that asserted
"we match the official server" against a live remote would be both flaky
and untrue.

So parity is pinned: each vendor has a dated snapshot under
``snapshots/``, recording what the official surface looked like when it
was captured and how good that capture is. This test asserts our servers
against those files. Every official tool must be either **implemented**
or **waived with a reason** — silence is a failure.

Refreshing a snapshot is a deliberate commit: capture the new
``tools/list``, write a new dated file, update PARITY-MATRIX.md in the
same change, and let review see the diff.
"""

import json
from pathlib import Path

import pytest

from workbench.core.events import Event
from workbench.core.events.control import SimRunStartedPayload
from workbench.tools.framework import build_server, project_system
from workbench.tools.registry import get_system

SNAPSHOTS = Path(__file__).parent / "snapshots"
REPO = Path(__file__).resolve().parents[2]


def _latest_snapshot(vendor: str) -> dict:
    files = sorted(SNAPSHOTS.glob(f"{vendor}-*.json"))
    if not files:
        pytest.skip(f"no pinned snapshot for {vendor}")
    return json.loads(files[-1].read_text(encoding="utf-8"))


def _minimal_world() -> list[Event]:
    """A world with nothing in it but a clock.

    Some servers read the epoch when their tools are registered, so an
    empty projection is not enough to stand one up.
    """

    return [
        Event(
            seq=0,
            event_id="evt-000000",
            time=0,
            tag="sim.run.started",
            source="gm",
            payload=SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-parity",
                seed_root=1,
                workplace_id="parity",
                config_hash="0" * 64,
                schema_version=1,
                epoch="2026-01-05T00:00:00-08:00",
                timezone="America/Los_Angeles",
            ),
        )
    ]


def _served_tools(vendor: str, tmp_path: Path):
    system = get_system(vendor)
    db_path = tmp_path / f"{vendor}.db"
    project_system(system, _minimal_world(), db_path)
    return build_server(system, db_path)


VENDORS = sorted({path.name.split("-")[0] for path in SNAPSHOTS.glob("*.json")})


@pytest.mark.parametrize("vendor", VENDORS)
async def test_every_official_tool_is_implemented_or_waived(
    vendor: str, tmp_path: Path
) -> None:
    snapshot = _latest_snapshot(vendor)
    server = _served_tools(vendor, tmp_path)
    served = {tool.name for tool in await server.list_tools()}
    official = set(snapshot["tools"])
    waived = {
        name.split(".")[0]
        for name in snapshot.get("waived", {})
        if "." not in name  # whole-tool waivers only
    }
    missing = official - served - waived
    assert not missing, (
        f"{vendor}: official tools neither implemented nor waived: "
        f"{sorted(missing)}. Implement them, or add a waiver with a reason "
        f"to {SNAPSHOTS.name}/{vendor}-*.json."
    )


@pytest.mark.parametrize("vendor", VENDORS)
async def test_no_invented_tools(vendor: str, tmp_path: Path) -> None:
    """A tool we serve that the official server does not have is drift too.

    An agent trained against an invented tool learns a call that fails in
    the real product.
    """

    snapshot = _latest_snapshot(vendor)
    server = _served_tools(vendor, tmp_path)
    served = {tool.name for tool in await server.list_tools()}
    extra = served - set(snapshot["tools"]) - {"directory"}
    assert not extra, (
        f"{vendor}: we serve tools the official surface does not: {sorted(extra)}"
    )


@pytest.mark.parametrize("vendor", VENDORS)
async def test_required_parameters_are_present(vendor: str, tmp_path: Path) -> None:
    """Every parameter the official tool requires must exist on ours.

    Optional parameters may lag (recorded as waivers); a missing *required*
    one means a call that works against the official server fails here.
    """

    snapshot = _latest_snapshot(vendor)
    server = _served_tools(vendor, tmp_path)
    waived = set(snapshot.get("waived", {}))
    problems = []
    by_name = {tool.name: tool for tool in await server.list_tools()}
    for tool_name, spec in snapshot["tools"].items():
        tool = by_name.get(tool_name)
        if tool is None:
            continue
        ours = set((tool.input_schema or {}).get("properties", {}))
        for param, signature in spec.get("params", {}).items():
            required = signature.endswith("!")
            if required and param not in ours and f"{tool_name}.{param}" not in waived:
                problems.append(f"{tool_name}.{param}")
    assert not problems, (
        f"{vendor}: required parameters missing from our surface: {sorted(problems)}"
    )


@pytest.mark.parametrize("vendor", VENDORS)
def test_snapshot_records_its_own_provenance(vendor: str) -> None:
    """A snapshot without provenance is an unfalsifiable parity claim."""

    snapshot = _latest_snapshot(vendor)
    for field in ("captured", "provenance", "confidence", "endpoint", "status"):
        assert snapshot.get(field), f"{vendor} snapshot is missing {field}"
    assert snapshot["tools"], f"{vendor} snapshot lists no tools"


def test_parity_matrix_covers_every_vendor() -> None:
    matrix = (REPO / "docs/epochs/v2/PARITY-MATRIX.md").read_text(encoding="utf-8")
    for vendor in VENDORS:
        assert vendor in matrix, f"PARITY-MATRIX.md does not mention {vendor}"

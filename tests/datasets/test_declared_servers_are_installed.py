"""A task that declares a tool the stager never installs has no such tool.

Every task's `[[environment.mcp_servers]]` names an executable under
`/usr/local/bin/`, and the staging script writes one wrapper per entry in
its own `TOOLS` tuple. The two lists are maintained in different files and
drifted: five tasks declared `calendar`, the projection built `calendar.db`,
the stager's tuple did not name it, and the wrapper was never written.

Nothing failed. The server could not spawn, and the agent simply had no
calendar tools -- which presents as a model that ignored the diary.

This compares the two sides directly, because a declaration and an
installation kept in step by hand will not stay in step.
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATASETS = REPO / "datasets"

_STAGER = (DATASETS / "hartwell" / "harbor_stage.py").read_text()
_PREFIX = re.search(r'MCP_WRAPPER_PREFIX = "([^"]+)"', _STAGER)
_TOOLS = re.search(r"^TOOLS = \(([^)]*)\)", _STAGER, re.M)


def _installed() -> set[str]:
    assert _TOOLS, "harbor_stage.py no longer declares a TOOLS tuple"
    return set(re.findall(r'"([a-z]+)"', _TOOLS.group(1)))


# The write-side system is added separately by the stager when its database
# is present, so it is legitimately absent from TOOLS.
_STAGED_SEPARATELY = {"compliance"}


def _tasks() -> list[Path]:
    return sorted(
        p
        for p in DATASETS.glob("*/tasks/*/task.toml")
        if not p.parent.name.startswith("_")
    )


TASKS = _tasks()


def test_the_audit_found_tasks_to_check() -> None:
    assert TASKS, f"no task.toml under {DATASETS}"


def test_the_wrapper_prefix_is_still_parseable() -> None:
    """Guard the guard: if the prefix moves, the check below still passes
    while comparing nothing useful."""

    assert _PREFIX, "harbor_stage.py no longer declares MCP_WRAPPER_PREFIX"


@pytest.mark.parametrize(
    "task", TASKS, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}"
)
def test_declared_servers_are_installed(task: Path) -> None:
    declared = {
        entry["name"]
        for entry in tomllib.loads(task.read_text())
        .get("environment", {})
        .get("mcp_servers", [])
    }
    missing = declared - _installed() - _STAGED_SEPARATELY
    assert not missing, (
        f"{task.parent.name} declares MCP server(s) the stager never installs: "
        f"{sorted(missing)}. The task points at "
        f"{_PREFIX.group(1) if _PREFIX else '<prefix>'}<name>, which is written "
        "only for names in harbor_stage.TOOLS -- so the server cannot spawn and "
        "the agent silently has no such tools."
    )


@pytest.mark.parametrize(
    "task", TASKS, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}"
)
def test_declared_servers_point_at_the_wrappers(task: Path) -> None:
    """A task naming a command other than the wrapper reintroduces the
    adapter bug the wrapper exists to avoid: an adapter that joins command
    and args into one string produces a program name that cannot spawn."""

    assert _PREFIX
    for entry in (
        tomllib.loads(task.read_text()).get("environment", {}).get("mcp_servers", [])
    ):
        command = entry.get("command", "")
        assert command == f"{_PREFIX.group(1)}{entry['name']}", (
            f"{task.parent.name}: server {entry['name']!r} runs {command!r}, "
            f"not the installed wrapper"
        )


def test_every_read_system_is_installed() -> None:
    """The other direction, which nothing checked.

    The tests above catch a task declaring a server the stager never
    installs. Nothing caught a *system that exists and nobody declares* —
    projected into a database, registered, tested, and reachable by no
    agent because no wrapper was written and no task named it.

    That is the same defect as the one this file was written for, one
    level up, and it is how `meeting.transcript` stayed invisible: 723
    transcripts and 255,889 words in the world log, a projection ready to
    serve them, and nothing in the container that could spawn the server.
    """

    import sys

    sys.path.insert(0, str(REPO / "src"))
    from tools import REGISTRY

    built = {system.name for system in REGISTRY}
    missing = built - _installed() - _STAGED_SEPARATELY
    assert not missing, (
        f"these tool systems are in REGISTRY and get no wrapper: {sorted(missing)}. "
        "The database is projected and the server can never spawn, so the "
        "surface exists and no agent can reach it. Add them to "
        "harbor_stage.TOOLS."
    )


@pytest.mark.parametrize(
    "task", TASKS, ids=lambda p: f"{p.parent.parent.parent.name}/{p.parent.name}"
)
def test_merrick_tasks_declare_every_read_surface(task: Path) -> None:
    """A Merrick task that omits a surface is a task whose agent is blind
    to it, with nothing failing to say so.

    Scoped to merrick because the other datasets' worlds predate some of
    these systems and their briefs are written against the surfaces they
    had; widening this would fail them for a corpus they never claimed.
    """

    if task.parent.parent.parent.name != "merrick":
        pytest.skip("scoped to the merrick dataset")
    import sys

    sys.path.insert(0, str(REPO / "src"))
    from tools import REGISTRY

    declared = {
        entry["name"]
        for entry in tomllib.loads(task.read_text())
        .get("environment", {})
        .get("mcp_servers", [])
    }
    expected = {system.name for system in REGISTRY} - _STAGED_SEPARATELY
    assert expected <= declared, (
        f"{task.parent.name} does not declare {sorted(expected - declared)}. "
        "The surface is projected into the bundle and the agent has no tool "
        "for it."
    )

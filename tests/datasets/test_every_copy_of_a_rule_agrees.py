"""Every private copy of a rule must agree with its world's shared module.

The promise rule exists in sixteen implementations here: a shared module
and a shared checker on each world, plus a full private copy inside each of
seven solvers and seven verifiers. Only four tasks import the shared ones.
The seven commitment registers do not — each solver defines its own
`commitment_in`, and that copy is what computes the answer key.

So a fix applied to both shared modules, verified against the whole corpus,
moved zero rows. It ran, it passed its own differential check, and nothing
that builds an answer key imports the file that was edited.

The copies were behaviourally identical before that edit and are again
after it. That is the state this test exists to hold: the danger is never
that a copy is wrong, it is that a copy is right until somebody fixes the
original.

Skips where a world is not materialised — `out/` is not distributed, and a
clone that cannot see a corpus cannot compare behaviour over one.
"""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# The entry points a private copy may define, and the shared module that
# owns each. A rule family absent from a world is simply not compared.
FAMILIES = (("commitment_in", "promise_rule"),)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _cases() -> list[tuple[str, str, str, str]]:
    found = []
    for world in sorted(p for p in (REPO / "datasets").iterdir() if (p / "tasks").is_dir()):
        for task in sorted((world / "tasks").iterdir()):
            solver = task / "solution" / "solve.py"
            if not solver.is_file():
                continue
            body = solver.read_text()
            for entry, shared in FAMILIES:
                if f"\ndef {entry}" in body and (world / f"{shared}.py").is_file():
                    found.append((world.name, task.name, entry, shared))
    return found


@pytest.mark.parametrize(
    "world, task, entry, shared", _cases(), ids=[f"{w}/{t}" for w, t, _e, _s in _cases()]
)
def test_the_private_copy_matches_the_shared_module(
    world: str, task: str, entry: str, shared: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = REPO / "out" / world / "bundle" / "state"
    if not (state / "meetings.db").is_file():
        pytest.skip(f"{world} is not materialised here")

    # These solvers read the environment at IMPORT time. `monkeypatch`
    # rather than `os.environ` because this tree's conftest fails any test
    # that leaks a variable -- one reaches every subprocess a later test
    # starts, and that is how a build once graded against another world.
    monkeypatch.setenv("WORKBENCH_STATE", str(state))
    monkeypatch.setenv(
        "WORKBENCH_WORKSPACE", str(REPO / "out" / world / "bundle" / "workspace")
    )
    sys.path.insert(0, str(REPO / "datasets" / world))
    try:
        for stale in [k for k in sys.modules if k.startswith((shared, "copy_"))]:
            sys.modules.pop(stale)
        module = _load(shared, REPO / "datasets" / world / f"{shared}.py")
        private = _load(
            f"copy_{world}_{task}".replace("-", "_"),
            REPO / "datasets" / world / "tasks" / task / "solution" / "solve.py",
        )
        connection = sqlite3.connect(f"file:{state / 'clio.db'}?mode=ro", uri=True)
        names = [n for (n,) in connection.execute("SELECT name FROM people")]
        connection.close()
        for holder in (module, private):
            if hasattr(holder, "use_roster"):
                holder.use_roster(names)
        connection = sqlite3.connect(f"file:{state / 'meetings.db'}?mode=ro", uri=True)
        turns = [t for (t,) in connection.execute("SELECT text FROM utterances")]
        connection.close()

        theirs, ours = getattr(module, entry), getattr(private, entry)
        differ = [t for t in turns if theirs(t) != ours(t)]
    finally:
        sys.path.remove(str(REPO / "datasets" / world))

    assert not differ, (
        f"{world}/{task}'s own {entry} disagrees with {shared} on "
        f"{len(differ)} of {len(turns)} turns, e.g. {differ[0][:120]!r}. "
        "This task's oracle is built by ITS copy, so the shared module is "
        "not the rule here -- fix every implementation in one change."
    )

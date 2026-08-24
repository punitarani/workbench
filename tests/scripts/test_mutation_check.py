"""The harness that checks the tests has to be checked itself.

Six hand-written mutation sweeps in one day produced three distinct
harness bugs, each of which made the *tests* look wrong when the harness
was: a sweep killed mid-run left the source mutated for the next one, bare
substring anchors mutated a neighbouring function, and an unmatched anchor
aborted a sweep whose caller had already claimed the result.

So `scripts/mutation_check.py` exists, and these are its own tests. They
use a throwaway module and a throwaway test file rather than real ones,
because a harness verified only against code that happens to pass tells
you nothing about the paths where it does not.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOL = REPO / "scripts" / "mutation_check.py"

SOURCE = """
GUARD = 3


def keep(value):
    if value < GUARD:
        return "small"
    return "big"


def unrelated(value):
    if value < GUARD:
        return "other"
    return "other"
"""

TESTS = """
import sys
sys.path.insert(0, {directory!r})
from subject import keep


def test_small():
    assert keep(1) == "small"


def test_big():
    assert keep(9) == "big"
"""


_RUNS = iter(range(1000))


def _run(tmp_path: Path, *mutations: tuple[str, str], function: str | None = None):
    """Each call gets its own directory.

    Sharing one made the second call in a test import the *first* call's
    `__pycache__`: run one mutates `keep`, pytest compiles and caches the
    broken module, and run two -- mutating a different function -- picked
    up the stale bytecode and reported CAUGHT for a mutation nothing could
    see. A harness test that lies about the harness is worse than no test,
    and this one lied in the direction of "your tool works".
    """

    tmp_path = tmp_path / f"run{next(_RUNS)}"
    tmp_path.mkdir()
    source = tmp_path / "subject.py"
    source.write_text(SOURCE)
    tests = tmp_path / "test_subject.py"
    tests.write_text(TESTS.format(directory=str(tmp_path)))
    argv = [
        sys.executable,
        str(TOOL),
        "--source",
        str(source),
        "--tests",
        str(tests),
        "--python",
        sys.executable,
    ]
    if function:
        argv += ["--function", function]
    for before, after in mutations:
        argv += ["--mutation", before, after]
    done = subprocess.run(argv, capture_output=True, text=True, cwd=REPO)
    return done, source


def test_a_caught_mutation_exits_zero(tmp_path: Path) -> None:
    done, _ = _run(tmp_path, ('return "small"', 'return "big"'))
    assert done.returncode == 0, done.stdout + done.stderr
    assert "CAUGHT" in done.stdout


def test_a_surviving_mutation_exits_non_zero(tmp_path: Path) -> None:
    """`unrelated` returns the same value either way — nothing can notice."""

    done, _ = _run(
        tmp_path,
        (
            'return "other"\n    return "other"',
            'return "other"\n    return "other"  # same',
        ),
    )
    assert done.returncode == 1
    assert "SURVIVED" in done.stdout


def test_a_missing_anchor_exits_non_zero(tmp_path: Path) -> None:
    """The bug that let a sweep stop after two of four and say nothing."""

    done, _ = _run(tmp_path, ("no such text", "x"))
    assert done.returncode == 1
    assert "MISSING" in done.stdout
    assert "not found" in done.stderr


def test_the_source_is_restored_even_when_a_mutation_survives(
    tmp_path: Path,
) -> None:
    """The bug that poisoned the next sweep's baseline."""

    done, source = _run(tmp_path, ('return "other"', 'return "OTHER"'))
    assert source.read_text() == SOURCE
    assert "source restored and verified" in done.stdout
    assert hashlib.sha256(source.read_text().encode()).hexdigest() == (
        hashlib.sha256(SOURCE.encode()).hexdigest()
    )


def test_function_scoping_keeps_a_mutation_out_of_its_neighbour(
    tmp_path: Path,
) -> None:
    """The bug that reported three false survivors.

    `if value < GUARD:` appears in both functions. Unscoped, the first
    match is in `keep`, which the tests cover, so it is caught. Scoped to
    `unrelated`, the same text is mutated where nothing looks — and the
    harness must report that honestly rather than reusing the earlier hit.
    """

    caught, _ = _run(tmp_path, ("if value < GUARD:", "if False:"))
    assert caught.returncode == 0 and "CAUGHT" in caught.stdout

    scoped, _ = _run(tmp_path, ("if value < GUARD:", "if False:"), function="unrelated")
    assert scoped.returncode == 1, scoped.stdout
    assert "SURVIVED" in scoped.stdout


def test_scoping_to_a_missing_function_is_an_error(tmp_path: Path) -> None:
    done, _ = _run(tmp_path, ("GUARD", "guard"), function="nonexistent")
    assert done.returncode != 0
    assert "nonexistent" in done.stderr

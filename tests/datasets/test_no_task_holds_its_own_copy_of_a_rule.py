"""No task may vendor a module its world already defines.

One task did. It kept its own `promise_rule.py` in `solution/` and its own
`promise_rule_check.py` in `checks/`, imported them from `parent` rather
than from `parents[3]`, and both drifted away from the world's modules.

The build's strongest gate is that two independently written derivations
of a rule must agree before an oracle ships. It compares them to each
OTHER, so two copies stale in the same direction pass it: the build
printed `second derivation agrees` while the vendored rule admitted 61 of
that world's 1,399 mail messages and the world's rule admitted 57.

Six messages of difference, inside an answer key, behind the check meant
to catch precisely that.

This test is cheap and total: every `.py` under a task that shares a name
with a module at the top of its dataset must be byte-identical to it, and
the honest fix is to import the world's module instead of holding a copy.
"""

import hashlib
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[2] / "datasets"

# The files a task legitimately owns. Everything else sharing a name with a
# world module is a copy.
ITS_OWN = frozenset(
    (
        "solve.py",
        "verify.py",
        "criteria.py",
        "criteria_base.py",
        "grade.py",
        "method.py",
    )
)


def _worlds() -> list[Path]:
    return sorted(p for p in DATASETS.iterdir() if (p / "tasks").is_dir())


def _copies() -> list[tuple[Path, Path]]:
    found = []
    for world in _worlds():
        canonical = {p.name: p for p in world.glob("*.py")}
        for vendored in sorted((world / "tasks").glob("*/*/*.py")):
            if vendored.name in ITS_OWN or "__pycache__" in vendored.parts:
                continue
            source = canonical.get(vendored.name)
            if source is not None:
                found.append((source, vendored))
    return found


@pytest.mark.parametrize(
    "source, vendored",
    _copies(),
    ids=lambda p: str(p).rsplit("datasets/", 1)[-1] if isinstance(p, Path) else "",
)
def test_a_vendored_module_matches_its_world(source: Path, vendored: Path) -> None:
    theirs = hashlib.md5(source.read_bytes()).hexdigest()
    ours = hashlib.md5(vendored.read_bytes()).hexdigest()
    assert ours == theirs, (
        f"{vendored} has drifted from {source}. A task holding its own copy "
        "of a rule is a derivation the agreement gate cannot see going "
        "stale, because it compares the copies to each other. Import the "
        "world's module with parents[3] instead of keeping this."
    )


def test_nothing_vendors_at_all() -> None:
    """Byte-identical today is one edit away from forked tomorrow.

    The hash check above is the safety net. This is the actual rule, and
    it is what makes the net rarely needed: every task in this tree
    imports its world's modules, and none holds a copy.
    """

    copies = [str(v).rsplit("datasets/", 1)[-1] for _s, v in _copies()]
    assert not copies, (
        f"{len(copies)} vendored module(s): {copies}. Import the world's "
        "module rather than copying it; a copy that matches today is one "
        "edit from a fork nothing will report."
    )

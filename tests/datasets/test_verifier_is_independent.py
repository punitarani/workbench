"""A task's verifier must not share the solver's expression of the rule.

The independence check exists so that an answer key is derived twice. If
the second derivation copies the first's regexes, it reproduces the
first's bugs and then certifies that the two agree — a check that cannot
fail. Two published scores were certified that way and both were the
answer key rather than a measurement.

This is a gate rather than a paragraph because a paragraph does not work.
The template these tasks were written from says, in bold, "transcribe the
rule from `instruction.md`, never from `solve.py`". One of the five came
back with **nine verbatim regex literals** shared between the two files
and nineteen shared lines of substantive code. The author had read the
warning.

What is deliberately allowed: imports, path plumbing, and reading the
served state. Those are how a file gets to the data, not what it decides
once there. The rule is about the *expression of the rule*.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "datasets" / "merrick" / "tasks"

# A raw-string literal long enough to encode a rule rather than a
# separator. `r"\\s+"` is shared plumbing; a seven-form alternation is the
# rule itself.
_RULE_LITERAL = re.compile(r'r"[^"]{10,}"')

# Lines that are how a file reaches the data rather than what it decides.
_PLUMBING = re.compile(
    r"^\s*(import|from|sys\.path|WORKSPACE|STATE|def main|if __name__"
    r"|conn\s*=|cursor|\.execute\(|json\.dump|argparse|Path\()",
)

MAX_SHARED_LITERALS = 0
# Some overlap in long lines is unavoidable — a shared column list, a
# shared output field order. Nineteen is a copied rule; a handful is not.
MAX_SHARED_CODE_LINES = 10


def _tasks() -> list[Path]:
    if not TASKS.is_dir():
        return []
    return sorted(
        p
        for p in TASKS.iterdir()
        if p.is_dir()
        and not p.name.startswith("_")
        and (p / "solution" / "solve.py").is_file()
        and (p / "tests" / "verify.py").is_file()
    )


PAIRS = _tasks()


def test_the_audit_found_tasks_to_check() -> None:
    """Guard the guard: with no task pairs this passes vacuously, and this
    dataset's tasks are written over time."""

    assert PAIRS, f"no solver/verifier pairs under {TASKS}"


def _substantive(text: str) -> set[str]:
    return {
        line.strip()
        for line in text.splitlines()
        if len(line.strip()) > 40
        and not line.strip().startswith("#")
        and not _PLUMBING.match(line)
    }


@pytest.mark.parametrize("task", PAIRS, ids=lambda p: p.name)
def test_the_verifier_does_not_copy_the_solvers_rule(task: Path) -> None:
    solver = (task / "solution" / "solve.py").read_text()
    verifier = (task / "tests" / "verify.py").read_text()

    shared_literals = set(_RULE_LITERAL.findall(solver)) & set(
        _RULE_LITERAL.findall(verifier)
    )
    assert len(shared_literals) <= MAX_SHARED_LITERALS, (
        f"{task.name}: verifier reuses {len(shared_literals)} of the solver's "
        f"own rule literals, so it cannot disagree with them: "
        f"{sorted(shared_literals)[:3]}. Transcribe the rule from "
        "instruction.md — the prose the agent is graded against."
    )

    shared_lines = _substantive(solver) & _substantive(verifier)
    assert len(shared_lines) <= MAX_SHARED_CODE_LINES, (
        f"{task.name}: {len(shared_lines)} substantive lines are identical "
        f"in both files. Example: {sorted(shared_lines)[0][:70]!r}"
    )


@pytest.mark.parametrize("task", PAIRS, ids=lambda p: p.name)
def test_the_verifier_is_not_a_stub(task: Path) -> None:
    """The template ships a `verify.py` that raises. A task that never
    replaced it has no independent derivation at all, and the gate above
    would pass it happily — zero shared literals."""

    verifier = (task / "tests" / "verify.py").read_text()
    assert "verify.py is a template" not in verifier, (
        f"{task.name}: verify.py is still the template stub"
    )
    assert len(verifier.splitlines()) > 30, (
        f"{task.name}: verify.py is too short to be a second derivation"
    )


# A verifier is only a check on the rules it actually reads from the
# brief. Anything it hardcodes, it hardcodes identically to the solver —
# and then the two agree about a rule neither of them re-derived.
_PINS = (
    "insists(",  # assert the brief still carries a phrase
    "_STATED",  # the phrase table
    "_fields_pinned",
    "_hardcoded",
    "_past_words",
)


@pytest.mark.parametrize("task", PAIRS, ids=lambda p: p.name)
def test_the_verifier_pins_its_assumptions_to_the_brief(task: Path) -> None:
    """Zero shared code is not enough: two files can hardcode the same
    reading of a spec and never disagree.

    Measured on one task here — a verifier sharing nothing with its
    solver, gate clean, that read two of the instruction table's three
    columns and hardcoded the third. The brief could say `end of week`
    means the Sunday and both would compute the Friday, agree, and report
    an independent reading. **20 of 27 brief mutations went unnoticed.**

    The repair is to assert the brief still states what the arithmetic
    assumes. This checks the repair is present; only mutating the brief
    checks that it works, which is what the task's own suite does.
    """

    verifier = (task / "tests" / "verify.py").read_text()
    assert any(pin in verifier for pin in _PINS), (
        f"{task.name}: verify.py reads the brief but never asserts it still "
        "says what the arithmetic assumes. A rule the verifier hardcodes is "
        "a rule the second derivation does not check — flip it in the brief "
        "and nothing fails."
    )

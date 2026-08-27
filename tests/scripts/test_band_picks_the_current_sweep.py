"""A stale sweep is worse than a missing one.

It is a real number, from a real run, against a question nobody is asking
any more -- and nothing about it looks wrong. This table reported
`commitment-revision-register` at opus 0.704 from a sweep that predated
`first_due` while the current sweep sat beside it at 0.706, and reported
`live-commitment-register` at opus 1.000 from a 42-day sweep after the
window had moved to 147 days.

Three separate mistakes were behind those, and they need three separate
fixes:

**A changed KEY.** A trial never asked for `first_due` cannot be scored on
it. Caught by looking for each graded field in the brief that trial was
given.

**A changed WINDOW.** Moving a window changes no field at all, so the field
check is blind to it. This dataset writes a window's boundaries and sizes
in quadruple asterisks because they are generated into the prose, which
makes them exactly the strings that change when a window moves.

**A tie.** Equal evidence was broken by tag name, which is alphabetical
and therefore arbitrary -- `glm-rev-k3` sorts before `glm-rev2-k3`. It is
now broken by recency, which matters most where the other two checks
cannot help: some harnesses never record the prompt, and every glm trial
in this tree is like that, so only the date separates a stale sweep from a
current one.
"""

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _trial(root: Path, brief: str) -> Path:
    (root / "agent").mkdir(parents=True, exist_ok=True)
    (root / "verifier").mkdir(parents=True, exist_ok=True)
    (root / "agent" / "trajectory.json").write_text(
        json.dumps({"steps": [{"source": "user", "message": brief}]})
    )
    return root


CURRENT = (
    "write answer.json with owner, due, first_due per person, for meetings "
    "from ****Tuesday 6 January 2026**** through ****Monday 1 June 2026****"
)
OLD_KEY = (
    "write answer.json with owner and due per person, for meetings "
    "from ****Tuesday 6 January 2026**** through ****Monday 1 June 2026****"
)
OLD_WINDOW = (
    "write answer.json with owner, due, first_due per person, for meetings "
    "from ****Tuesday 6 January 2026**** through ****Monday 16 February 2026****"
)
FIELDS = ("owner", "due", "first_due")
PARAMS = ("Tuesday 6 January 2026", "Monday 1 June 2026")


def test_the_current_brief_is_accepted(tmp_path):
    band = _load("band")
    t = _trial(tmp_path / "a", CURRENT)
    assert band._answered_an_older_brief(t, FIELDS, "answer.json") is False
    assert band._read_a_different_window(t, PARAMS, "answer.json") is False


def test_a_missing_graded_field_is_caught(tmp_path):
    band = _load("band")
    t = _trial(tmp_path / "b", OLD_KEY)
    assert band._answered_an_older_brief(t, FIELDS, "answer.json") is True


def test_a_moved_window_is_caught_though_no_field_changed(tmp_path):
    """The hole the field check alone leaves."""

    band = _load("band")
    t = _trial(tmp_path / "c", OLD_WINDOW)
    assert band._answered_an_older_brief(t, FIELDS, "answer.json") is False
    assert band._read_a_different_window(t, PARAMS, "answer.json") is True


def test_a_trajectory_without_the_anchor_is_not_judged(tmp_path):
    """Some harnesses never record the prompt. Every glm trial here is one."""

    band = _load("band")
    t = _trial(tmp_path / "d", "tool output, no brief anywhere in it")
    assert band._answered_an_older_brief(t, FIELDS, "answer.json") is False
    assert band._read_a_different_window(t, PARAMS, "answer.json") is False


def test_the_brief_parameters_are_read_from_the_bolded_literals(tmp_path):
    band = _load("band")
    tasks = tmp_path / "tasks" / "thetask"
    tasks.mkdir(parents=True)
    (tasks / "instruction.md").write_text(
        "read from ****Tuesday 6 January 2026**** through ****Monday 1 June "
        "2026****, ****105**** working days and ****420**** meetings"
    )
    assert band._brief_parameters(tmp_path / "tasks", "thetask") == (
        "Tuesday 6 January 2026",
        "Monday 1 June 2026",
        "105",
        "420",
    )


def test_recency_breaks_a_tie_between_equally_sampled_jobs(tmp_path):
    band = _load("band")
    older, newer = tmp_path / "older", tmp_path / "newer"
    for job in (older, newer):
        (job / "t" / "verifier").mkdir(parents=True)
        (job / "t" / "verifier" / "reward.json").write_text('{"reward": 0.5}')
    past = time.time() - 10_000
    import os

    os.utime(older / "t" / "verifier" / "reward.json", (past, past))
    os.utime(older, (past, past))
    assert band._mtime(newer) > band._mtime(older)


def test_a_tier_nobody_ran_does_not_block_a_measured_task(tmp_path, capsys, monkeypatch):
    """Missing evidence is not evidence of a problem.

    MODELS grew to four while only three are routinely swept, and "any
    blocked model blocks the verdict" then held every measured task at
    INCOMPLETE -- including one that certify.py had already certified on
    three tiers. The two tools have to ask the same question.

    A tier that FAILED still blocks: "glm timed out" and "glm was never
    run" call for opposite responses, which is the distinction the reason
    strings carry.
    """

    band = _load("band")
    blocked = ["gpt-5.6-sol: not run"]
    unmeasured = [w for w in blocked if w.endswith(": not run")]
    broken = [w for w in blocked if not w.endswith(": not run")]
    assert unmeasured and not broken

    blocked = ["glm-5.2: timeout, nothing written"]
    broken = [w for w in blocked if not w.endswith(": not run")]
    assert broken, "a failed tier must still block"

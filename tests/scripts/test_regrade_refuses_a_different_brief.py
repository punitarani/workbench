"""Re-scoring an answer to a different question is not a measurement.

`regrade` exists so that correcting an oracle does not cost a sweep per
tier: the agent's work is on disk and a corrected key is a better grader of
the same work. That holds only while the BRIEF is the same. Once the brief
gains a field, the old deliverable is a complete answer to a question
nobody is asking, and scoring it against the new key produces a low number
with no meaning.

This is not hypothetical. A kimi trial that returned 26 rows and a
superseded count of 127 against a true 128 scored 0.200 -- the
empty-register floor -- because `first_due` entered the key while it ran.

The check is deliberately narrow. Trials keep no copy of `instruction.md`,
so it asks the only question that matters: does every field the current
key GRADES appear in the brief that trial was given? Hashing the
instruction would be stricter and useless, because the brief is reformatted
into a larger prompt and a digest would refuse every trial ever run.

Its first version described this check in the docstring and did not
implement it -- it printed a digest and compared nothing. Hence a test.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _trial(tmp_path: Path, brief: str) -> Path:
    trial = tmp_path / "thetask__t1"
    (trial / "agent").mkdir(parents=True)
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps([{"role": "user", "content": brief}])
    )
    return trial


GRADED = {"owner", "due", "first_due", "superseded"}
ANCHOR = "answer.json"

NEW_BRIEF = "write answer.json with owner, due, first_due and superseded per person"
OLD_BRIEF = "write answer.json with owner, due and superseded per person"


def test_a_trial_given_the_current_brief_is_comparable(tmp_path):
    regrade = _load("regrade")
    assert regrade._answered_this_brief(_trial(tmp_path, NEW_BRIEF), GRADED, ANCHOR) == set()


def test_a_trial_given_an_older_brief_is_refused(tmp_path):
    regrade = _load("regrade")
    missing = regrade._answered_this_brief(_trial(tmp_path, OLD_BRIEF), GRADED, ANCHOR)
    assert missing == {"first_due"}, missing


def test_a_trial_with_no_trajectory_is_not_refused_on_that_alone(tmp_path):
    """Absence of evidence is not evidence. A trial whose trajectory was
    never written cannot be checked, and refusing it would quietly drop
    work for a reason unrelated to the brief."""

    regrade = _load("regrade")
    bare = tmp_path / "thetask__t2"
    bare.mkdir()
    assert regrade._answered_this_brief(bare, GRADED, ANCHOR) == set()


def test_a_trajectory_that_never_recorded_the_brief_is_not_evidence(tmp_path):
    """The failure this check had on its first run, pinned.

    Trajectories are compacted and truncated. A field missing from one is
    not evidence the brief lacked it -- and reported as though it were, it
    refused six real measurements, including a trial that had "never been
    asked for owner" whose every row was keyed on owner.
    """

    regrade = _load("regrade")
    silent = _trial(tmp_path, "tool call output with no brief in it at all")
    assert regrade._answered_this_brief(silent, GRADED, ANCHOR) == set()

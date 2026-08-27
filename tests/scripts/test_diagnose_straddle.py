"""Nobody earned it is two findings, and reporting them as one deletes a
criterion that was working.

`superseded_count` reads 0.000 for every trial of every tier on
`standing-commitment-register`. The rule that fires on that -- a criterion
no trial ever earns is a claim about the key -- is a good rule with one
blind spot: it cannot see WHERE the answers sit relative to the key.

    oracle 132    opus 123, 124, 118    glm 98, 134, 95

Those straddle it. Readers who disagree with the key in both directions
agree with the key on average and are merely imprecise -- opus within
6-11%, scored zero three times of three because an exact grade on a
three-digit figure cannot express a near miss. That is a hard criterion.

A convention mismatch looks different and is the case the rule was written
for: every reader on the SAME side, agreeing with each other and not with
the key. This dataset has one on record, where a register's rows were
graded against a rule the brief did not state and three model families
declined all eleven of them.

Acting on the first as though it were the second would have removed the
only criterion separating the tiers on that task.
"""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _fixture(tmp_path: Path, answers: list[int], truth: int = 132) -> tuple:
    """A task dir and one job of three trials, each answering `answers[i]`."""

    task_dir = tmp_path / "task"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "tests" / "oracle.json").write_text(
        json.dumps({"superseded_count": truth, "live": []})
    )
    (task_dir / "tests" / "criteria.py").write_text('DELIVERABLE = "answer.json"\n')

    job = tmp_path / "jobs" / "ds-thetask-tag-k3"
    for index, value in enumerate(answers):
        trial = job / f"thetask__t{index}"
        (trial / "verifier").mkdir(parents=True)
        (trial / "verifier" / "reward-details.json").write_text(
            json.dumps(
                {
                    "answer": {
                        "criteria": [
                            {"name": "superseded_count", "value": 0.0},
                            {"name": "live.f1", "value": 0.95},
                        ]
                    }
                }
            )
        )
        (trial / "verifier" / "submitted-answer.json").write_text(
            json.dumps({"superseded_count": value})
        )
    return task_dir, [job]


def test_answers_straddling_the_key_are_not_reported_as_a_defect(tmp_path, capsys):
    diagnose = _load("diagnose")
    task_dir, jobs = _fixture(tmp_path, [123, 124, 134])
    diagnose.criteria_table(task_dir, jobs, "thetask")
    out = capsys.readouterr().out
    assert "STRADDLE" in out, out
    assert "claim\n     about the key" not in out, out


def test_answers_all_on_one_side_are_reported_as_a_defect(tmp_path, capsys):
    diagnose = _load("diagnose")
    task_dir, jobs = _fixture(tmp_path, [62, 61, 63])
    diagnose.criteria_table(task_dir, jobs, "thetask")
    out = capsys.readouterr().out
    assert "STRADDLE" not in out, out
    assert "claim" in out and "about the key" in out, out
    # The figures themselves, so the reader can see the offset that makes
    # it a convention mismatch rather than taking the verdict on trust.
    assert "61..63 vs 132" in out, out


def test_a_criterion_every_trial_earns_is_reported_as_neither(tmp_path, capsys):
    """The rule is about criteria nobody earns; a passing one says nothing."""

    diagnose = _load("diagnose")
    task_dir, jobs = _fixture(tmp_path, [132, 132, 132])
    for trial in (jobs[0]).iterdir():
        details = trial / "verifier" / "reward-details.json"
        data = json.loads(details.read_text())
        data["answer"]["criteria"][0]["value"] = 1.0
        details.write_text(json.dumps(data))
    diagnose.criteria_table(task_dir, jobs, "thetask")
    out = capsys.readouterr().out
    assert "STRADDLE" not in out and "claim about the key" not in out, out

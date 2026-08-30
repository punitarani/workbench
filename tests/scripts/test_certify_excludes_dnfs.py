"""The final gate documented a check it did not perform.

`certify.py` opens with: "A DNF is excluded rather than averaged as a
zero: how well a model answers and how often it manages to answer are
different facts, and folding one into the other puts any task in any band
you like."

Its `_rewards` read `reward.json` for every trial, DNFs included.

That is not a cosmetic error and it does not fail safe. A DNF averaged as
zero drags an ABOVE-band task DOWN into range, so the more often a tier
fails to answer, the more certifiable the task looks. It happened:
`standing-commitment-register` certified with kimi reading
[0.0, 0.346, 0.383] for a mean of 0.243, where the 0.0 was a trial that
wrote no deliverable. Excluding it leaves two graded trials, which is
below the three the same file requires -- so the honest verdict was NOT
CERTIFIED, and the bug had reversed it.

`band` already owns the reasons a zero is not a score. This asserts that
`certify` uses that module rather than a second copy of the rule.
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


def _job(
    tmp_path: Path,
    rewards: list[float],
    *,
    wrote: list[bool],
    finished: list[bool] | None = None,
) -> Path:
    job = tmp_path / "jobs" / "ds-thetask-tag"
    ran = finished if finished is not None else [True] * len(rewards)
    for index, (value, made_file, completed) in enumerate(zip(rewards, wrote, ran)):
        trial = job / f"thetask__t{index}"
        (trial / "verifier").mkdir(parents=True)
        (trial / "verifier" / "reward.json").write_text(json.dumps({"reward": value}))
        if made_file:
            (trial / "verifier" / "submitted-answer.json").write_text("{}")
        # The harness writes `result.json` when a trial runs to completion,
        # and both gates require it. A fixture without one models a trial
        # that cannot happen, and left this suite passing while certify and
        # band disagreed about whether a tier existed.
        if completed:
            (trial / "result.json").write_text(json.dumps({"trial": f"t{index}"}))
    return job


def _tasks_dir(tmp_path: Path) -> Path:
    tasks = tmp_path / "tasks" / "thetask" / "tests"
    tasks.mkdir(parents=True)
    (tasks / "criteria.py").write_text(
        'DELIVERABLE = "answer.json"\nKEY = ("owner",)\nFIELDS = {}\n'
    )
    (tasks.parent / "instruction.md").write_text("write answer.json")
    return tmp_path / "tasks"


def test_a_trial_that_wrote_nothing_is_not_averaged_in(tmp_path):
    certify = _load("certify")
    job = _job(tmp_path, [0.0, 0.346, 0.383], wrote=[False, True, True])
    got = certify._rewards(job, "thetask", _tasks_dir(tmp_path))
    assert got == [0.346, 0.383], got
    assert sum(got) / len(got) > 0.36, "the DNF must not drag the mean down"


def test_every_trial_answering_is_kept(tmp_path):
    certify = _load("certify")
    job = _job(tmp_path, [0.4, 0.5, 0.6], wrote=[True, True, True])
    assert certify._rewards(job, "thetask", _tasks_dir(tmp_path)) == [0.4, 0.5, 0.6]


def test_without_a_tasks_dir_it_falls_back_rather_than_crashing(tmp_path):
    """The deliverable's name is what makes the DNF check possible; with no
    way to learn it, reading the rewards plainly is better than failing."""

    certify = _load("certify")
    job = _job(tmp_path, [0.0, 0.5], wrote=[False, True])
    assert certify._rewards(job, "thetask") == [0.0, 0.5]


def test_a_trial_the_harness_never_finished_is_not_counted(tmp_path: Path) -> None:
    """No `result.json` means the harness has no record the trial ran.

    `band.py` has always required it. `certify.py` did not, so the two
    could disagree about whether a tier existed -- and did, on a task that
    certified while band reported "glm-5.2: not run" from the same jobs.

    The publication gate must be at least as strict as the tool reporting
    the band, or "certified" and "in band" stop describing the same
    evidence.
    """

    certify = _load("certify")
    job = _job(
        tmp_path,
        [0.4, 0.5, 0.6],
        wrote=[True, True, True],
        finished=[True, True, False],
    )
    kept = certify._rewards(job, "thetask", _tasks_dir(tmp_path))
    assert kept == [0.4, 0.5], (
        "a trial with no result.json was counted; band would refuse it and "
        f"the two gates would disagree. Got {kept}"
    )

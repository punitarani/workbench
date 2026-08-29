"""The three-model mean per task, and whether it is real.

    uv run python scripts/band.py --dataset <name>
    uv run python scripts/band.py --dataset <name> --tag-opus fair-k3

The target is a task whose score, averaged over gpt-5.6-sol, Opus 5 and
glm-5.2, lands in 0.2-0.8. Averaging invites one specific way of cheating
yourself, so this refuses it:

**A DNF is not a zero.** A model that ran out of clock, or ended its turn
believing sub-agents were still working, or never wrote the deliverable at
all, has not scored 0.000 -- it has not scored. Averaged in as a zero it
drags any task into the band: Opus 1.000 + Sol 0.600 + glm *nothing*
reads as 0.533, which looks like a well-calibrated task and is really a
broken measurement wearing one's clothes.

**But a DNF is not a disqualification either.** How well a model answers
and how often it manages to answer at all are different facts, and
collapsing them in either direction loses one of them. gpt-5.6-sol on
`approval-register`: 47 steps and 0.997 on one trial, 5 and 7 steps and
no deliverable on the other two. The task is plainly solvable by it, and
a rule that discards the 0.997 because it is outnumbered reports nothing
at all about a model that nearly aced the work.

So the score is the mean over **gradeable trials only**, at least two of
them so it is never a single sample, and the completion rate is printed
beside it rather than folded into it. Below two, the task is reported
loudly as incomplete -- with the reason, because "glm timed out" and
"glm answered badly" call for opposite fixes.
"""

import argparse
import ast
import json
import re
import statistics
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JOBS = REPO / "jobs"
DATASETS = REPO / "datasets"

# Two, not a majority. One gradeable trial is an anecdote; two is an
# estimate. Requiring a majority threw away a 0.997 on a task the model
# demonstrably solves, because its other two attempts ended in an
# orchestration failure that says nothing about the task.
_MIN_GRADEABLE = 2

# The three the goal names, in the order a report should read.
# The sign-off trio for merrick: a frontier tier, a strong mid tier, and
# an open-weights tier, so a band is read across capability rather than
# across one vendor. glm-5.2 stays routable as a fallback.
# One width for the header and the row, so the two cannot drift.
_COLUMN = 13

MODELS = ("gpt-5.6-sol", "opus-5", "glm-5.2", "kimi-k3")

# The short prefix each model's job tags carry. Shared with the rollout
# writer, because a writer and a reader that disagree about a job name
# fail silently -- the sweep runs, the scores land, and this reports "not
# run", which is indistinguishable from never having measured.
TAG_PREFIX = {
    "gpt-5.6-sol": "gpt",
    "opus-5": "opus",
    "glm-5.2": "glm",
    "kimi-k3": "kimi",
}


# Several tags per model, newest first: the k=9 re-samples live under their
# own, and a world's scores must never be read beside another's. Requiring
# the reader to remember which tag holds the best evidence is how a task
# that *is* in band gets reported as 0 in band -- which happened, on the
# first one that qualified.
#
# `-v7-` is the merrick run on the oracle whose eleven bad rows were the
# score; `-v8-` the one whose three were; `-v9-` the corrected task. They
# are listed newest first and never merged: a run against a different
# oracle is a different measurement.
#
# Module level, not a local inside `main`, because the test that checks a
# sweep writes a tag the aggregator searches used to keep its OWN copy of
# this table. A hand-kept copy of the thing under test cannot fail for the
# right reason -- it only fails when it goes stale, which is how adding a
# fourth tier broke it.
# `<prefix>-k9` is on every row because that is what `rollout.py` writes
# when nobody passes `--tag`, and a default sweep whose scores the default
# reader cannot find is the exact failure this table exists to prevent.
DEFAULT_TAGS: dict[str, list[str]] = {
    "gpt-5.6-sol": [
        "gpt-v10-k3",
        "gpt-v9-k3",
        "gpt-v8-k3",
        "gpt-v7-k3",
        "gpt-k9",
        "gpt-k3",
    ],
    "opus-5": [
        "opus-v10-k3",
        "opus-v9-k3",
        "opus-v8-k3",
        "opus-v7-k3",
        "opus-k9",
        "fair-k3",
    ],
    "glm-5.2": [
        "glm-v10-k3",
        "glm-v9-k3",
        "glm-v8-k3",
        "glm-v7-k3",
        "glm-k9",
        "glm-fair",
    ],
    "kimi-k3": ["kimi-v10-k3", "kimi-v9-k3", "kimi-v8-k3", "kimi-v7-k3", "kimi-k9"],
}


def _trials(job: Path) -> list[Path]:
    if not job.is_dir():
        return []
    return sorted(
        p for p in job.iterdir() if p.is_dir() and (p / "result.json").is_file()
    )


def _retired(task: Path) -> bool:
    """Whether this task was withdrawn on measured evidence.

    Three of this dataset's tasks were retired and simply left in place,
    which was invisible: they carry a full `task.toml`, an instruction and
    a solver, and differ from a live task only in never having been built.
    A reader that iterates the directory cannot tell them apart, so it
    either reports tasks nobody intends to run or -- once it began
    refusing tasks whose deliverable it cannot name -- stops on one.
    """

    manifest = task / "task.toml"
    if not manifest.is_file():
        return False
    return any(
        line.split("#", 1)[0].replace(" ", "").startswith("retired=true")
        for line in manifest.read_text(encoding="utf-8").splitlines()
    )


class UnknownDeliverable(SystemExit):
    """The reader cannot tell what file the task asked for."""


def _deliverable(tasks_dir: Path, task: str) -> str:
    """The file this task asks the agent to write.

    Read from the task's own `criteria.py`, which is where the name lives.
    This looked for a line starting with `D =` in `grade.py`, and
    `grade.py` declares `DELIVERABLE = criteria.DELIVERABLE` -- so it
    returned None for every task in the dataset.

    That mattered because of how the caller used it. `_outcome` guarded
    its DNF check with `if wanted and ...`, so a None turned the check
    off: a trial that wrote no deliverable at all fell through to
    `reward.json`, which `test.sh` writes as 0.0 whatever happened. Every
    did-not-finish was being averaged in as a **zero** -- which is the
    precise failure this module's own docstring exists to prevent, and it
    fails in the flattering direction, dragging any task toward the band.

    Raising rather than returning None is the other half of the fix. A
    reader that cannot tell what the task asked for must stop, not quietly
    grade as though every trial answered.
    """

    criteria = tasks_dir / task / "tests" / "criteria.py"
    if not criteria.is_file():
        raise UnknownDeliverable(
            f"{task}: no tests/criteria.py, so there is no way to tell "
            "whether a trial produced an answer or nothing at all."
        )
    tree = ast.parse(criteria.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "DELIVERABLE":
                value = ast.literal_eval(node.value)
                if isinstance(value, str) and value:
                    return value
    raise UnknownDeliverable(
        f"{task}: tests/criteria.py names no DELIVERABLE. Without it a "
        "trial that wrote nothing is indistinguishable from one that "
        "answered badly, and the two average differently."
    )


# Reasons a cell is empty that mean "nothing was measured here on this
# version", as opposed to "this tier was measured and it went wrong".
_NO_CURRENT_RUN = re.compile(
    r": not run$|superseded key|older brief|different window"
)


def _mtime(job: Path) -> float:
    """When this job last produced anything, for breaking ties by recency."""

    if not job.is_dir():
        return 0.0
    stamps = [job.stat().st_mtime]
    stamps.extend(p.stat().st_mtime for p in job.glob("*/verifier/reward.json"))
    return max(stamps)


def _graded_fields(tasks_dir: Path, task: str) -> tuple[str, ...]:
    """Every field this task's key and per-row checks are scored on."""

    criteria = tasks_dir / task / "tests" / "criteria.py"
    if not criteria.is_file():
        return ()
    found: dict[str, object] = {}
    for node in ast.parse(criteria.read_text(encoding="utf-8")).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in ("KEY", "FIELDS"):
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return tuple(found.get("KEY", ())) + tuple(found.get("FIELDS", ()))


def _brief_parameters(tasks_dir: Path, task: str) -> tuple[str, ...]:
    """The bolded literals the brief states as its own parameters.

    This dataset writes a window's boundaries and sizes in quadruple
    asterisks -- `****Monday 1 June 2026****`, `****105****`, `****420****`
    -- because they are generated into the prose rather than typed. That
    makes them exactly the strings that change when a window moves, and a
    window can move without any FIELD changing, which is the hole the field
    check alone leaves: a 42-day sweep and a 147-day sweep of the same task
    ask for the same columns and are not the same measurement.
    """

    brief = tasks_dir / task / "instruction.md"
    if not brief.is_file():
        return ()
    return tuple(
        dict.fromkeys(re.findall(r"\*{4}([^*]+)\*{4}", brief.read_text()))
    )


def _answered_an_older_brief(trial: Path, fields: tuple[str, ...], anchor: str) -> bool:
    """Whether this trial was given a brief that predates the current key.

    A stale sweep is worse than a missing one: it is a real number, from a
    real run, against a question nobody is asking any more. This table read
    `commitment-revision-register` at opus 0.704 from a sweep that predated
    `first_due` while the current sweep sat beside it at 0.706 -- and
    picked the stale one because "best evidence" meant "most gradeable
    trials".

    The witness has to be testifying first: trajectories are compacted and
    sometimes never record the prompt, so the deliverable's own name must
    appear before any field's absence is read as evidence. Without that
    guard the same check refused six real measurements elsewhere, including
    a trial reported as never having been asked for `owner` whose every row
    was keyed on owner.
    """

    trajectory = trial / "agent" / "trajectory.json"
    if not fields or not trajectory.is_file():
        return False
    seen = trajectory.read_text(encoding="utf-8", errors="replace")
    if anchor not in seen:
        return False
    return any(f'"{field}"' not in seen and field not in seen for field in fields)


def _read_a_different_window(trial: Path, parameters: tuple[str, ...], anchor: str) -> bool:
    """Whether the brief this trial was given stated different parameters."""

    trajectory = trial / "agent" / "trajectory.json"
    if not parameters or not trajectory.is_file():
        return False
    seen = trajectory.read_text(encoding="utf-8", errors="replace")
    if anchor not in seen:
        return False
    return any(value not in seen for value in parameters)


def _graded_before_the_key(trial: Path, oracle: Path) -> bool:
    """Whether this trial was scored against an oracle that has since moved.

    The content checks above need the brief to be in the trajectory. Some
    harnesses never put it there -- every glm trial in this tree is one --
    and for those, a stale sweep is invisible: `glm-v10-k3` answered the
    42-day task, scored 3 of 3, and was preferred over the current 147-day
    sweep because it had one more gradeable trial.

    This needs nothing from the trial. Harbor writes `reward.json` when the
    trial finishes, using whatever `tests/oracle.json` says at that moment.
    If the oracle has been rewritten since, that number was computed
    against a key that no longer exists, whatever the agent was asked. It
    is not a current measurement.

    The saved deliverable is still good -- `scripts/regrade.py` re-scores
    it against the current key, which is the right tool when only the key
    moved. This one is about which sweep a BAND verdict may rest on, and
    the answer is never a reward computed from a superseded oracle.

    Mtimes are a working-tree fact: a fresh clone rewrites them all and
    this check goes quiet. It is a guard for the machine doing the work,
    which is where stale sweeps accumulate.
    """

    reward = trial / "verifier" / "reward.json"
    if not reward.is_file() or not oracle.is_file():
        return False
    return reward.stat().st_mtime < oracle.stat().st_mtime


def _served_garbage(trial: Path) -> bool:
    """Whether the provider returned text that is not language.

    A sixth cause of 0.000, and it is not a fact about the model. A glm
    trial ended after five steps having emitted

        .I meetings. . -  |. meeting  .  |   -6.. Meeting  0:Let  It If

    -- a decoding fault on a quantized endpoint, scored as though the model
    could not read a transcript. Averaged in as a zero it would have
    dragged the tier below band on a task it answers at 0.5.

    Measured over every glm trial in this tree before shipping: 1 of 30 is
    degenerate by this test, and it is the one that produced the text
    above. A test that flagged more would be catching terse answers, not
    broken ones.

    The threshold looks at the agent's OWN turns only. Tool output is full
    of tables and punctuation and would trip any such rule.
    """

    trajectory = trial / "agent" / "trajectory.json"
    if not trajectory.is_file():
        return False
    try:
        recorded = json.loads(trajectory.read_text(encoding="utf-8", errors="replace"))
    except ValueError:
        return False
    steps = recorded.get("steps", []) if isinstance(recorded, dict) else []
    for step in steps:
        if step.get("source") != "agent":
            continue
        said = str(step.get("message", ""))
        if len(said) < 40:
            continue
        words = re.findall(r"[A-Za-z]{2,}", said)
        if len(" ".join(words)) < 0.35 * len(said):
            return True
    return False


def _outcome(
    trial: Path,
    wanted: str,
    fields: tuple[str, ...] = (),
    parameters: tuple[str, ...] = (),
    oracle: Path | None = None,
) -> tuple[float | None, str]:
    """The trial's score, or None with the reason it is not one."""

    if oracle is not None and _graded_before_the_key(trial, oracle):
        return None, "graded against a superseded key"
    if _answered_an_older_brief(trial, fields, wanted):
        return None, "answered an older brief"
    if _read_a_different_window(trial, parameters, wanted):
        return None, "read a different window"
    verifier = trial / "verifier"
    # A timeout is only a DNF when nothing was written. If the deliverable
    # is there and the grader scored it, the trial answered -- and the
    # score is what the model produced inside its budget, which is the
    # thing being measured.
    #
    # This was the other way round, and it mattered: on
    # opening-days-commitment-register the two timed-out trials scored
    # 0.720 and 0.770 against a 0.655 average for the rest. A truncated
    # write scores low, not high; those were finished answers whose
    # harness ran out of clock afterwards. Discarding them moved the task
    # from 0.802 to 0.795 and across the band boundary, which is a good
    # reason to get the rule right rather than to keep the one that
    # flattered the result.
    # Asked before the deliverable, because a provider that served
    # gibberish explains the missing file rather than being explained by
    # it -- and because a garbage run that DID write something would
    # otherwise be averaged in as a real answer.
    if _served_garbage(trial):
        return None, "provider served garbage"
    if not (verifier / f"submitted-{wanted}").is_file():
        # Working files may be present; the answer is not.
        exception = trial / "exception.txt"
        if exception.is_file() and "AgentTimeoutError" in exception.read_text():
            return None, "timeout, nothing written"
        return None, "no deliverable"
    reward = verifier / "reward.json"
    if not reward.is_file():
        return None, "no reward"
    try:
        return float(json.loads(reward.read_text())["reward"]), "ok"
    except ValueError, KeyError, TypeError:
        return None, "unreadable reward"


def measure(tasks_dir: Path, task: str, job: Path) -> dict:
    trials = _trials(job)
    wanted = _deliverable(tasks_dir, task)
    fields = _graded_fields(tasks_dir, task)
    parameters = _brief_parameters(tasks_dir, task)
    oracle = tasks_dir / task / "tests" / "oracle.json"
    scores, reasons = [], []
    for trial in trials:
        value, why = _outcome(trial, wanted, fields, parameters, oracle)
        (scores if value is not None else reasons).append(
            value if value is not None else why
        )
    return {
        "trials": len(trials),
        "scored": len(scores),
        "mean": statistics.fmean(scores) if scores else None,
        "min": min(scores) if scores else None,
        "max": max(scores) if scores else None,
        "excluded": reasons,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        required=True,
        help="dataset name under datasets/; job names are <dataset>-<task>-<tag>",
    )
    # One flag per model, derived from MODELS rather than written out, so
    # adding a tier cannot leave a column with no way to name its tag --
    # which is how kimi-k3's first sweep read as "not run" while three
    # graded trials sat on disk.
    for _model in MODELS:
        parser.add_argument(
            f"--tag-{TAG_PREFIX[_model]}", action="append", default=None
        )
    parser.add_argument(
        "--tiers",
        type=int,
        default=3,
        help=(
            "how many tiers must be measured before a verdict is given "
            "(default 3, matching certify.py). A tier with no sweep is "
            "reported but does not block, so a fourth model nobody has run "
            "yet cannot hold every task at INCOMPLETE"
        ),
    )
    parser.add_argument(
        "--any-tag",
        action="store_true",
        help=(
            "find each model's job by scanning jobs/ instead of naming its "
            "tag. Prints the tag it chose for every cell, because a table "
            "that does not say which sweep it read cannot be checked"
        ),
    )
    args = parser.parse_args(argv)
    tasks_dir = DATASETS / args.dataset / "tasks"
    if not tasks_dir.is_dir():
        parser.error(f"no tasks under {tasks_dir}")
    tags = {
        model: getattr(args, f"tag_{TAG_PREFIX[model]}") or DEFAULT_TAGS[model]
        for model in MODELS
    }

    header = "".join(f"{model:>{_COLUMN}s}" for model in MODELS)
    print(f"{'task':32s}{header} {'mean':>7s}  verdict")
    print("-" * 92)
    in_band = []
    for task in sorted(p.name for p in tasks_dir.iterdir() if p.is_dir()):
        # `_template` is a scaffold, not a task: it has no DELIVERABLE, so
        # reading it raises UnknownDeliverable -- a SystemExit, which took
        # the whole report down and printed a header with no rows under it.
        # A leading underscore is this tree's mark for "not a task".
        if task.startswith("_"):
            continue
        if _retired(tasks_dir / task):
            continue
        cells, means, blocked, rates, picked = [], [], [], [], []
        for model in MODELS:
            # Best evidence wins: the job with the most gradeable trials,
            # and the larger sample breaks a tie.
            wanted_tags = tags[model]
            if args.any_tag:
                # Every job for this task whose tag opens with this model's
                # prefix. Named tags are a maintenance burden that silently
                # reports a measured task as "not run" the moment a sweep
                # lands under a tag nobody added to the list -- which is
                # exactly what this table did for four tasks that had three
                # graded tiers sitting on disk.
                prefix = f"{args.dataset}-{task}-{TAG_PREFIX[model]}"
                wanted_tags = sorted(
                    job.name.split(f"{args.dataset}-{task}-", 1)[1]
                    for job in JOBS.glob(f"{prefix}*")
                    if job.is_dir()
                )
            candidates = [
                (
                    tag,
                    measure(tasks_dir, task, JOBS / f"{args.dataset}-{task}-{tag}"),
                    _mtime(JOBS / f"{args.dataset}-{task}-{tag}"),
                )
                for tag in wanted_tags
            ]
            # Best evidence wins, and RECENCY breaks the tie. It used to be
            # broken by tag name, which is alphabetical and therefore
            # arbitrary: `glm-rev-k3` sorts before `glm-rev2-k3`, so a table
            # comparing two equally-sampled sweeps reported the older one.
            #
            # That matters most where the brief check cannot help. Some
            # harnesses never record the prompt in the trajectory -- every
            # glm trial in this tree is like that -- so a stale sweep of
            # theirs is indistinguishable from a current one by content
            # alone, and only its date separates them.
            chosen, found, _when = max(
                candidates,
                key=lambda c: (c[1]["scored"], c[1]["trials"], c[2]),
            ) if candidates else ("none", measure(tasks_dir, task, JOBS / "missing"), 0.0)
            if args.any_tag and found["mean"] is not None:
                picked.append(f"{TAG_PREFIX[model]}={chosen}")
            if found["mean"] is None:
                cells.append("  --")
                why = found["excluded"][0] if found["excluded"] else "not run"
                blocked.append(f"{model}: {why}")
            else:
                cells.append(f"{found['mean']:.3f}")
                means.append(found["mean"])
                if found["scored"] < _MIN_GRADEABLE:
                    blocked.append(
                        f"{model}: only {found['scored']}/{found['trials']} gradeable"
                    )
                elif found["scored"] < found["trials"]:
                    # Reported, never averaged in: the score stands on the
                    # trials that produced an answer, and the reader is told
                    # how many did.
                    rates.append(
                        f"{model} answered {found['scored']}/{found['trials']}"
                    )
        if args.any_tag and picked:
            rates.append(" ".join(picked))
        if rates and not blocked:
            note = "  (" + "; ".join(rates) + ")"
        else:
            note = ""
        # A tier that was never swept is missing evidence, not evidence of
        # a problem, and it must not hold a measured task at INCOMPLETE --
        # which is what "any blocked model blocks" did once a fourth model
        # joined MODELS and was run on nothing. certify.py has always asked
        # for three tiers; this now asks the same question.
        # Two kinds of "no number here", and they are not the same fact.
        #
        # NO CURRENT MEASUREMENT: never swept, or swept against a brief or a
        # key that has since moved. Nothing is known about this tier on this
        # version of the task, and a task the other tiers measure cleanly
        # should not be held hostage to it.
        #
        # A FAILURE: the tier was swept on this version and something went
        # wrong -- a timeout, no deliverable, a provider serving gibberish.
        # That is a fact about this task as it stands, and it blocks.
        unmeasured = [why for why in blocked if _NO_CURRENT_RUN.search(why)]
        broken = [why for why in blocked if not _NO_CURRENT_RUN.search(why)]
        if unmeasured and not broken and len(means) >= args.tiers:
            note = (note + "  " if note else "  ") + "(" + "; ".join(unmeasured) + ")"
            blocked = []
        if blocked or len(means) < args.tiers:
            short = (
                []
                if len(means) >= args.tiers
                else [f"only {len(means)} tier(s) measured, fewer than {args.tiers}"]
            )
            verdict = "INCOMPLETE — " + "; ".join(blocked + short)
            mean_text = "     --"
        else:
            mean = statistics.fmean(means)
            mean_text = f"{mean:7.3f}"
            if 0.2 <= mean <= 0.8:
                verdict = "IN BAND"
                in_band.append((task, mean))
            else:
                verdict = "out of band"
        # Derived from MODELS, like the header. It used to name
        # `cells[0]`, `cells[1]`, `cells[2]` -- three, when MODELS had
        # grown to four. The fourth model's column was simply not printed,
        # and the columns after it shifted left, so `kimi-k3` read as `--`
        # while `measure` had its mean in hand the whole time. A row that
        # is written out by hand cannot stay in step with a list that
        # grows; the header was derived and the row was not.
        row = "".join(f"{cell:>{_COLUMN}s}" for cell in cells)
        print(f"{task:32s}{row} {mean_text}  {verdict}{note}")

    print(f"\n{len(in_band)} task(s) in 0.2-0.8 on the mean of {args.tiers}+ tiers")
    for task, mean in sorted(in_band, key=lambda kv: kv[1]):
        print(f"    {mean:.3f}  {task}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

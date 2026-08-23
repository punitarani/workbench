"""A dump floor is only a floor if the dump holds something the truth does not.

`baselines.measure` scores answers that involve no comprehension, so a
task's band can be read against what doing nothing already pays. The
strongest of them reports *every candidate* as a row: perfect recall,
terrible precision.

That answer is built as `truth + noise`, where the noise count is
`candidates - len(truth)` and `candidates` comes from the task's own count
of what it read. When a task states no such count, `candidates` fell back
to `len(truth)`, `_noise_rows` was asked for nothing, and the "dump" **was
the oracle** -- so the floor came back at or near 1.000 and read as "a
reader who did no work scores full marks". That is a fact about the
measurement, not about the task.

Measured across ashgrove's fifteen keyed tasks: five state no
count-of-what-was-read at all, and a sixth states one equal to its own row
count. Six of fifteen produced exactly this artifact, two of them a clean
1.000, which is what made it visible. Merrick's tasks all carry a real
count -- the defect was latent in the dataset that owns the file and live
in the one that does not.

The fix reports the floor as *absent, with its reason*, rather than as a
number. A missing floor makes someone look; a fabricated one does not, and
this dataset's argument for measuring floors at all is that a band read
without one is a judgement made on half the evidence.

**These tests do not run Reward Kit.** An earlier version measured all
fifteen ashgrove tasks for real and took 5m51s, which is how a test stops
being run. What changed here is control flow -- *which* answers are scored
and which are refused -- so `_score` is replaced by a stub that records
what it was asked to grade. That is both faster and a sharper instrument:
it can assert the dump was never constructed, where an end-to-end score
can only observe that the number came out high. One real end-to-end
measurement is kept, on one task, so the stub cannot drift from the thing
it stands in for.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from dataset_modules import dataset_module

B = dataset_module("merrick", "baselines")
REPO = Path(__file__).resolve().parents[2]
ASHGROVE = REPO / "datasets" / "ashgrove" / "tasks"
MERRICK = REPO / "datasets" / "merrick" / "tasks"
UNMEASURABLE = "reported_every_candidate_UNMEASURABLE"


@pytest.fixture
def graded(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Every answer `measure` asks to be scored, without scoring any."""

    seen: list[dict] = []

    def record(tests_dir: Path, deliverable: str, answer: dict) -> float:
        seen.append(answer)
        return 0.5

    monkeypatch.setattr(B, "_score", record)
    return seen


def _measure(task: Path) -> dict[str, float]:
    return B.measure(task, json.loads((task / "tests" / "oracle.json").read_text()))


def _rows_of(answer: dict) -> list:
    return next((v for v in answer.values() if isinstance(v, list)), [])


# Five state no count at all; staffing-leverage-review states
# engagements_reviewed=10 against 10 rows, which is non-zero, correctly
# named and equally useless. The guard is `<=`, not "is missing".
NO_CANDIDATE_COUNT = (
    "engagement-closeout-readiness",
    "engagement-time-allocation",
    "self-review-exposure",
    "staffing-leverage-review",
    "tracker-reconciliation",
    "work-product-review",
)


@pytest.mark.parametrize("name", NO_CANDIDATE_COUNT)
def test_no_dump_floor_without_a_candidate_count(name: str, graded: list[dict]) -> None:
    floors = _measure(ASHGROVE / name)
    assert "reported_every_candidate" not in floors
    assert math.isnan(floors[UNMEASURABLE])


@pytest.mark.parametrize("name", NO_CANDIDATE_COUNT)
def test_the_dump_is_never_even_built(name: str, graded: list[dict]) -> None:
    """The sharper form, and the one an end-to-end score cannot make.

    Refusing to *report* a floor while still grading the oracle against
    itself would pass the test above and leave the artifact in place for
    anyone calling `_score` directly. Nothing handed to the grader may
    carry more rows than the answer key has.
    """

    truth = len(
        _rows_of(json.loads((ASHGROVE / name / "tests" / "oracle.json").read_text()))
    )
    _measure(ASHGROVE / name)
    assert graded, "measure must still grade the answers it can"
    assert max(len(_rows_of(a)) for a in graded) <= truth


def test_a_real_candidate_count_still_builds_a_dump(graded: list[dict]) -> None:
    """approval-register: 235 rows against messages_read=1585."""

    floors = _measure(ASHGROVE / "approval-register")
    assert UNMEASURABLE not in floors
    assert max(len(_rows_of(a)) for a in graded) == 1585


def test_reviewed_counts_as_a_count_of_what_was_read(graded: list[dict]) -> None:
    """One dataset spells it `_read`, the other `_reviewed`.

    Matching only `_read` reported no measurable dump floor for
    `client-responsiveness-sla`, which states `threads_reviewed=49` against
    43 rows -- an absence manufactured by this function's vocabulary rather
    than by the task. An absent floor is the honest answer when a task
    cannot support one, and a wrong answer when it can.
    """

    floors = _measure(ASHGROVE / "client-responsiveness-sla")
    assert UNMEASURABLE not in floors, floors
    assert max(len(_rows_of(a)) for a in graded) == 49


def test_the_empty_register_floor_survives_the_guard(graded: list[dict]) -> None:
    """It must not be taken out by the early return added for the dump.

    Every task can support this floor, and it is the one that says an
    answer with no rows at all scores a median 0.405 across ashgrove.
    """

    for name in NO_CANDIDATE_COUNT:
        floors = _measure(ASHGROVE / name)
        assert "empty_register" in floors, name
        assert "no_work_at_all" in floors, name


def test_the_deliverable_is_found_in_either_generation() -> None:
    """Merrick names it in criteria.py; ashgrove in answer/grade.py.

    Reading only the first returned an empty dict for all seventeen
    ashgrove tasks, which reads as "this task has no floors" -- and is why
    a shipped dataset was banded without a single floor measured.
    """

    assert (
        B._deliverable_of(MERRICK / "off-sense-register" / "tests" / "criteria.py")
        == "word_register.json"
    )
    assert (
        B._deliverable_of(ASHGROVE / "approval-register" / "tests" / "criteria.py")
        == "approvals.json"
    )


def test_one_task_measured_for_real() -> None:
    """The stub above is only worth having if it stands for something.

    One end-to-end run, on the task whose dump floor is the highest real
    one found: reporting every candidate on `workpaper-open-items` scores
    0.954 against 55 true rows. No stub -- this actually runs Reward Kit.
    """

    floors = _measure(ASHGROVE / "workpaper-open-items")
    assert UNMEASURABLE not in floors
    assert 0.9 < floors["reported_every_candidate"] < 1.0, floors
    assert 0.0 < floors["empty_register"] < 0.6, floors

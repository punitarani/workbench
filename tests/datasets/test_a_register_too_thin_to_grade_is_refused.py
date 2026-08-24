"""`degenerate` has reported this since it was written, and only reported it.

Its docstring carries the evidence in its own words -- "six of seven tasks
here answered with four to ten rows and every rollout came back 1.000 or
near zero" -- and it reports rather than refuses, deliberately, because
*sparseness can be the finding*: few documents ever reach a client, and a
task about that should be allowed to say so.

That justification is about a **constant column**. It was written for one
of `degenerate`'s two report kinds and inherited by the other, and the
other is not a finding about the world. A four-row register does not tell
you something surprising about the firm; it tells you the grade cannot be
partial. The two reports travel in one list and one of them earned the
exemption.

Downstream, in the dataset that never gated on it: ashgrove ships five
tasks under the threshold, `open-items-triage` at four rows. Both thin ones
whose scores were published came back at or beside 1.000 across every
model -- what the report predicted, printed at build time, and shipped.

Merrick's three built tasks hold 20, 22 and 34 rows, so this blocks nothing
today. It is for the next thin one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dataset_modules import dataset_module

M = dataset_module("merrick", "build_tasks")
A = dataset_module("ashgrove", "build_tasks")
REPO = Path(__file__).resolve().parents[2]


def _rows(n: int) -> list[dict]:
    return [{"ref": f"r{i}", "value": i} for i in range(n)]


def test_a_thin_register_is_refused() -> None:
    with pytest.raises(SystemExit, match="4"):
        M._refuse_a_register_too_thin_to_grade({"found": _rows(4)}, "t")


def test_the_threshold_is_the_one_the_report_uses() -> None:
    M._refuse_a_register_too_thin_to_grade({"found": _rows(M.THIN_ROWS)}, "t")
    with pytest.raises(SystemExit):
        M._refuse_a_register_too_thin_to_grade({"found": _rows(M.THIN_ROWS - 1)}, "t")


def test_a_set_of_scalars_is_not_a_thin_register() -> None:
    """Grading four engagement numbers as a set is a criterion, not a defect.

    The first version of this gate counted every short list and refused
    four more ashgrove tasks than the report it is supposed to be the teeth
    of -- the gate inventing its own rule rather than enforcing one.
    """

    M._refuse_a_register_too_thin_to_grade(
        {"at_risk": ["00001-Fairmount", "00002-Halden"], "rows": _rows(20)}, "t"
    )


def test_every_short_list_of_rows_is_counted_not_only_a_lone_one() -> None:
    """The other half of the same mistake, in the other direction.

    The first version returned early unless the oracle held exactly one
    list, which let a thin register through whenever a task also reported a
    set -- four of ashgrove's five thin tasks are exactly that shape.
    """

    with pytest.raises(SystemExit, match="engagements holds 10"):
        M._refuse_a_register_too_thin_to_grade(
            {"engagements": _rows(10), "at_risk": ["a", "b"]}, "t"
        )


def _oracles(dataset: str) -> list[tuple[str, dict]]:
    return [
        (task.name, json.loads((task / "tests" / "oracle.json").read_text()))
        for task in sorted((REPO / "datasets" / dataset / "tasks").iterdir())
        if (task / "tests" / "oracle.json").is_file()
    ]


@pytest.mark.parametrize("dataset", ["merrick", "ashgrove"])
def test_the_gate_refuses_exactly_what_the_report_flags(dataset: str) -> None:
    """The two must not drift.

    A gate that refuses more than its report is a new rule nobody agreed
    to; one that refuses less is a report with no teeth. Checked over every
    committed oracle in both datasets rather than on a fixture, because the
    disagreement showed up only on real shapes.
    """

    flagged, refused = [], []
    for name, answer in _oracles(dataset):
        if any("too thin" in report for report in A.degenerate(answer)):
            flagged.append(name)
        try:
            M._refuse_a_register_too_thin_to_grade(answer, name)
        except SystemExit:
            refused.append(name)
    assert flagged == refused, f"{dataset}: report {flagged}, gate {refused}"


def test_this_dataset_s_own_tasks_pass() -> None:
    for name, answer in _oracles("merrick"):
        M._refuse_a_register_too_thin_to_grade(answer, name)

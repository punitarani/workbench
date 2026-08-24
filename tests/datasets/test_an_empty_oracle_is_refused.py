"""The gate that every other gate needs, and the only one without a test.

`_refuse_empty_answer` exists because an oracle with no rows *passes
everything else*. Its own docstring lists why: reachability finds no
unserved identifier because there are no identifiers; the second derivation
agrees, because nothing equals nothing; degeneracy reports no constant
column because there are no columns. Every check is satisfied, and the task
then grades an empty register — where a model that writes `[]` scores 1.0
and a model that finds anything at all scores less.

It was the one refusal in `build_tasks` that no test named. That is not
harmless: a gate whose failing branch is never exercised is one edit away
from being inert, and this one guards the case where *all the other gates
are green*. Three tasks were retired for producing 0–3 rows and each was
caught by measuring on purpose, not by the build refusing.

The second branch matters as much as the first. `len(rows) != 1` refuses an
oracle carrying two lists, because the gate cannot tell which one to count
— and ashgrove ships six tasks of exactly that shape (a register plus a
set-membership figure), so it is not hypothetical, it is the neighbouring
dataset's normal.
"""

from __future__ import annotations

import pytest
from dataset_modules import dataset_module

M = dataset_module("merrick", "build_tasks")


def test_an_oracle_with_no_rows_is_refused() -> None:
    with pytest.raises(SystemExit, match="no rows"):
        M._refuse_empty_answer({"found": [], "count": 0}, "t")


def test_the_refusal_says_what_makes_this_one_dangerous() -> None:
    """The message has to carry the reason, because the build log is green.

    Everything else passed. A reader who sees only "refused" will widen a
    window and try again; a reader who is told that every other gate passes
    on an empty answer knows the rule itself may be the problem.
    """

    with pytest.raises(SystemExit) as raised:
        M._refuse_empty_answer({"found": []}, "t")
    message = str(raised.value)
    assert "Every other gate passes" in message
    assert "retire the rule" in message


def test_two_lists_are_refused_because_the_count_is_ambiguous() -> None:
    with pytest.raises(SystemExit, match="exactly one list"):
        M._refuse_empty_answer({"rows": [{"a": 1}], "others": [{"b": 2}]}, "t")


def test_no_list_at_all_is_refused() -> None:
    with pytest.raises(SystemExit, match="exactly one list"):
        M._refuse_empty_answer({"count": 3}, "t")


def test_a_populated_oracle_passes() -> None:
    M._refuse_empty_answer({"found": [{"ref": "a"}], "count": 1}, "t")


def test_a_single_row_passes_this_gate() -> None:
    """Emptiness only. Thinness is `_refuse_a_register_too_thin_to_grade`.

    Two gates, two thresholds, and this one must not quietly take on the
    other's job: if it refused at some size of its own they would drift,
    which is the failure the window screen and the build already have a
    test pinning them against.
    """

    M._refuse_empty_answer({"found": [{"ref": "a"}]}, "t")
    with pytest.raises(SystemExit):
        M._refuse_a_register_too_thin_to_grade({"found": [{"ref": "a"}]}, "t")

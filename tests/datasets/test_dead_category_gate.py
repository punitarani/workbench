"""A brief may not enumerate a category the world never fills.

Every dict-valued figure in these oracles is a table the brief prints:
`form_counts` has one key per row of the admitted-forms table. A key whose
count is zero means the brief spent a table row, and a paragraph of the
reader's attention, on a rule the corpus never exercises — and the key
becomes a constant an agent scores by writing 0 without looking.

Measured in this tree: `deadline-week-promise-clock` prints a form table
whose `end of month` row matches zero of 2,717 mail messages, counting
`end of month`, `end of the month` and `EOM` together. A sibling firm's
brief warned about `end of the week`, which occurred fifteen times there
and not once here while the bare form occurred 172 times.

The gate is a refusal, unlike `degenerate()`, which reports constant row
columns and does not fail. The asymmetry is the point: a sparse row column
can be the finding, but a dead table row is the brief asserting a category
exists when it does not.
"""

import pytest
from dataset_modules import merrick_build_tasks


def _write_criteria(task, allowed=None) -> None:
    (task / "tests").mkdir(parents=True, exist_ok=True)
    body = 'DELIVERABLE = "out.json"\nROWS = "hits"\nKEY = ("ref",)\n'
    if allowed is not None:
        body += f"ALLOWED_EMPTY_KEYS = {allowed!r}\n"
    (task / "tests" / "criteria.py").write_text(body)


def _gate():
    return merrick_build_tasks()._refuse_dead_categories


LIVE = {"hits": [{"ref": "a"}], "form_counts": {"agree": 11, "agreed": 4}}
DEAD = {"hits": [{"ref": "a"}], "form_counts": {"by weekday": 9, "end of month": 0}}


def test_a_dead_table_row_stops_the_build(tmp_path) -> None:
    _write_criteria(tmp_path)
    with pytest.raises(SystemExit, match="end of month"):
        _gate()(tmp_path, DEAD, "deadline-week")


def test_a_table_every_row_of_which_fires_is_fine(tmp_path) -> None:
    _write_criteria(tmp_path)
    _gate()(tmp_path, LIVE, "off-sense")


def test_a_declared_empty_key_is_allowed(tmp_path) -> None:
    """Grading whether an agent reports an empty category is legitimate.

    It just has to be said out loud, by name, with the reason next to it -
    which is the difference between a decision and an oversight.
    """

    _write_criteria(tmp_path, allowed=("form_counts.end of month",))
    _gate()(tmp_path, DEAD, "deadline-week")


def test_declaring_a_different_key_does_not_cover_this_one(tmp_path) -> None:
    _write_criteria(tmp_path, allowed=("form_counts.by weekday",))
    with pytest.raises(SystemExit, match="end of month"):
        _gate()(tmp_path, DEAD, "deadline-week")


def test_every_dead_key_is_named_not_just_the_first(tmp_path) -> None:
    _write_criteria(tmp_path)
    answer = {
        "hits": [{"ref": "a"}],
        "form_counts": {"live": 3, "dead one": 0, "dead two": 0},
        "department_counts": {"dead three": 0},
    }
    with pytest.raises(SystemExit) as caught:
        _gate()(tmp_path, answer, "t")
    message = str(caught.value)
    for key in ("dead one", "dead two", "dead three"):
        assert key in message, f"{key!r} missing from {message!r}"


def test_a_stale_allowance_is_reported(tmp_path, capsys) -> None:
    """An allowance that allows nothing is a comment about a fixed defect.

    Left in place it tells the next reader the row is still dead, and they
    believe it.
    """

    _write_criteria(tmp_path, allowed=("form_counts.agreed",))
    _gate()(tmp_path, LIVE, "off-sense")
    assert "Drop the allowance" in capsys.readouterr().out


def test_row_lists_are_not_mistaken_for_categories(tmp_path) -> None:
    """Only dicts are tables. A row whose field is 0 is data, not a dead rule."""

    _write_criteria(tmp_path)
    _gate()(tmp_path, {"hits": [{"ref": "a", "count": 0}], "total": 0}, "t")

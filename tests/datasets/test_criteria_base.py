"""The shared grader, tested on the mistakes its predecessors made.

Every rule in `criteria_base` exists because its absence cost a
measurement, so each is pinned here by the failure rather than by the
happy path. Twenty-eight near-identical copies of this logic exist in the
older datasets; a fix applied to one has never reached the others, which
is the whole reason this is one file.

The oracle is loaded at import, so these tests build a task directory on
disk and import the module against it.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "datasets" / "merrick" / "criteria_base.py"


def _load(tmp_path: Path, oracle: dict):
    """Import the shared grader with a given oracle beside it.

    Under the shared rewardkit stand-in, in its calling mode: the real
    decorator returns the function unchanged, so what these tests invoke
    is exactly what the verifier invokes.
    """

    sys.path.insert(0, str(REPO / "tests"))
    import rewardkit_stub

    sys.modules["rewardkit"] = rewardkit_stub.calling()
    (tmp_path / "oracle.json").write_text(json.dumps(oracle))
    (tmp_path / "criteria_base.py").write_text(SOURCE.read_text())
    spec = importlib.util.spec_from_file_location(
        f"cb_{tmp_path.name}", tmp_path / "criteria_base.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(workspace: Path, payload: dict) -> None:
    (workspace / "answer.json").write_text(json.dumps(payload))


ORACLE = {"total": 2, "rows": [{"ref": "a", "ok": True}, {"ref": "b", "ok": False}]}


def test_a_boolean_field_can_score(tmp_path: Path) -> None:
    """`bool` subclasses `int`, so a tolerance comparison rejects `True`
    outright and every boolean field scores zero — including correct
    ones. A reference answer graded 0.571 against its own criteria."""

    cb = _load(tmp_path, ORACLE)
    _write(tmp_path, {"total": 2, "rows": ORACLE["rows"]})
    score = cb.row_fields(
        tmp_path, "answer.json", "rows", ["ref"], ORACLE["rows"], {"ok": 0.0}
    )
    assert score == 1.0


def test_under_reporting_is_not_free(tmp_path: Path) -> None:
    """Iterating the submission and skipping unmatched rows would score
    one perfect row out of two as 1.000."""

    cb = _load(tmp_path, ORACLE)
    _write(tmp_path, {"total": 2, "rows": [{"ref": "a", "ok": True}]})
    score = cb.row_fields(
        tmp_path, "answer.json", "rows", ["ref"], ORACLE["rows"], {"ok": 0.0}
    )
    assert score == pytest.approx(0.5)


def test_invented_rows_cost_but_do_not_wipe_out_correct_work(tmp_path: Path) -> None:
    """A cliff to zero tells the reader nothing about what the agent knew."""

    cb = _load(tmp_path, ORACLE)
    invented = [{"ref": f"x{n}", "ok": True} for n in range(40)]
    _write(tmp_path, {"total": 2, "rows": ORACLE["rows"] + invented})
    score = cb.row_fields(
        tmp_path, "answer.json", "rows", ["ref"], ORACLE["rows"], {"ok": 0.0}
    )
    assert 0.0 < score < 1.0


def test_nothing_expected_and_nothing_given_is_correct(tmp_path: Path) -> None:
    """A task whose world held no findings used to fail its own reference
    answer."""

    cb = _load(tmp_path, {"total": 0, "rows": []})
    _write(tmp_path, {"total": 0, "rows": []})
    assert (
        cb.row_fields(tmp_path, "answer.json", "rows", ["ref"], [], {"ok": 0.0}) == 1.0
    )
    assert cb.row_f1(tmp_path, "answer.json", "rows", ["ref"], []) == 1.0


def test_a_multi_part_key_does_not_collapse_rows(tmp_path: Path) -> None:
    """A key that distinguishes fewer rows than exist caps the achievable
    score below 1.0 for reasons no agent can fix."""

    oracle = {
        "rows": [
            {"ref": "a", "due": "2026-01-05", "ok": True},
            {"ref": "a", "due": "2026-01-09", "ok": False},
        ]
    }
    cb = _load(tmp_path, oracle)
    _write(tmp_path, {"rows": oracle["rows"]})
    spec = {"ok": 0.0}
    good = ["ref", "due"]
    assert cb.row_f1(tmp_path, "answer.json", "rows", good, oracle["rows"]) == 1.0
    assert (
        cb.row_fields(tmp_path, "answer.json", "rows", good, oracle["rows"], spec)
        == 1.0
    )

    # Keyed on `ref` alone the two rows collide — and F1 is *not* where
    # that shows, because both sides dedupe identically and it still reads
    # 1.0. That is exactly why the defect is easy to miss. It bites in the
    # per-row check, where both oracle rows are looked up against the one
    # surviving submission and one of them cannot match: the ceiling drops
    # below 1.0 for a reason no agent can fix.
    assert cb.row_f1(tmp_path, "answer.json", "rows", ["ref"], oracle["rows"]) == 1.0
    assert (
        cb.row_fields(tmp_path, "answer.json", "rows", ["ref"], oracle["rows"], spec)
        < 1.0
    )


def test_the_schema_check_reads_the_oracle_not_a_copy(tmp_path: Path) -> None:
    """A hand-kept field list fails every correct answer the day the
    report changes shape."""

    cb = _load(tmp_path, ORACLE)
    assert cb.TOP == frozenset({"total", "rows"})
    _write(tmp_path, {"total": 2, "rows": []})
    assert cb.schema_ok(tmp_path, "answer.json") is True
    _write(tmp_path, {"total": 2})
    assert cb.schema_ok(tmp_path, "answer.json") is False


def test_a_missing_or_unparsable_deliverable_scores_zero(tmp_path: Path) -> None:
    cb = _load(tmp_path, ORACLE)
    assert cb.submitted(tmp_path, "answer.json") is None
    (tmp_path / "answer.json").write_text("not json at all")
    assert cb.submitted(tmp_path, "answer.json") is None

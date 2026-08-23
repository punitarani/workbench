"""`_STRUCTURAL_BANDS` is two names long, and nothing reviews it.

The gate that refuses a world for having none of something reads a
hand-kept tuple. That scope is deliberate and defensible -- most of the
bands here were written for an accounting firm, so *which* apply to a law
firm is a judgement a function should not make. What was missing is any
prompt to review the list against what the world actually reads: a new
absence lands among 36 failing bands and is never seen again.

On the v6 world, nine surfaces **exist and read effectively nothing** while
not being declared -- including `calendar.cancellation_share` at 0.000, not
one meeting cancelled in sixty-eight days, and `email.machine_share` at
0.000, a firm with no automated mail at all. Both are FAIL, and the gate
reads only its own two names, so neither had ever been surfaced.

The filter that makes the report readable is the one distinction that
matters: a metric scored ABSENT has no surface to measure -- a band written
for a different firm -- while a FAIL at effectively zero is a surface this
world has and never uses. Without it the report is 30 lines of mostly tax
and billing bands; with it, 9.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dataset_modules import dataset_module

M = dataset_module("merrick", "build_tasks")


class _Band:
    def __init__(self, minimum, maximum=None):
        self.min, self.max = minimum, maximum

    def rendered(self):
        return f"{self.min}-{self.max}"


class _Result:
    def __init__(self, metric, verdict, observed, minimum):
        self.metric, self.verdict, self.observed = metric, verdict, observed
        self.band = _Band(minimum)


def test_a_surface_that_exists_and_reads_zero_is_reported(
    capsys: pytest.CaptureFixture,
) -> None:
    M._report_undeclared_absences([_Result("calendar.cancel", "FAIL", 0.0, 0.03)])
    out = capsys.readouterr().out
    assert "calendar.cancel" in out
    assert "_STRUCTURAL_BANDS" in out, "the report must say what to review"


def test_a_missing_surface_is_not_reported(capsys: pytest.CaptureFixture) -> None:
    """ABSENT is a band for another firm, not a hole in this one.

    This is the whole filter. Without it the report carries every tax and
    billing band merrick has no surface for, and a report that is mostly
    noise is not read.
    """

    M._report_undeclared_absences([_Result("tax.efile_ack_share", "ABSENT", None, 0.5)])
    assert capsys.readouterr().out == ""


def test_a_near_miss_is_not_an_absence(capsys: pytest.CaptureFixture) -> None:
    """A tenth of the floor, the same line the real gate draws.

    0.25 against a floor of 0.30 is a realism note; 0.0003 is a missing
    feature. Reporting the first as an absence would bury the second.
    """

    M._report_undeclared_absences([_Result("slack.busy", "FAIL", 0.25, 0.30)])
    assert capsys.readouterr().out == ""
    M._report_undeclared_absences([_Result("slack.busy", "FAIL", 0.0003, 0.30)])
    assert "slack.busy" in capsys.readouterr().out


def test_a_declared_band_is_left_to_the_gate(capsys: pytest.CaptureFixture) -> None:
    """It refuses on those; reporting them here would double the noise."""

    declared = M._STRUCTURAL_BANDS[0]
    M._report_undeclared_absences([_Result(declared, "FAIL", 0.0, 0.15)])
    assert capsys.readouterr().out == ""


def test_a_passing_band_says_nothing(capsys: pytest.CaptureFixture) -> None:
    M._report_undeclared_absences([_Result("email.cc_share", "PASS", 0.30, 0.1)])
    assert capsys.readouterr().out == ""


def test_a_band_with_no_floor_cannot_be_an_absence(
    capsys: pytest.CaptureFixture,
) -> None:
    """`min` of 0 or None means nothing is below it.

    Dividing by ten and comparing would report every such band forever,
    which is how a report earns being ignored.
    """

    M._report_undeclared_absences([_Result("x.share", "FAIL", 0.0, 0)])
    M._report_undeclared_absences([_Result("y.share", "FAIL", 0.0, None)])
    assert capsys.readouterr().out == ""


def test_the_real_world_names_the_two_that_prompted_this() -> None:
    """Not a fixture: the world on disk, if it is there.

    The nine come from a real recording, and two of them are findings in
    their own right. A test that only ever sees hand-built results would
    have passed while the filter did nothing to the shape it was written
    for.
    """

    source = Path("out/merrick/bundle/SOURCE")
    if not source.is_file():
        pytest.skip("no bundle on disk")
    import sys

    sys.path.insert(0, "src")
    from analysis.fidelity import evaluate, load_bands
    from analysis.fidelity import measure as measure_bands

    state = Path("out/merrick/bundle/state")
    world = Path(source.read_text().strip())
    if not world.is_file():
        pytest.skip("bundle names a world log that is gone")
    results = evaluate(measure_bands(state, world), load_bands())
    named = {
        r.metric
        for r in results
        if r.metric not in M._STRUCTURAL_BANDS
        and r.verdict == "FAIL"
        and r.band.min
        and r.observed is not None
        and r.observed < r.band.min / 10
    }
    assert "calendar.cancellation_share" in named
    assert "email.machine_share" in named


def test_absent_and_unmeasured_are_the_same_thing_here() -> None:
    """Why two of this filter's conditions are redundant, on purpose.

    `verdict == "FAIL"` and `observed is not None` exclude exactly the same
    bands, so mutating either one away changes nothing — they are
    equivalent mutants rather than gaps in the tests above, and it is
    better to say so than to write a fixture that manufactures a
    combination the system never produces.

    Over all 91 real bands: ABSENT always carries `observed is None`, and
    FAIL and PASS always carry a number. Both conditions are kept — the
    verdict is the semantic one, the None check keeps a future FAIL with no
    observation from raising TypeError inside a build — and this test is
    what will notice if the equivalence ever stops holding.
    """

    source = Path("out/merrick/bundle/SOURCE")
    if not source.is_file():
        pytest.skip("no bundle on disk")
    import sys

    sys.path.insert(0, "src")
    from analysis.fidelity import evaluate, load_bands
    from analysis.fidelity import measure as measure_bands

    world = Path(source.read_text().strip())
    if not world.is_file():
        pytest.skip("bundle names a world log that is gone")
    results = evaluate(
        measure_bands(Path("out/merrick/bundle/state"), world), load_bands()
    )
    assert results, "no bands measured"
    for result in results:
        assert (result.verdict == "ABSENT") == (result.observed is None), result.metric

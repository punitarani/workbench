"""The gate that refuses a world missing something a firm certainly has.

It filtered on the FAIL verdict. A metric whose surface is missing, or
present and holding no rows, measures None and is scored **ABSENT** —
never FAIL — so the filter skipped the strongest form of the absence the
gate exists to catch. A world with no chat surface at all passed it; a
world with a chat surface reading 0.0 did not.

That is the gate being wrong about its own subject, and it is the third
guard in this tree found unable to fire in the case it was written for.

The other assertion here is the tenth-of-the-floor line. The first
version refused only an exact zero, and the world it was written for
measured `threaded_reply_share` at 0.000315 — three replies in 3,177
messages, each a fluke of a path that could not fire deliberately. It was
caught only because a second metric happened to land on 0.0 exactly.
"""

import pytest

from analysis.fidelity import Band, Result


def _gate():
    """The build's own decision function, not a copy of it.

    The first version of this file restated the loop — which is the exact
    defect this tree spent the day finding, and it would have agreed with
    a broken gate forever.
    """

    import sys
    from pathlib import Path

    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "datasets" / "merrick")
    )
    import build_tasks

    return build_tasks._structural_absences


BAND = Band(label="DM share", surface="chat", min=0.15, max=0.35)
METRIC = "slack.dm_share"


@pytest.mark.parametrize(
    ("observed", "refused", "why"),
    [
        (None, True, "surface missing entirely — the case the gate exists for"),
        (0.0, True, "surface present, capability absent"),
        (0.000315, True, "three flukes in 3,177 is absence, not shyness"),
        (0.10, False, "below band but real — a realism note, not a refusal"),
        (0.25, False, "in band"),
        (0.50, False, "above band — reported on shape, never refused"),
    ],
)
def test_the_gate_refuses_absence_and_reports_shape(observed, refused, why) -> None:
    result = Result(METRIC, BAND, observed, BAND.verdict(observed))
    assert bool(_gate()([result], report=False)) is refused, why


def test_a_band_outside_the_structural_set_is_never_refused() -> None:
    """Most of the committed bands describe a different firm entirely.
    Refusing on all of them could never pass."""

    other = Result("book.clients", BAND, None, "ABSENT")
    assert _gate()([other], report=False) == []


def test_absent_is_what_an_empty_surface_actually_produces() -> None:
    """Guard the premise: if `verdict` ever returned FAIL for None, the
    fix above would be solving a problem that no longer exists and the
    real one would be somewhere else."""

    assert BAND.verdict(None) == "ABSENT"

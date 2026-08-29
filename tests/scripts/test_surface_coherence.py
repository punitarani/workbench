"""A world can pass every surface's own realism gate and still be four firms.

Every other gate in this tree asks whether a surface looks right ON ITS
OWN. None of them asks whether the surfaces agree about who is busy, and a
generator that writes each surface independently passes all of them.

Two distinct defects live here and they need separate verdicts:

**A FLAT surface** has no ordering at all. merrick's billing logs 976-1083
entries for every one of 21 people -- a Gini of 0.011. There is no busiest
person to disagree about, and the first version of this script duly
reported five "inverted" pairs against it, which were the sign of a coin
flip printed to three decimal places. Flat is the worse defect: no task
keyed on who is busiest can be built on such a surface at all.

**An INVERTED pair** is the real finding: the actors busiest in one surface
are the least busy in another. No institution does that.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "coherence", REPO / "scripts" / "coherence.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["coherence"] = module
    spec.loader.exec_module(module)
    return module


def test_a_flat_surface_has_a_gini_near_zero():
    c = _load()
    flat = {f"p{i}": 1000 + i for i in range(21)}
    assert c.gini(flat) < 0.10, c.gini(flat)


def test_a_real_workload_spread_is_not_flat():
    c = _load()
    spread = {f"p{i}": 10 * (i + 1) ** 2 for i in range(21)}
    assert c.gini(spread) > 0.10


def test_identical_orderings_correlate_at_one():
    c = _load()
    a = {f"p{i}": 100 - i for i in range(10)}
    b = {f"p{i}": (100 - i) * 3 for i in range(10)}
    rho, n = c.spearman(a, b)
    assert rho > 0.99 and n == 10


def test_a_reversed_ordering_is_negative():
    """The finding the script exists for."""

    c = _load()
    a = {f"p{i}": 100 - i for i in range(10)}
    b = {f"p{i}": i for i in range(10)}
    rho, _ = c.spearman(a, b)
    assert rho < -0.99, rho


def test_an_actor_present_in_one_surface_and_absent_in_the_other_counts():
    """The union, not the intersection.

    Somebody who bills heavily and sends no mail at all is the strongest
    evidence of incoherence available, and intersecting drops exactly that
    person from the comparison.
    """

    c = _load()
    heavy = {"a": 100, "b": 90, "c": 80, "d": 70}
    elsewhere = {"d": 100, "c": 90, "b": 80}
    _, n = c.spearman(heavy, elsewhere)
    assert n == 4, "the actor missing from one surface was dropped"


def test_ties_share_a_rank_rather_than_falling_alphabetically():
    """Without this, a surface where most actors are absent -- all zero, all
    tied -- reports a correlation driven by name order."""

    c = _load()
    tied = {"a": 5, "b": 5, "c": 5, "d": 5}
    ordered = {"a": 4, "b": 3, "c": 2, "d": 1}
    rho, _ = c.spearman(tied, ordered)
    assert abs(rho) < 1e-9, f"tied surface produced a correlation: {rho}"

"""The family screen, tested on the shapes that misled a build.

Choosing the word a literalism register is built on decides whether the
task lands in band or at ceiling, and the intuition the shape invites is
wrong. Two families that read perfectly on paper were dead on the corpus
— one second spelling appeared in a single message out of 1,585, another
in none at all — and a third looked ideal on excluded-inflection density,
which is the decoy metric.

The number that predicts is the off-sense share of the *admitted* form,
and it cannot be counted mechanically. So the screen refuses to pass a
family whose sample nobody has read: treating "unmeasured" as "fine" is
exactly how the decoy won.
"""

from analysis.form_families import (
    MIN_OFF_SENSE_SHARE,
    Family,
    measure_family,
    screen,
)

_COMPLETE = Family(
    "complete", ("complete", "completed"), ("completion", "completes", "completing")
)


def _corpus(*bodies: str) -> list[str]:
    return list(bodies)


def test_word_boundary_is_letters_not_python_b() -> None:
    """`completed` must not count as `complete`, and a hyphen is a break."""

    report = measure_family(
        _corpus(
            "the work is complete",  # form A
            "she completed it",  # form B
            "completion is near",  # excluded only
            "a cost-to-complete figure",  # hyphen is a break: counts
            "incomplete and uncompleted",  # letters before: neither counts
        ),
        _COMPLETE,
        sample=0,
    )
    assert dict(report.per_form) == {"complete": 2, "completed": 1}
    assert report.messages == 3
    assert report.exclusion_only_messages == 1


def test_a_dead_second_form_is_reported_as_dead() -> None:
    """A rule whose second form never fires is a one-form rule with extra
    words. `finalised` occurs in none of 1,585 real messages."""

    report = measure_family(
        _corpus("the final order", "the final schedule", "final numbers"),
        Family("final", ("final", "finalised")),
        sample=0,
    )
    assert not report.alive
    assert any("on its own" in problem for problem in screen(report, windowed=True))


def test_a_lopsided_family_is_rejected() -> None:
    """`file` appears in 106 messages and `filed` in one. The task would
    grade a single spelling."""

    bodies = ["please file the response"] * 40 + ["it was filed yesterday"]
    report = measure_family(bodies, Family("file", ("file", "filed")), sample=0)
    assert report.alive  # both fire, so liveness alone does not catch it
    assert report.minority_share < 0.05
    assert any("minority form" in problem for problem in screen(report, windowed=True))


def test_unmeasured_off_sense_cannot_pass() -> None:
    """The guard against the decoy metric. A family that is alive, has
    plenty of rows and a balanced split still fails until somebody has
    read the sample."""

    bodies = ["work is complete"] * 30 + ["she completed it"] * 30
    report = measure_family(bodies, _COMPLETE, sample=0)
    assert report.alive and report.minority_share == 0.5 and report.messages >= 20
    problems = screen(report, windowed=True)
    assert len(problems) == 1 and "off-sense share not measured" in problems[0]
    assert (
        screen(report, windowed=True, off_sense_share=MIN_OFF_SENSE_SHARE + 0.05) == ()
    )


def test_low_off_sense_is_rejected_with_the_reason() -> None:
    bodies = ["work is complete"] * 30 + ["she completed it"] * 30
    report = measure_family(bodies, _COMPLETE, sample=0)
    problems = screen(report, windowed=True, off_sense_share=0.10)
    assert len(problems) == 1
    assert "at ceiling" in problems[0]


def test_samples_are_seeded_and_carry_context() -> None:
    """The decision rests on a hand-read sample, so the sample a decision
    was made on has to be reproducible."""

    bodies = [f"that gives you the complete picture, item {n}" for n in range(50)]
    first = measure_family(bodies, _COMPLETE, sample=5)
    second = measure_family(bodies, _COMPLETE, sample=5)
    assert first.samples == second.samples
    assert len(first.samples) == 5
    assert all("complete" in window for window in first.samples)


def test_occurrences_counts_repeats_but_messages_does_not() -> None:
    """One row per message, however many times the form appears — but the
    sample for classification is drawn over occurrences."""

    report = measure_family(
        _corpus("complete, complete, and complete again"), _COMPLETE, sample=0
    )
    assert report.messages == 1
    assert report.occurrences == 3


def test_a_second_form_that_never_appears_alone_is_dead() -> None:
    """The metric that matters is not how often a spelling occurs but how
    often it matches a message *by itself*.

    A family whose rarer form appears ten times, always beside the
    commoner one, contributes no row the first form would not already
    have matched — yet the naive share reads 0.33 and clears a 0.20 floor.
    """

    both_then_alpha = ["alpha and beta"] * 10 + ["alpha only"] * 10
    report = measure_family(both_then_alpha, Family("t", ("alpha", "beta")), sample=0)
    assert dict(report.per_form) == {"alpha": 20, "beta": 10}
    assert dict(report.exclusive_per_form) == {"alpha": 10, "beta": 0}
    assert not report.alive
    assert report.minority_share == 0.0
    assert any("on its own" in problem for problem in screen(report, windowed=True))


def test_an_unwindowed_report_cannot_pass() -> None:
    """The floors are calibrated in the rows a task grades. Handing the
    whole corpus to the same threshold passed the calibration family at
    110 rows against a floor derived from its 25-row window."""

    bodies = ["work is complete"] * 30 + ["she completed it"] * 30
    report = measure_family(bodies, _COMPLETE, sample=0)
    problems = screen(report, off_sense_share=0.79)
    assert any("unwindowed" in problem for problem in problems)
    assert screen(report, windowed=True, off_sense_share=0.79) == ()


def test_a_percentage_where_a_fraction_belongs_is_a_hard_error() -> None:
    """79 meaning 79% silently clears a 0.60 floor, and so does every
    other family, forever."""

    import pytest as _pytest

    bodies = ["work is complete"] * 30 + ["she completed it"] * 30
    report = measure_family(bodies, _COMPLETE, sample=0)
    for bad in (79, -0.1, 1.5, float("nan")):
        with _pytest.raises(ValueError):
            screen(report, windowed=True, off_sense_share=bad)


def test_samples_carry_the_word_and_its_surroundings() -> None:
    """The sample exists to be read for sense, so it has to contain enough
    sentence to judge. A zero-context window is a list of the same word."""

    bodies = ["Once the reconciliation is complete we will circulate the schedule."] * 5
    report = measure_family(bodies, _COMPLETE, sample=3, context=40)
    assert report.samples
    for window in report.samples:
        assert "complete" in window
        assert len(window) > len("complete") + 20, window

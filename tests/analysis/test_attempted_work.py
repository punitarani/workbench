"""A world can be structurally incomplete and look perfectly well behaved.

The referee resolves every reference against world state and rejects what
it cannot resolve. That is what makes a replay deterministic, and every
individual rejection here was correct. But when the actors reach for
something the world does not offer, the record simply ends up with less
in it than the day had — and nothing else in the pipeline notices.

Measured on a law firm's first three recorded days: personas logging
admin, internal-meeting and practice-group time had no matter code for
it, invented plausible ones, and 84 of 500 attempted entries — 16.8% —
were dropped. A utilisation figure over the survivors is perfectly
self-consistent and describes a firm that does not exist.
"""

from analysis.attempted_work import MAX_DROPPED_SHARE, measure, violations

# The referee's real note text, verbatim.
_NOTE = (
    "dropped 2 timesheet entries against unknown engagements "
    "['internal-000001', 'admin-000001']"
)


def test_the_measured_known_bad_fails() -> None:
    work = measure([_NOTE] * 42, logged=416)
    assert work.dropped == 84
    assert work.attempted == 500
    assert 0.16 < work.dropped_share < 0.17
    problems = violations(work)
    assert len(problems) == 1
    assert "16.8%" in problems[0]
    # The message has to say the referee was right, or the next reader
    # "fixes" it by making the referee permissive.
    assert "right to reject" in problems[0]
    assert "internal-000001" in problems[0]


def test_a_healthy_world_passes() -> None:
    """A ceiling that fails everything is a wall, not a calibration."""

    assert violations(measure([_NOTE], logged=400)) == ()


def test_a_little_drift_is_tolerated() -> None:
    """Somebody mistyping a matter is real and is not a build failure."""

    work = measure([_NOTE] * 5, logged=400)
    assert work.dropped_share < MAX_DROPPED_SHARE
    assert violations(work) == ()


def test_an_empty_world_is_a_violation_not_a_pass() -> None:
    """Every ratio is vacuously fine at zero. Without this, a world that
    recorded no time at all sails through."""

    assert violations(measure([], logged=0)) == (
        "no time was recorded or attempted at all",
    )


def test_unrelated_notes_are_ignored() -> None:
    """The referee writes many kinds of note; only one shape counts."""

    work = measure(
        [
            "Rejected action from x: an email needs at least one recipient",
            "Rejected action from y: doc-000001 declares spreadsheet but ...",
            _NOTE,
        ],
        logged=100,
    )
    assert work.dropped == 2


def test_invented_refs_are_ranked_by_frequency() -> None:
    """The list is the fix list: the codes the world should have offered."""

    work = measure(
        [_NOTE, _NOTE, "dropped 1 timesheet entries against unknown engagements ['x']"],
        logged=10,
    )
    assert work.invented_refs[0][0] in {"admin-000001", "internal-000001"}
    assert work.invented_refs[0][1] == 2
    assert ("x", 1) in work.invented_refs

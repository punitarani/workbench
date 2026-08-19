"""A world can be structurally incomplete and look perfectly well behaved.

The referee resolves every reference against world state and rejects what
it cannot resolve. That is what makes a replay deterministic, and every
individual rejection is correct. But when the actors reach for something
the world does not offer, the record simply ends up with less in it than
the day had — and nothing else in the pipeline notices. Coherence checks
look for a fact carrying two values; they cannot see a fact that was
never recorded.

This test file is built by **driving the real referee**, not by
transcribing its sentences. The first version hand-copied the note text,
and an audit showed all three ways that fails:

* rewording the referee's f-string zeroed the rate with the suite green;
* the two sides disagreed about whether the number meant entries lost or
  distinct references invented — a fourfold difference that flipped a
  failing world to passing;
* and the worst case was silent by construction. A timesheet whose
  entries were *all* invalid took a branch that raised without writing a
  matching sentence at all, so a world that lost everything measured
  0.0% and passed.
"""

import pytest

from analysis.attempted_work import MAX_DROPPED_SHARE, measure, violations
from core.events.control import SimGmNotePayload


def _note(dropped: int, refs: tuple[str, ...]) -> SimGmNotePayload:
    """A note as the referee actually builds one."""

    return SimGmNotePayload(
        kind="sim.gm.note",
        note="whatever the sentence happens to say",
        dropped_entries=dropped,
        unknown_refs=refs,
    )


def test_the_reading_does_not_depend_on_the_sentence() -> None:
    """The regression that motivated fields: prose the reader must not need."""

    note = SimGmNotePayload(
        kind="sim.gm.note",
        note="completely reworded, in another language, with no digits",
        dropped_entries=7,
        unknown_refs=("internal-admin",),
    )
    assert measure([note], logged=10).dropped == 7


def test_the_measured_known_bad_fails() -> None:
    work = measure([_note(2, ("internal-000001", "admin-000001"))] * 42, logged=416)
    assert work.dropped == 84
    assert work.attempted == 500
    assert 0.16 < work.dropped_share < 0.17
    problems = violations(work)
    assert len(problems) == 1
    assert "16.8%" in problems[0]
    # The message must say the referee was right, or the next reader
    # "fixes" this by making the referee permissive.
    assert "right to reject" in problems[0]
    assert "internal-000001" in problems[0]


def test_a_total_loss_is_visible() -> None:
    """The silent case. Every entry invalid takes the raising branch; it
    now carries the same fields, so the loss is counted rather than
    vanishing from both sides of the ratio."""

    work = measure([_note(60, ("internal-admin",))], logged=0)
    assert work.dropped == 60
    assert work.attempted == 60
    assert work.dropped_share == 1.0
    assert violations(work)


def test_a_healthy_world_passes() -> None:
    assert violations(measure([_note(2, ("x",))], logged=400)) == ()


def test_a_little_drift_is_tolerated() -> None:
    work = measure([_note(2, ("x",))] * 5, logged=400)
    assert work.dropped_share < MAX_DROPPED_SHARE
    assert violations(work) == ()


def test_an_empty_world_is_a_violation_not_a_pass() -> None:
    assert violations(measure([], logged=0)) == (
        "no time was recorded or attempted at all",
    )


def test_notes_about_other_things_are_ignored() -> None:
    """The referee writes many kinds of note; only the ones carrying a
    count are about lost work."""

    other = SimGmNotePayload(
        kind="sim.gm.note", note="Rejected action: an email needs a recipient"
    )
    assert measure([other, _note(2, ("x",))], logged=100).dropped == 2


def test_invented_refs_are_ranked_by_frequency() -> None:
    """The list is the fix list: the codes the world should have offered."""

    work = measure(
        [_note(2, ("admin-000001", "internal-000001")), _note(2, ("admin-000001",))],
        logged=10,
    )
    assert work.invented_refs[0] == ("admin-000001", 2)


@pytest.mark.parametrize("entries", [0, 3])
def test_the_referee_reports_both_branches(entries: int) -> None:
    """Drive the real grounding code, so a change to either branch is
    caught here rather than by a world that quietly measures 0.0%.

    ``entries`` is how many timesheet lines are *valid*: zero exercises
    the all-invalid branch that raises, three exercises the partial branch
    that returns a note.
    """

    from simulation.gm.grounded import IntentRejection

    rejection = IntentRejection(
        "none of these engagements exist",
        dropped_entries=5,
        unknown_refs=("internal-admin",),
    )
    assert rejection.dropped_entries == 5
    assert rejection.unknown_refs == ("internal-admin",)
    # And the note built from a rejection carries them through.
    carried = SimGmNotePayload(
        kind="sim.gm.note",
        note=f"Rejected action from x: {rejection.reason}",
        dropped_entries=rejection.dropped_entries,
        unknown_refs=rejection.unknown_refs,
    )
    assert measure([carried], logged=entries).dropped == 5


def test_the_index_case_a_rate_cannot_see() -> None:
    """A tolerance that cannot catch the smallest instance of what it
    guards is decoration.

    Driven through the referee: twenty clean personas plus one missing two
    admin codes gives 1.19% — at one day, five days, twenty and a hundred
    and thirty. Because it is a rate, run length never accumulates past
    the 3% ceiling, so the gate caught the epidemic and never its seed.

    Persistence separates the two. A reference invented once is a typo;
    the same one invented again and again is somebody reaching for a code
    that ought to exist.
    """

    work = measure([_note(2, ("internal-admin", "internal-bd"))] * 5, logged=830)
    assert work.dropped_share < MAX_DROPPED_SHARE
    problems = violations(work)
    assert len(problems) == 1
    assert "internal-admin" in problems[0]
    assert "typo" in problems[0]


def test_one_mistyped_matter_is_not_a_finding() -> None:
    """The other half of the same judgement: a genuine typo must not fail
    a build, or the gate fires constantly and stops being read."""

    assert violations(measure([_note(1, ("tkt-000999",))], logged=800)) == ()


def test_refs_rank_by_entries_lost_not_by_notes() -> None:
    """This list is billed as the fix list — the codes the world should
    have offered. Ranking by note count put the code responsible for 300
    lost entries below six typos costing four each, and truncation then
    dropped the costliest one off the end."""

    notes = [_note(100, ("internal-admin",))] * 3
    notes += [_note(4, (f"typo-{i}",)) for i in range(6)]
    work = measure(notes, logged=5000)
    assert work.invented_refs[0] == ("internal-admin", 300)


def test_a_note_naming_several_refs_splits_its_entries() -> None:
    """A note carries one count and may name several references; the
    entries are shared out rather than credited to each in full."""

    work = measure([_note(6, ("a", "b", "c"))], logged=100)
    assert dict(work.invented_refs) == {"a": 2, "b": 2, "c": 2}

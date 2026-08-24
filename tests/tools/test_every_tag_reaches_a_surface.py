"""An event kind no tool system handles is a corpus no agent can read.

`meeting.transcript` was in `TAG_REGISTRY` from the first commit, was
emitted by the referee, validated by the world-log validator, counted by a
fidelity band, and **handled by no tool system at all**. It therefore
reached no database, no file and no tool. One six-month recording held 723
transcripts, 3,662 turns and 255,889 words — roughly 30% of everything
anyone at that firm said or wrote — and an agent could read every email
and every message in the firm without learning what was decided in any
room.

Nothing failed, because nothing compared the two registries. Every check
that existed looked at one side or the other:

* the world-log validator asked whether the events were well formed, and
  they were;
* `ToolSystem.__post_init__` asked whether a system declares `sim.*` tags
  it should not, which is the opposite direction;
* the fidelity band `calendar.transcript_share_internal` counted
  `log.count("meeting.transcript")` — the *log*, not the surface — so it
  confirmed the transcripts existed while nobody could read them;
* coherence asked whether every reference in a projected database
  resolves, and an absent database has no references to dangle.

This test is the one line that closes it, and it is deliberately static:
it needs no world, so it fails the moment a tag is added without a reader
rather than the first time somebody builds a bundle and counts.
"""

from core.events import TAG_REGISTRY
from tools import REGISTRY

# Offstage by construction: `sim.*` is the simulation talking to itself —
# wakes, planning, reflection, checkpoints — and `ToolSystem` refuses to
# let a system declare one. They are the machinery, not the workplace.
OFFSTAGE_PREFIX = "sim."


def _handled() -> set[str]:
    return {tag for system in REGISTRY for tag in system.handled_tags}


def test_every_on_stage_tag_is_handled_by_some_system() -> None:
    unhandled = sorted(
        tag
        for tag in TAG_REGISTRY
        if not tag.startswith(OFFSTAGE_PREFIX) and tag not in _handled()
    )
    assert not unhandled, (
        f"these event kinds are recorded into the world and no tool system "
        f"reads them, so no agent can ever see them: {unhandled}. Either give "
        "a system the tag and a projection, or the world is writing a corpus "
        "for nobody."
    )


def test_no_system_claims_a_tag_the_world_cannot_emit() -> None:
    """The other direction: a system reading a kind that does not exist.

    Harmless at runtime — the projection simply never matches — which is
    exactly why it survives. It reads as a supported surface in the
    system's declaration and is a dead branch, and the next person to look
    for a corpus finds the claim rather than the absence.
    """

    unknown = sorted(_handled() - set(TAG_REGISTRY))
    assert not unknown, (
        f"these systems declare event kinds no payload registers: {unknown}. "
        "The projection can never fire, and the declaration advertises a "
        "surface that cannot exist."
    )


def test_the_registries_are_both_populated() -> None:
    """Guard the guard.

    Both assertions above are set differences, and a set difference against
    an empty set is empty. If either registry ever fails to import its
    members, the two tests above pass while comparing nothing — which is
    the failure mode this whole file exists to prevent, one level up.
    """

    assert len(TAG_REGISTRY) > 20, TAG_REGISTRY
    assert len(_handled()) > 10, sorted(_handled())
    assert any(tag.startswith(OFFSTAGE_PREFIX) for tag in TAG_REGISTRY)

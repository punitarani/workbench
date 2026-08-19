"""How much of what the actors tried to record actually landed.

A referee that resolves every reference against world state, and rejects
what it cannot resolve, is the right design — it is what makes a replay
deterministic. But it means a world can be *structurally* incomplete in a
way that looks like correct behaviour: the actors reach for something the
world does not offer, the referee refuses, and the record simply has less
in it than the day did.

Measured on a law firm's first three recorded days: personas logging
admin, internal-meeting and practice-group time had no matter code to log
it against, invented plausible ones (`internal-000001`, `admin-000001`,
`internal-ip-tech-group`), and **84 of 500 attempted entries — 16.8% —
were dropped**. Every rejection was correct. The world was still wrong.

Nothing else would have caught it. Coherence checks look for a fact
carrying two values, not for a fact that never got recorded; the
materializer writes what exists; and a utilisation figure computed over
the survivors is perfectly self-consistent and answers a question about a
firm that does not exist.

So: read the referee's own rejection notes, and treat a high loss rate as
a structural finding about the world rather than as noise.

Read them as **fields**, never as prose. The first version of this parsed
the sentence, and an audit showed what that costs: rewording the
referee's message zeroed the rate with the whole suite green, and the
worst case was silent by construction — a timesheet whose entries were
*all* invalid took a different branch that wrote no matching sentence at
all, so a world that lost everything measured 0.0%.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

# Set between two measured worlds: 16.8% is the known-bad that prompted
# this, and a world with the codes its people need should sit near zero.
# A few percent is real drift — somebody mistyping a matter — and is not
# worth failing a build over.
MAX_DROPPED_SHARE = 0.03


@dataclass(frozen=True)
class AttemptedWork:
    """Recorded time versus time the actors tried to record."""

    logged: int
    dropped: int
    invented_refs: tuple[tuple[str, int], ...]

    @property
    def attempted(self) -> int:
        return self.logged + self.dropped

    @property
    def dropped_share(self) -> float:
        return (self.dropped / self.attempted) if self.attempted else 0.0


class RefereeNote(Protocol):
    """The part of a referee note this reads. Fields, not prose.

    It used to parse the sentence. Three consequences, all measured: an
    ordinary rewording of the referee's f-string zeroed the rate with the
    suite green; the test's "verbatim" copy of that sentence was a
    transcription that imported nothing; and the two sides disagreed about
    whether the number meant entries lost or distinct references invented
    — a fourfold difference that flipped a failing world to passing.
    """

    dropped_entries: int
    unknown_refs: tuple[str, ...]


def measure(notes: list[RefereeNote], logged: int) -> AttemptedWork:
    """Total work refused, read off the referee's own fields."""

    dropped = 0
    refs: dict[str, int] = {}
    for note in notes:
        count = getattr(note, "dropped_entries", 0) or 0
        if not count:
            continue
        dropped += count
        for ref in getattr(note, "unknown_refs", ()) or ():
            refs[ref] = refs.get(ref, 0) + 1
    return AttemptedWork(
        logged=logged,
        dropped=dropped,
        invented_refs=tuple(sorted(refs.items(), key=lambda kv: (-kv[1], kv[0]))),
    )


def violations(work: AttemptedWork) -> tuple[str, ...]:
    if work.attempted == 0:
        return ("no time was recorded or attempted at all",)
    if work.dropped_share <= MAX_DROPPED_SHARE:
        return ()
    invented = ", ".join(ref for ref, _ in work.invented_refs[:5])
    return (
        f"{work.dropped} of {work.attempted} attempted time entries were "
        f"dropped ({work.dropped_share:.1%}, over the "
        f"{MAX_DROPPED_SHARE:.0%} ceiling) against references the world does "
        f"not offer: {invented}. The referee was right to reject them; the "
        "world is missing something its people need. Any figure computed "
        "over the survivors answers a question about a different firm.",
    )


__all__ = ["MAX_DROPPED_SHARE", "AttemptedWork", "measure", "violations"]

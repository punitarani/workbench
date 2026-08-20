"""What kinds of file a materialized world actually contains.

An institution is partly defined by the artifacts it produces. A firm
whose entire file room is markdown is not the firm it claims to model,
and the difference is not cosmetic: opening a workbook, reading a deck
and pulling a table out of a print-form document are distinct pieces of
work, and a world with only prose has silently removed all three.

This is measured rather than asserted because it drifts. The authoring
prompt asks for the real form every time, and one recorded world still
came back 19 markdown and 33 workbooks with no documents, no decks and
no issued PDFs at all — while a later run of the same firm produced
documents and no decks. Format mix is an emergent property of a
generated world, so it belongs with the other measured properties and
not in a comment.

Two failure shapes, and they are different:

**Absence** — a form the institution really produces never appears.
**Corruption** — a file carries a form's extension and is not that form.

The second is the more dangerous, because it is invisible until
something reads the surface. A renderer handed content that does not
parse writes the raw bytes beside the intended name, so the file room
ends up holding a `.txt` whose body is a broken JSON fragment. An agent
told to open the workbook finds text, and the resulting zero reads as a
model failure.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

# The forms a professional institution exchanges, and what each is for.
# Keyed by suffix because that is what an agent sees in the file room.
OFFICE_SUFFIXES = (".docx", ".xlsx", ".pptx", ".pdf")
TABULAR_SUFFIXES = (".xlsx", ".csv")
# The renderer writes these when structured content did not parse. Their
# presence is not a style preference; it is a corrupted artifact.
FALLBACK_SUFFIXES = (".txt",)

# What a file of each form must actually begin with. The office formats
# are zip containers; a print form has its own marker.
#
# Checking the *suffix* only catches the honest failure. A fallback lands
# as `.txt`, which is the one case where the extension tells the truth —
# while a prose body written to a `.csv`, or anything else whose declared
# format and real bytes disagree, passes untouched. This module says
# corruption is the more dangerous of the two failures and then detected
# the benign one.
_MAGIC: dict[str, tuple[bytes, ...]] = {
    ".docx": (b"PK\x03\x04",),
    ".xlsx": (b"PK\x03\x04",),
    ".pptx": (b"PK\x03\x04",),
    ".pdf": (b"%PDF",),
}


def mislabelled(workspace: Path) -> tuple[str, ...]:
    """Files whose bytes are not the form their name claims.

    An agent told to open a workbook and handed prose scores zero, and the
    zero reads as a model failure. Read the first bytes rather than the
    extension: the extension is the claim being checked.
    """

    wrong: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        expected = _MAGIC.get(path.suffix.lower())
        if expected is None:
            continue
        try:
            head = path.open("rb").read(8)
        except OSError:  # pragma: no cover - unreadable file is its own problem
            wrong.append(f"{path.name}: unreadable")
            continue
        if not any(head.startswith(marker) for marker in expected):
            wrong.append(
                f"{path.relative_to(workspace)}: named {path.suffix} but its "
                f"bytes are not {path.suffix}"
            )
    return tuple(wrong)


@dataclass(frozen=True)
class ArtifactMix:
    """The measured file-type composition of one materialized workspace.

    ``total`` must equal the counts it summarises. Without that invariant
    the type accepts `total=1, by_suffix=(('.md', 999))` and reports a
    markdown share of 999.0 — and every test in this module used to build
    its own instances by hand, so a `total` computed wrongly by `measure`
    was checked by nothing at all.
    """

    total: int
    by_suffix: tuple[tuple[str, int], ...]
    # Files whose bytes contradict their extension. Empty is the normal
    # case; anything here is a corrupted artifact, not a style choice.
    mislabelled: tuple[str, ...] = ()
    # How many documents the record says exist. Every share here is
    # computed over the files that survived materialization, so a document
    # that produced no file leaves the numerator *and* the denominator —
    # which raises every share. The bias runs one way only: a world that
    # loses documents reads healthier than one that does not. Measured on
    # a real bundle, 52 declared against 49 on disk moved the office share
    # from 0.365 to 0.388.
    declared: int | None = None
    # How many distinct paths those documents name. Two documents written
    # to one path is a different failure from a document that produced no
    # file, and the fix is different too: the first loses work to a name
    # collision the record still remembers, the second loses it outright.
    distinct_paths: int | None = None
    # Files that exist and hold nothing. A count by suffix cannot see these:
    # a 0-byte `.docx` is one `.docx`, exactly like a 1,600-word one, so a
    # world with empty work product measures as healthy as one without.
    # Measured on a real bundle: three documents registered under full
    # professional titles, with named authors and matters, and no body.
    empty: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        counted = sum(count for _, count in self.by_suffix)
        if counted != self.total:
            raise ValueError(
                f"total {self.total} does not match the {counted} files "
                "counted by suffix; every share computed from this would be "
                "wrong in the same direction"
            )

    @property
    def counts(self) -> dict[str, int]:
        return dict(self.by_suffix)

    def share(self, *suffixes: str) -> float:
        """Fraction of files carrying any of these suffixes, 0.0 when empty."""

        if self.total == 0:
            return 0.0
        counts = self.counts
        return sum(counts.get(s, 0) for s in suffixes) / self.total

    @property
    def markdown_share(self) -> float:
        return self.share(".md")

    @property
    def office_share(self) -> float:
        return self.share(*OFFICE_SUFFIXES)

    @property
    def fallback_count(self) -> int:
        counts = self.counts
        return sum(counts.get(s, 0) for s in FALLBACK_SUFFIXES)

    @property
    def missing_forms(self) -> tuple[str, ...]:
        counts = self.counts
        return tuple(s for s in OFFICE_SUFFIXES if counts.get(s, 0) == 0)


def measure(
    workspace: Path,
    *,
    declared: int | None = None,
    distinct_paths: int | None = None,
) -> ArtifactMix:
    """Count files by suffix under a materialized workspace.

    ``declared`` is how many documents the record holds. Supply it: without
    it every share is computed over the survivors, and losing a document
    improves the numbers.
    """

    counts: Counter[str] = Counter()
    empty: list[str] = []
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        counts[suffix or "(none)"] += 1
        if path.stat().st_size == 0:
            empty.append(str(path.relative_to(workspace)))
    return ArtifactMix(
        total=sum(counts.values()),
        by_suffix=tuple(sorted(counts.items())),
        mislabelled=mislabelled(workspace),
        declared=declared,
        distinct_paths=distinct_paths,
        empty=tuple(empty),
    )


@dataclass(frozen=True)
class MixFloors:
    """Thresholds set between measured worlds, not at round numbers.

    Every world this tree has produced, measured:

    | world      | files | markdown | office | fallbacks |
    |------------|-------|----------|--------|-----------|
    | chronicle  |    36 |   100.0% |   0.0% |         0 |
    | audit v1   |    49 |    40.8% |  38.8% |        10 |
    | accounting |    17 |    35.3% |  64.7% |         0 |
    | law firm   |    13 |     0.0% |  92.3% |         1 |

    A 15% markdown ceiling and a 70% office floor fall between the worst
    three and the fourth, which is the point — a band that no measured
    world sits inside is a wall, and one every world clears is decoration.

    `required_forms` is the exception and is deliberately *aspirational*:
    no recorded world has ever emitted a deck, though the renderer makes a
    valid 28KB one on demand and the authoring schema has the field. That
    is a fact about worlds that gave nobody an occasion to present, not
    about the capability, so the floor states what the institution owes
    rather than what its predecessors managed.
    """

    max_markdown_share: float
    min_office_share: float
    max_fallbacks: int
    # Which office forms this institution genuinely produces. A firm that
    # never presents to a committee should not be failed for having no
    # decks, so this is per-world rather than universal.
    required_forms: tuple[str, ...]


def violations(mix: ArtifactMix, floors: MixFloors) -> tuple[str, ...]:
    """Every way this workspace falls short, as readable sentences."""

    found: list[str] = []
    if mix.total == 0:
        return ("the workspace is empty",)
    if mix.empty:
        found.append(
            f"{len(mix.empty)} file(s) hold no content at all: "
            f"{list(mix.empty[:3])} — a count by suffix cannot see this, and "
            "an empty file is work product that was registered and lost"
        )
    if mix.markdown_share > floors.max_markdown_share:
        found.append(
            f"markdown is {mix.markdown_share:.0%} of {mix.total} files, "
            f"over the {floors.max_markdown_share:.0%} ceiling — a firm's "
            "file room is not made of notes"
        )
    if mix.office_share < floors.min_office_share:
        found.append(
            f"real office formats are {mix.office_share:.0%}, under the "
            f"{floors.min_office_share:.0%} floor"
        )
    if mix.declared is not None and mix.total < mix.declared:
        # Split the shortfall, because the two halves call for different
        # fixes. Documents sharing a path overwrite each other — the work
        # exists in the record and the file room shows one of it.
        # Documents that produced nothing are lost outright.
        collided = (
            0
            if mix.distinct_paths is None
            else max(0, mix.declared - mix.distinct_paths)
        )
        vanished = mix.declared - mix.total - collided
        parts = []
        if collided:
            parts.append(
                f"{collided} were written to a path another document "
                "already used, so the file room shows the last one only"
            )
        if vanished > 0:
            parts.append(f"{vanished} produced no file at all")
        found.append(
            f"the record holds {mix.declared} documents and the file room "
            f"has {mix.total}: " + "; ".join(parts) + ". Every share above "
            "is computed over what survived, so the loss makes the mix read "
            "better than it is"
        )
    if mix.mislabelled:
        found.append(
            f"{len(mix.mislabelled)} file(s) are not the form their name "
            f"claims: {'; '.join(mix.mislabelled[:3])}"
        )
    if mix.fallback_count > floors.max_fallbacks:
        found.append(
            f"{mix.fallback_count} files are raw-text fallbacks, over the "
            f"{floors.max_fallbacks} allowed — each one claims a form it "
            "does not have"
        )
    counts = mix.counts
    absent = [form for form in floors.required_forms if counts.get(form, 0) == 0]
    if absent:
        found.append(
            f"produces no {', '.join(absent)} at all, though this institution's "
            "work includes them"
        )
    return tuple(found)


__all__ = [
    "FALLBACK_SUFFIXES",
    "mislabelled",
    "OFFICE_SUFFIXES",
    "TABULAR_SUFFIXES",
    "ArtifactMix",
    "MixFloors",
    "measure",
    "violations",
]

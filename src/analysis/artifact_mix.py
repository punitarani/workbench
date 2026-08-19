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


def measure(workspace: Path) -> ArtifactMix:
    """Count files by suffix under a materialized workspace."""

    counts: Counter[str] = Counter()
    for path in sorted(workspace.rglob("*")):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        counts[suffix or "(none)"] += 1
    return ArtifactMix(
        total=sum(counts.values()),
        by_suffix=tuple(sorted(counts.items())),
    )


@dataclass(frozen=True)
class MixFloors:
    """Thresholds, set between a measured known-bad and a known-good world
    rather than at a round number. A band picked by intuition either never
    fires or fires constantly, and in both cases stops being read.

    The known-bad this is set against: a recorded world of 52 documents
    that materialized 19 markdown, 33 workbooks, zero documents, zero
    decks, zero issued PDFs, and 10 unparseable `.txt` fallbacks.
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
    "OFFICE_SUFFIXES",
    "TABULAR_SUFFIXES",
    "ArtifactMix",
    "MixFloors",
    "measure",
    "violations",
]

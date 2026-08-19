"""The file-room gate, tested against the world that motivated it.

Materialized bundles live in gitignored output directories, so a test
that pointed at one would skip in CI and never fail. The floors are
therefore exercised against fixtures built to the exact shape of a
recorded world — a check that only runs on a developer's laptop is not
a check.

The known-bad is real and is reproduced below: 49 files, 20 markdown, 19
workbooks, 10 raw-text fallbacks, and no documents, decks or issued PDFs
at all, from a firm whose authoring prompt asked for the real form every
single time. Format mix is an emergent property, and emergent properties
drift.
"""

from pathlib import Path

import pytest

from analysis.artifact_mix import ArtifactMix, MixFloors, measure, violations

FLOORS = MixFloors(
    max_markdown_share=0.20,
    min_office_share=0.60,
    max_fallbacks=0,
    required_forms=(".docx", ".xlsx", ".pdf"),
)

# Exactly what one recorded world materialized.
KNOWN_BAD = ArtifactMix(
    total=49,
    by_suffix=((".md", 20), (".txt", 10), (".xlsx", 19)),
)

# What a firm's file room looks like when the forms are real.
KNOWN_GOOD = ArtifactMix(
    total=60,
    by_suffix=((".docx", 18), (".md", 6), (".pdf", 12), (".pptx", 6), (".xlsx", 18)),
)


def test_the_known_bad_world_fails_every_way_it_should() -> None:
    found = violations(KNOWN_BAD, FLOORS)
    assert len(found) == 4, found
    joined = " ".join(found)
    assert "markdown" in joined
    assert "office formats" in joined
    assert "fallback" in joined
    assert ".docx" in joined and ".pdf" in joined


def test_the_known_good_world_passes() -> None:
    """A floor that fails everything is not calibrated, it is just a wall."""

    assert violations(KNOWN_GOOD, FLOORS) == ()


def test_one_corrupt_file_is_enough_to_fail() -> None:
    """A file claiming a form it does not have is a defect, not a ratio.
    An agent told to open the workbook finds text, and the zero it scores
    reads as a model failure."""

    nearly = ArtifactMix(
        total=60,
        by_suffix=(
            (".docx", 18),
            (".md", 5),
            (".pdf", 12),
            (".pptx", 6),
            (".txt", 1),
            (".xlsx", 18),
        ),
    )
    found = violations(nearly, FLOORS)
    assert len(found) == 1 and "fallback" in found[0], found


def test_an_empty_workspace_is_a_violation_not_a_pass() -> None:
    """Every ratio is vacuously fine at zero files. Without this, a
    materializer that wrote nothing would sail through."""

    assert violations(ArtifactMix(total=0, by_suffix=()), FLOORS) == (
        "the workspace is empty",
    )


def test_required_forms_are_per_world() -> None:
    """A firm that never presents to a committee should not be failed for
    having no decks."""

    no_decks = MixFloors(
        max_markdown_share=0.20,
        min_office_share=0.60,
        max_fallbacks=0,
        required_forms=(".docx", ".xlsx"),
    )
    mix = ArtifactMix(total=40, by_suffix=((".docx", 20), (".md", 4), (".xlsx", 16)))
    assert violations(mix, no_decks) == ()
    assert violations(mix, FLOORS)  # the same world fails when PDFs are required


def test_share_of_an_empty_mix_is_zero_not_a_crash() -> None:
    assert ArtifactMix(total=0, by_suffix=()).share(".docx") == 0.0


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (("a/b.docx", "a/c.xlsx"), {".docx": 1, ".xlsx": 1}),
        (("a/B.DOCX",), {".docx": 1}),  # suffix comparison is case-insensitive
        (("a/no-suffix",), {"(none)": 1}),
    ],
)
def test_measure_counts_what_is_on_disk(
    tmp_path: Path, files: tuple[str, ...], expected: dict[str, int]
) -> None:
    for name in files:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")
    assert measure(tmp_path).counts == expected


def test_measure_and_violations_are_connected(tmp_path: Path) -> None:
    """The gate is `measure` feeding `violations`, and nothing tested the
    join. Every case above builds an `ArtifactMix` by hand with a
    hand-supplied `total`, so two mutations of `measure` left the suite
    green while disabling the gate entirely: `total = len(counts)` made a
    49-file workspace report an office share of 6.33 with the floor
    violation silently gone, and skipping `.md` in the suffix loop made a
    100%-markdown world report a markdown share of 0.0.
    """

    for name in ("a/note.md", "a/b/other.md", "a/c/third.md"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x")

    mix = measure(tmp_path)
    assert mix.total == 3
    assert mix.markdown_share == 1.0
    problems = violations(mix, FLOORS)
    assert any("markdown" in problem for problem in problems)
    assert any("office formats" in problem for problem in problems)


def test_total_must_match_the_counts_it_summarises() -> None:
    """A hand-built mix whose total disagrees with its own counts reports
    a share above 1.0 and every floor derived from it is meaningless."""

    with pytest.raises(ValueError):
        ArtifactMix(total=1, by_suffix=((".md", 999),))

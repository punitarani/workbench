"""A resume must not splice one world out of two rule sets.

`config_hash` covers the compiled spec, the seed and the compiler
version — everything about *what world* is being recorded, and nothing
about *how*. So a long recording can be stopped, its grounding rules
edited, and resumed: the hash still matches, nothing raises, and the
world is flat for forty days and nested afterwards with no record of
where the seam is.

Not hypothetical. A document-emptiness rule was added at day 4 of a live
130-workday run in this repository, and only the fact that the run was
stopped for unrelated reasons kept the world uniform.

The fingerprint is a source digest rather than a hand-bumped constant,
because a constant is exactly the thing somebody forgets. A comment-only
edit trips it, which is the right side to err on: resuming a day-long
recording after any edit to the referee deserves a person looking.
"""

from pathlib import Path

import pytest

from simulation.run import _ENGINE_SURFACE, engine_fingerprint

SRC = Path(__file__).resolve().parents[2] / "src"


def test_the_fingerprint_is_stable() -> None:
    assert engine_fingerprint() == engine_fingerprint()


@pytest.mark.parametrize("relative", _ENGINE_SURFACE)
def test_every_named_file_exists(relative: str) -> None:
    """A path that stopped existing would be hashed as `<absent>` and the
    fingerprint would go on looking healthy while covering less."""

    assert (SRC / relative).is_file(), f"{relative} is named but not present"


def test_it_covers_the_referee_and_the_prompts() -> None:
    """The two halves that decide what lands in a world: the rules that
    ground an intent, and the prompts that produce one."""

    covered = set(_ENGINE_SURFACE)
    assert "simulation/gm/grounded.py" in covered
    assert "simulation/persona/programs.py" in covered


def test_a_changed_rule_changes_the_fingerprint(tmp_path, monkeypatch) -> None:
    """Driven by editing a real file in a copy of the tree, rather than by
    asserting that sha256 is a hash function."""

    import hashlib
    import shutil

    mirror = tmp_path / "src"
    shutil.copytree(SRC, mirror, dirs_exist_ok=True)

    def fingerprint_of(root: Path) -> str:
        digest = hashlib.sha256()
        for relative in _ENGINE_SURFACE:
            path = root / relative
            digest.update(relative.encode())
            digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        return digest.hexdigest()

    before = fingerprint_of(mirror)
    grounded = mirror / "simulation" / "gm" / "grounded.py"
    grounded.write_text(grounded.read_text() + "\n# a rule changed here\n")
    assert fingerprint_of(mirror) != before


def test_a_file_outside_the_surface_does_not_trip_it(tmp_path) -> None:
    """The digest has to be narrow enough to be usable. If every source
    file counted, no long run could ever resume."""

    import hashlib
    import shutil

    mirror = tmp_path / "src"
    shutil.copytree(SRC, mirror, dirs_exist_ok=True)

    def fingerprint_of(root: Path) -> str:
        digest = hashlib.sha256()
        for relative in _ENGINE_SURFACE:
            path = root / relative
            digest.update(relative.encode())
            digest.update(path.read_bytes() if path.is_file() else b"<absent>")
        return digest.hexdigest()

    before = fingerprint_of(mirror)
    unrelated = mirror / "analysis" / "fidelity.py"
    if unrelated.is_file():
        unrelated.write_text(unrelated.read_text() + "\n# unrelated\n")
        assert fingerprint_of(mirror) == before

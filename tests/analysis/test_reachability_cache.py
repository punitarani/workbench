"""The crawl is cached across builds, and keyed on what its answer depends on.

It is the dominant cost of a build — roughly eighteen minutes of the
twenty-five a single-task build takes — and it was repeated in full every
time, because `materialize` rewrites `state/` from scratch and the
in-process memo dies with the process.

**The obvious key does not work.** Hashing the databases looked right and
failed in exactly the case the cache exists for: two SQLite files holding
identical rows differ byte for byte after a rebuild — page layout,
freelists, insertion order — so the digest changed on every build and the
cache never once hit. The test below is what found that.

The served state is a deterministic projection of one world log, so the
log is the honest key, and `SOURCE` records which log built this bundle.

Getting this wrong in the stale direction would be serious in a way a
slow build is not: a reachability verdict carried from another world
would let an oracle name values that world does not serve, which is the
defect the gate exists to catch. So every test here is about the key.
"""

import json
from pathlib import Path

from analysis.reachability import _CACHE_NAME, _read_cache, _state_digest, _write_cache


def _bundle(root: Path, log_text: str, *, source: bool = True) -> Path:
    log = root / "world.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(log_text)
    state = root / "bundle" / "state"
    state.mkdir(parents=True, exist_ok=True)
    if source:
        (state.parent / "SOURCE").write_text(str(log.resolve()) + "\n")
    return state


def test_the_same_world_log_gives_the_same_key(tmp_path: Path) -> None:
    a = _bundle(tmp_path / "a", '{"seq":1}\n')
    b = _bundle(tmp_path / "b", '{"seq":1}\n')
    assert _state_digest(a) == _state_digest(b) is not None


def test_a_different_world_gives_a_different_key(tmp_path: Path) -> None:
    a = _bundle(tmp_path / "a", '{"seq":1}\n')
    before = _state_digest(a)
    (tmp_path / "a" / "world.jsonl").write_text('{"seq":2}\n')
    assert _state_digest(a) != before


def test_a_rebuilt_bundle_hits(tmp_path: Path) -> None:
    """The case the cache exists for, and the one the byte-hash version
    failed: the databases are rewritten from the same log."""

    state = _bundle(tmp_path / "w", '{"seq":1}\n')
    fingerprint = _state_digest(state)
    _write_cache(state, fingerprint, {"msg-000001", "LEGAL!1.2"})
    # materialize runs again: state/ is wholly rewritten, the log is not.
    for stale in state.glob("*"):
        stale.unlink()
    assert _read_cache(state, _state_digest(state)) == {"msg-000001", "LEGAL!1.2"}


def test_a_bundle_from_another_world_misses(tmp_path: Path) -> None:
    state = _bundle(tmp_path / "w", '{"seq":1}\n')
    _write_cache(state, _state_digest(state), {"msg-000001"})
    (tmp_path / "w" / "world.jsonl").write_text('{"seq":99}\n')
    assert _read_cache(state, _state_digest(state)) is None


def test_unknown_provenance_is_not_a_key(tmp_path: Path) -> None:
    """No SOURCE means crawl. A missing key must never be treated as a
    matching one, or every bundle without provenance shares an answer."""

    state = _bundle(tmp_path / "w", '{"seq":1}\n', source=False)
    assert _state_digest(state) is None


def test_a_source_naming_a_missing_log_is_not_a_key(tmp_path: Path) -> None:
    state = _bundle(tmp_path / "w", '{"seq":1}\n')
    (tmp_path / "w" / "world.jsonl").unlink()
    assert _state_digest(state) is None


def test_a_corrupt_cache_is_a_miss_not_a_crash(tmp_path: Path) -> None:
    state = _bundle(tmp_path / "w", '{"seq":1}\n')
    (state.parent / _CACHE_NAME).write_text("{not json")
    assert _read_cache(state, _state_digest(state)) is None


def test_the_cache_round_trips_through_json(tmp_path: Path) -> None:
    state = _bundle(tmp_path / "w", '{"seq":1}\n')
    fingerprint = _state_digest(state)
    _write_cache(state, fingerprint, {"b", "a"})
    stored = json.loads((state.parent / _CACHE_NAME).read_text())
    assert stored["reachable"] == ["a", "b"]
    assert _read_cache(state, fingerprint) == {"a", "b"}

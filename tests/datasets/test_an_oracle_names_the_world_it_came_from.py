"""One message covered two failures, and only one of them was a bug.

`build_tasks` refuses when the reference solver stops reproducing a
committed oracle. That refusal used to read:

    the reference solver no longer reproduces its oracle.
    Rebuild the world or pass --refresh-truth deliberately.

which is printed in two situations that call for opposite responses:

* the bundle is the **same world** and the answer changed -- the solver,
  the tools or the projection regressed, and the thing to do is go find
  out which;
* the bundle is a **later recording** -- entirely expected, and the thing
  to do is exactly the `--refresh-truth` the message offers.

Reaching for the refresh is right half the time and, the other half,
writes an unexamined new answer down as truth -- which is the only thing
this gate exists to prevent. A reader who is told to refresh whenever the
gate fires has been trained to disable it.

The fix is provenance: the oracle is written with a sibling
`oracle.world` naming the world log and its sha256, so the gate can ask
*which world* before it decides what kind of failure it is looking at.

This dataset arrived at the question the hard way -- `build_tasks` already
carries two long comments about "a fresh answer key against a stale
world", each added after a different route to it -- and both of those
guard the bundle *during* a build. Neither survives the build: nothing on
disk recorded which world an answer key belonged to, and one probe-derived
oracle was committed to the repository keyed to `epoch-v6` while the
shipping recording was `epoch-v7`.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from dataset_modules import merrick_build_tasks

B = merrick_build_tasks()

OTHER_WORLD = {
    "world_log": "/somewhere/out/merrick/epoch-v6/world.jsonl",
    "sha256": "deadbeef" * 8,
}


@pytest.fixture
def oracle(tmp_path: Path) -> Path:
    path = tmp_path / "oracle.json"
    path.write_text(json.dumps({"rows": [{"a": 1}], "n": 1}))
    return path


def test_a_reproduced_key_says_nothing(oracle: Path) -> None:
    B._refuse_a_key_that_no_longer_reproduces("t", oracle, {"rows": [{"a": 1}], "n": 1})


def test_same_world_different_answer_is_named_a_regression(
    oracle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression branch, on a world this test creates.

    It used to stamp with `_world_identity()` as it stood, which reads
    `out/merrick/bundle/SOURCE` -- present on the machine this was written
    on and absent in a fresh checkout, where the identity degrades to empty
    strings and the branch under test cannot be reached. It passed here and
    failed in a worktree, which is the same disease as a test that cannot
    fail: green for a reason that has nothing to do with the assertion.
    """

    log = tmp_path / "epoch-vX" / "world.jsonl"
    log.parent.mkdir()
    log.write_text('{"day": 1}\n')
    source = tmp_path / "SOURCE"
    source.write_text(str(log) + "\n")
    monkeypatch.setattr(B, "_SOURCE", source)

    B._world_stamp_path(oracle).write_text(json.dumps(B._world_identity()))
    with pytest.raises(SystemExit) as raised:
        B._refuse_a_key_that_no_longer_reproduces("t", oracle, {"n": 2})
    message = str(raised.value)
    assert "REGRESSION" in message
    # The remedy has to be refused *by name*. "Do not refresh" as a
    # sentiment is not enough when the other branch's remedy is the flag.
    assert "do NOT pass --refresh-truth" in message


def test_a_later_world_is_named_a_re_derivation(oracle: Path) -> None:
    B._world_stamp_path(oracle).write_text(json.dumps(OTHER_WORLD))
    with pytest.raises(SystemExit) as raised:
        B._refuse_a_key_that_no_longer_reproduces("t", oracle, {"n": 2})
    message = str(raised.value)
    assert "REGRESSION" not in message
    assert "--refresh-truth" in message
    assert "deadbeefdead" in message, "say which world the key belonged to"


def test_the_same_directory_recorded_twice_is_two_worlds(
    oracle: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The case a path alone cannot see -- recorded, then re-recorded.

    Every recording in this project appends to a path it will append to
    again: `epoch-v7/world.jsonl` at day 40 and at day 180 are the same
    string and different corpora. If the identity held the path only, a
    key derived from the partial recording would compare equal to the
    finished one and the gate would call the re-derivation a solver
    regression -- sending the reader to hunt a bug that is not there.

    An earlier version of this test asserted that by *writing a stamp with
    a different sha by hand*, which proves only that the comparison reads
    the field it is handed. Mutating `_world_identity` to digest the path
    instead of the bytes left it green. So the world log is really grown
    here, at one unchanging path, and the identity is asked both times.
    """

    log = tmp_path / "epoch-v7" / "world.jsonl"
    log.parent.mkdir()
    source = tmp_path / "SOURCE"
    monkeypatch.setattr(B, "_SOURCE", source)
    source.write_text(str(log) + "\n")

    log.write_text('{"day": 1}\n')
    at_day_one = B._world_identity()
    log.write_text('{"day": 1}\n{"day": 2}\n')
    at_day_two = B._world_identity()

    assert at_day_one["world_log"] == at_day_two["world_log"], (
        "the premise: one path, two corpora"
    )
    assert at_day_one["sha256"] != at_day_two["sha256"], (
        "a path is not an identity -- the digest has to read the bytes"
    )

    # And the gate built on it reaches the re-derivation branch, not the
    # regression branch, for a key stamped with the earlier recording.
    B._world_stamp_path(oracle).write_text(json.dumps(at_day_one))
    with pytest.raises(SystemExit) as raised:
        B._refuse_a_key_that_no_longer_reproduces("t", oracle, {"n": 2})
    assert "REGRESSION" not in str(raised.value)


def test_an_unstamped_oracle_is_not_called_a_regression(oracle: Path) -> None:
    """Every key committed before the stamp existed has no stamp.

    Treating "no provenance" as "same world" would greet the first build
    after this change with a regression report for each of them, and a
    false alarm on the first firing is how a gate gets ignored.
    """

    assert not B._world_stamp_path(oracle).exists()
    with pytest.raises(SystemExit) as raised:
        B._refuse_a_key_that_no_longer_reproduces("t", oracle, {"n": 2})
    assert "REGRESSION" not in str(raised.value)
    assert "an unrecorded world" in str(raised.value)


def test_the_stamp_is_not_inside_the_answer_key(oracle: Path) -> None:
    """`criteria_base` does `TOP = frozenset(_ORACLE)`.

    The oracle's top-level keys are the list of figures the report is
    graded on, so provenance added as a `_world` key would become a figure
    every answer is missing and every score would drop. It has to be a
    sibling file, and the name must not be the oracle itself.
    """

    stamp = B._world_stamp_path(oracle)
    assert stamp != oracle
    assert stamp.parent == oracle.parent
    assert stamp.name == "oracle.world"


def test_a_refused_build_rolls_back_the_stamp_with_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stamp must not outlive the answer it describes.

    Written outside the rollback, a build that fails a later gate leaves
    the *new* world named against the *restored old* answer. The next
    build then reads the two as the same world and reports a solver
    regression for a key that was never rewritten -- the false alarm this
    whole change exists to remove, reintroduced by the change itself.
    """

    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    oracle = task / "tests" / "oracle.json"
    oracle.write_text(json.dumps({"n": 1}))
    stamp = B._world_stamp_path(oracle)
    stamp.write_text(json.dumps(OTHER_WORLD))

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise SystemExit("a later gate refused")

    monkeypatch.setattr(B, "_run_second_derivation", refuse)

    with pytest.raises(SystemExit):
        B._commit_oracle(task, "t", {"n": 999}, oracle, fresh=False)

    assert json.loads(oracle.read_text()) == {"n": 1}, "the old key survives"
    assert json.loads(stamp.read_text()) == OTHER_WORLD, "and so does its world"


def test_a_first_build_that_fails_leaves_neither_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction: nothing to restore means nothing left behind.

    A stamp for an oracle that does not exist would be read by the next
    build as provenance for whatever key is written next.
    """

    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    oracle = task / "tests" / "oracle.json"

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise SystemExit("a later gate refused")

    monkeypatch.setattr(B, "_run_second_derivation", refuse)

    with pytest.raises(SystemExit):
        B._commit_oracle(task, "t", {"n": 999}, oracle, fresh=True)

    assert not oracle.exists()
    assert not B._world_stamp_path(oracle).exists()


def test_the_identity_is_content_not_a_path() -> None:
    """Guard the guard: an identity that is always empty compares equal.

    `_world_identity` degrades to empty strings when `SOURCE` is missing or
    names a log that is gone. Every branch above keys off `sha256` being
    *truthy*, so an always-empty identity would silently route every case
    to the re-derivation message -- including a real regression.
    """

    identity = B._world_identity()
    assert set(identity) == {"world_log", "sha256"}
    if identity["sha256"]:
        assert len(identity["sha256"]) == 64
        assert identity["world_log"].endswith(".jsonl")


def test_a_committed_oracle_is_stamped_with_the_world_it_came_from(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The write, not the read.

    Every test above exercises the gate that *reads* the stamp. Deleting
    the line that writes it left all of them green -- which is the
    capability-without-a-caller shape in miniature, and worse than it
    sounds: with nothing writing a stamp, every oracle is unstamped
    forever, every comparison routes to the re-derivation branch, and the
    SOLVER REGRESSION message this whole file exists to produce can never
    fire. A reader tested against a writer that does not run agrees with
    everything.
    """

    log = tmp_path / "epoch-vX" / "world.jsonl"
    log.parent.mkdir()
    log.write_text('{"day": 1}\n')
    source = tmp_path / "SOURCE"
    source.write_text(str(log) + "\n")
    monkeypatch.setattr(B, "_SOURCE", source)
    monkeypatch.setattr(B, "_run_second_derivation", lambda *a, **k: None)
    monkeypatch.setattr(B, "_ship_grading_base", lambda *a, **k: None)
    # `_commit_oracle` also runs the floors gate added on 2026-08-23, and a
    # synthetic task has no test.sh for Reward Kit to run, so the gate
    # correctly refuses "baselines could not be measured". Stubbed because
    # this test is about the stamp; the gate has its own file.
    monkeypatch.setattr(
        B.baselines, "refuse_a_task_a_dump_can_pass", lambda *a, **k: None
    )

    task = tmp_path / "task"
    (task / "tests").mkdir(parents=True)
    oracle = task / "tests" / "oracle.json"
    B._commit_oracle(task, "t", {"rows": [{"a": 1}]}, oracle, fresh=True)

    stamp = B._world_stamp_path(oracle)
    assert stamp.is_file(), "the answer key shipped without its provenance"
    written = json.loads(stamp.read_text())
    assert written == B._world_identity()
    assert written["sha256"] == hashlib.sha256(log.read_bytes()).hexdigest()
    assert written["world_log"] == str(log)


def test_the_stamp_follows_the_world_it_was_written_against(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Guard the guard: a stamp that is always the same value proves nothing.

    The test above compares the stamp to `_world_identity()`, and both
    would agree on a constant. Two worlds, two commits, two stamps.
    """

    monkeypatch.setattr(B, "_run_second_derivation", lambda *a, **k: None)
    monkeypatch.setattr(B, "_ship_grading_base", lambda *a, **k: None)
    monkeypatch.setattr(
        B.baselines, "refuse_a_task_a_dump_can_pass", lambda *a, **k: None
    )
    seen = []
    for index, body in enumerate(('{"day": 1}\n', '{"day": 1}\n{"day": 2}\n')):
        world = tmp_path / f"w{index}"
        world.mkdir()
        log = world / "world.jsonl"
        log.write_text(body)
        source = world / "SOURCE"
        source.write_text(str(log) + "\n")
        monkeypatch.setattr(B, "_SOURCE", source)
        task = tmp_path / f"task{index}"
        (task / "tests").mkdir(parents=True)
        oracle = task / "tests" / "oracle.json"
        B._commit_oracle(task, "t", {"rows": [{"a": index}]}, oracle, fresh=True)
        seen.append(json.loads(B._world_stamp_path(oracle).read_text())["sha256"])
    assert seen[0] != seen[1], "the stamp does not follow the world"

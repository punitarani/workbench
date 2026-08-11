"""Contract tests for fresh-bundle Hartwell oracle certification."""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import build_tasks  # noqa: E402


def _task(tmp_path: Path, source: str) -> tuple[Path, Path]:
    task = tmp_path / "task"
    solution = task / "solution"
    tests = task / "tests"
    bundle = task / "bundle"
    solution.mkdir(parents=True)
    tests.mkdir()
    (bundle / "state").mkdir(parents=True)
    (bundle / "workspace").mkdir()
    (solution / "solve.py").write_text(source)
    return task, bundle


def test_oracle_output_is_canonical_and_workspace_is_unchanged(tmp_path: Path) -> None:
    task, bundle = _task(
        tmp_path,
        "import json\nprint(json.dumps({'z': [2, 1], 'a': 'value'}))\n",
    )
    before = build_tasks.hash_tree(bundle / "workspace")

    actual = build_tasks.run_oracle(task, bundle)

    assert actual == b'{\n  "a": "value",\n  "z": [\n    2,\n    1\n  ]\n}\n'
    assert build_tasks.hash_tree(bundle / "workspace") == before


def test_oracle_rejects_workspace_mutation(tmp_path: Path) -> None:
    task, bundle = _task(
        tmp_path,
        "from pathlib import Path\nPath('leak.txt').write_text('x')\nprint('{}')\n",
    )

    with pytest.raises(build_tasks.OracleError, match="modified the agent workspace"):
        build_tasks.run_oracle(task, bundle)


@pytest.mark.parametrize("output", ["[]", '{"value": NaN}', "not json"])
def test_oracle_rejects_invalid_deliverables(tmp_path: Path, output: str) -> None:
    task, bundle = _task(tmp_path, f"print({output!r})\n")

    with pytest.raises(build_tasks.OracleError, match="valid finite JSON object"):
        build_tasks.run_oracle(task, bundle)


def test_default_check_fails_loudly_on_missing_or_drifted_truth(tmp_path: Path) -> None:
    task, bundle = _task(tmp_path, "print('{\"answer\": 7}')\n")

    with pytest.raises(build_tasks.OracleDriftError, match="missing"):
        build_tasks.certify_oracle(task, bundle, refresh=False)

    (task / "tests" / "oracle.json").write_text('{"answer": 6}\n')
    with pytest.raises(build_tasks.OracleDriftError, match="does not match"):
        build_tasks.certify_oracle(task, bundle, refresh=False)


def test_explicit_refresh_writes_canonical_truth_then_default_check_passes(
    tmp_path: Path,
) -> None:
    task, bundle = _task(tmp_path, "print('{\"answer\": 7}')\n")

    artifact = build_tasks.certify_oracle(task, bundle, refresh=True)

    assert artifact == task / "tests" / "oracle.json"
    assert artifact.read_bytes() == b'{\n  "answer": 7\n}\n'
    assert build_tasks.certify_oracle(task, bundle, refresh=False) == artifact


def test_harbor_staging_occurs_only_after_oracle_certification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task, bundle = _task(tmp_path, "print('{}')\n")
    (task / "task.toml").write_text(
        '[environment]\n[[environment.mcp_servers]]\nname="gmail"\n'
    )
    world = tmp_path / "world.jsonl"
    world.write_text("{}\n")
    calls: list[str] = []

    def fake_materialize(world_log: Path, target: Path) -> SimpleNamespace:
        assert world_log == world
        assert target == bundle
        calls.append("materialize")
        return SimpleNamespace(event_count=1, bundle=bundle)

    def fake_certify(task_path: Path, bundle_path: Path, *, refresh: bool) -> Path:
        assert (task_path, bundle_path, refresh) == (task, bundle, False)
        calls.append("certify")
        return task / "tests" / "oracle.json"

    def fake_stage(bundle_path: Path, environment: Path) -> Path:
        assert (bundle_path, environment) == (bundle, task / "environment")
        calls.append("stage")
        return environment / ".workbench"

    monkeypatch.setattr(build_tasks, "materialize", fake_materialize)
    monkeypatch.setattr(build_tasks, "certify_oracle", fake_certify)
    monkeypatch.setattr(build_tasks, "stage", fake_stage)

    build_tasks.build_task(world, task, refresh=False)

    assert calls == ["materialize", "certify", "stage"]


def test_cli_requires_explicit_refresh_flag() -> None:
    parser = build_tasks.parser()

    assert parser.parse_args([]).refresh_truth is False
    assert parser.parse_args(["--refresh-truth"]).refresh_truth is True

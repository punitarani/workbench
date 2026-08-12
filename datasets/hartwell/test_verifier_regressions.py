"""Cross-task regressions for the Hartwell verifier boundary."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARTWELL = Path(__file__).parent
TASKS = HARTWELL / "tasks"
REWARDKIT = shutil.which("rewardkit")

type TaskCase = tuple[str, str, str, str]

CASES: tuple[TaskCase, ...] = (
    (
        "billing-hygiene-audit",
        "hygiene.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "client-departure-postmortem",
        "postmortem.json",
        "search_threads",
        "gmail__search_threads",
    ),
    (
        "fee-dispute-reconstruction",
        "dispute.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "operative-deadline",
        "deadline.json",
        "slack_search_public_and_private",
        "slack__slack_search_public_and_private",
    ),
    (
        "second-read-audit",
        "second-read.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "settlement-authority-audit",
        "authority.json",
        "search_threads",
        "gmail__search_threads",
    ),
    (
        "standard-drift",
        "drift.json",
        "get_document_versions",
        "imanage__get_document_versions",
    ),
    (
        # clause.json, not vanished.json: the table named a file the task
        # never asks for, so this row's malformed-deliverable regression was
        # grading an empty workspace and passing for the wrong reason.
        "vanished-clause",
        "clause.json",
        "get_document_versions",
        "imanage__get_document_versions",
    ),
    (
        "visitor-log-audit",
        "visitor-log.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
)

pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")

# The task's own ``*_reconciles`` criterion, which certifies that the evidence
# ledger adds up to the public summary. Named per task so a regression can
# read the single criterion rather than the blended dimension.
RECONCILING: dict[str, str] = {
    "billing-hygiene-audit": "daily_review_reconciles",
    "second-read-audit": "response_audit_reconciles",
    "standard-drift": "version_audit_reconciles",
    "vanished-clause": "ledger_reconciles",
    "visitor-log-audit": "custody_audit_reconciles",
}

# Fields the public contract requires to be non-empty strings, so a hollowed
# deliverable still parses as one and reaches the criteria under test.
REQUIRED_NONEMPTY: dict[str, frozenset[str]] = {
    "settlement-authority-audit": frozenset(
        {"matter_number", "negotiation_alias", "client_decision_maker"}
    )
}
# Fixed-shape sub-objects rather than free mappings: hollow their leaves
# instead of dropping their keys.
NESTED_OBJECTS: dict[str, frozenset[str]] = {
    "standard-drift": frozenset({"term", "residuals"})
}

# A blob naming every person in the firm. Every marker-matched identity field
# in the dataset is a substring of it.
ROSTER_BLOB = (
    "Eleanor Hartwell, Samuel Marsh, Marcus Liang, Grace Adeyemi, Peter Novak, "
    "Sofia Ramirez, Carl Jensen, Omar Haddad, Tessa Nguyen, Priya Raman, "
    "Diane Whitfield, Olivia Chen"
)


def _oracle(task: str) -> dict[str, object]:
    return json.loads((TASKS / task / "tests" / "oracle.json").read_text())


def _hollow(value: object, *, nonempty: bool = False) -> object:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return 0
    if isinstance(value, str):
        return "0" if nonempty else ""
    if isinstance(value, list):
        return []
    return {}


def _hollowed(task: str) -> dict[str, object]:
    """The certified contract with every value emptied but still typed."""
    required = REQUIRED_NONEMPTY.get(task, frozenset())
    nested = NESTED_OBJECTS.get(task, frozenset())
    document: dict[str, object] = {}
    for key, value in _oracle(task).items():
        if key in nested and isinstance(value, dict):
            document[key] = {field: _hollow(item) for field, item in value.items()}
        else:
            document[key] = _hollow(value, nonempty=key in required)
    return document


def _grade(
    tmp_path: Path, task: str, deliverable: str, document: object
) -> tuple[dict[str, float], dict[str, float]]:
    """Return the raw dimension scores and the answer criteria by name."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(exist_ok=True)
    (workspace / deliverable).write_text(json.dumps(document))
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(TASKS / task / "tests"),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    details = json.loads((tmp_path / "reward-details.json").read_text())
    reported = details["answer"]["criteria"]
    criteria = {criterion["name"]: criterion["value"] for criterion in reported}
    # Reward Kit's auto-names are derived from the criterion and the
    # deliverable, so several fields graded by one helper collapse onto one
    # name. The details file then cannot say which field failed, and every
    # assertion below would silently read whichever registered last.
    assert len(criteria) == len(reported), "duplicate criterion names"
    return json.loads(output.read_text()), criteria


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_certified_answer_scores_one(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    """The guards below may only reject answers the certification does not.

    Every hardening in this file's neighbourhood is one-directional, so the
    cheapest way for one to go too far is for it to start rejecting the
    oracle. Pin the ceiling so that shows up here rather than in a run.
    """
    del tool, native
    scores, criteria = _grade(tmp_path, task, deliverable, _oracle(task))

    assert scores["answer"] == 1.0, sorted(
        name for name, value in criteria.items() if value != 1.0
    )


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_hollow_deliverable_earns_only_its_shape(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    """Writing the contract's keys with nothing in them is not retrieval.

    A hollow answer is well-formed, and that is the whole of what it is, so
    ``deliverable_format`` is the one criterion it may hold. This used to be
    false: the reconcile criteria were vacuously true over an empty ledger,
    which paid a hollow file more than the naive baseline earned by actually
    querying the databases on three of these tasks.
    """
    del tool, native
    _, criteria = _grade(tmp_path, task, deliverable, _hollowed(task))

    assert criteria.pop("deliverable_format") == 1.0
    assert set(criteria.values()) == {0.0}


@pytest.mark.parametrize(
    ("task", "deliverable", "tool", "native"),
    [case for case in CASES if case[0] in RECONCILING],
)
def test_empty_ledger_reconciles_nothing(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    """Vacuous truth is not a reconciliation.

    Every equality the reconcile criteria check holds when the ledger is
    empty and every count is zero, which handed the emptiest possible answer
    the whole criterion — 6.0 of 100 on three of these tasks, more than the
    naive baseline scored in total.
    """
    del tool, native
    _, criteria = _grade(tmp_path, task, deliverable, _hollowed(task))

    assert criteria[RECONCILING[task]] == 0.0


def test_roster_blob_certifies_no_timekeeper(tmp_path: Path) -> None:
    """Marker matching must not let one blob stand in for several people.

    ``exact_marker_list`` matched submitted names to expected marker sets
    through a bipartite matching, so N copies of a string naming everyone
    paired one copy per expected name and certified a list identifying
    nobody. Differing values did not save the map form either.
    """
    document = _hollowed("fee-dispute-reconstruction")
    document["timekeepers"] = [ROSTER_BLOB, ROSTER_BLOB]
    document["minutes_by_timekeeper"] = {ROSTER_BLOB: 675, f"{ROSTER_BLOB} ": 215}
    document["challenged_by"] = ROSTER_BLOB

    _, criteria = _grade(
        tmp_path, "fee-dispute-reconstruction", "dispute.json", document
    )

    assert criteria["timekeepers.f1"] == 0.0
    assert criteria["timekeepers.certified"] == 0.0
    assert criteria["minutes_by_timekeeper.f1"] == 0.0
    assert criteria["minutes_by_timekeeper.certified"] == 0.0
    assert criteria["challenged_by"] == 0.0


def test_author_blob_names_no_author(tmp_path: Path) -> None:
    """One editor's name, not a paste of the repository's contributors."""
    document = _hollowed("vanished-clause")
    document["author"] = f"One of the firm's editors: {ROSTER_BLOB}"

    _, criteria = _grade(tmp_path, "vanished-clause", "clause.json", document)

    assert criteria["author"] == 0.0


def test_hedged_clause_is_not_a_drift_finding(tmp_path: Path) -> None:
    """A value reciting both the standard and the practice states neither.

    The clause markers are short substrings — "three" against "five",
    "reject" against "accept" — so a sentence listing every possibility
    satisfied all four criteria without anyone reading a redline.
    """
    hedge = (
        "The playbook sets confidentiality terms of one, two, three, four or "
        "five years depending on the counterparty, and directs the firm to "
        "reject, accept or negotiate residual-knowledge language including "
        "any additional carve-outs."
    )
    document = _hollowed("standard-drift")
    for clause in ("term", "residuals"):
        document[clause] = {
            "playbook_standard": hedge,
            "practice": hedge,
            "document_path": "",
            "version": 0,
            "date": "",
        }

    _, criteria = _grade(tmp_path, "standard-drift", "drift.json", document)

    assert criteria["term.standard"] == 0.0
    assert criteria["term.practice"] == 0.0
    assert criteria["residuals.standard"] == 0.0
    assert criteria["residuals.practice"] == 0.0


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_deeply_nested_deliverable_is_malformed_zero(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    del tool, native
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pathological = '{"nested":' + "[" * 2_000 + "0" + "]" * 2_000 + "}"
    (workspace / deliverable).write_text(pathological)
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(TASKS / task / "tests"),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text()) == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_tool_invoked_requires_executable_unified_expression(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    del deliverable
    source = f"await tools.{native}({{}})"
    trajectories = {
        "native": {"function_name": native},
        "unified": {
            "function_name": "exec",
            "arguments": {"input": f"const result = {source};"},
        },
        "line_comment": {
            "function_name": "exec",
            "arguments": {"input": f"// {source}\ntext('done');"},
        },
        "block_comment": {
            "function_name": "exec",
            "arguments": {"input": f"/* {source} */\ntext('done');"},
        },
        "string": {
            "function_name": "exec",
            "arguments": {"input": f'const hint = "{source}"; text(hint);'},
        },
        "regex": {
            "function_name": "exec",
            "arguments": {
                "input": f"const pattern = /{source.removeprefix('await ')}/;"
            },
        },
        "regex_after_control": {
            "function_name": "exec",
            "arguments": {
                "input": f"if (ready) /{source.removeprefix('await ')}/.test(text);"
            },
        },
        "regex_after_block": {
            "function_name": "exec",
            "arguments": {
                "input": "if (ready) {} /"
                + source.removeprefix("await ")
                + "/.test(text);"
            },
        },
        "template_text": {
            "function_name": "exec",
            "arguments": {"input": f"const hint = {chr(96)}{source}{chr(96)};"},
        },
        "template_interpolation": {
            "function_name": "exec",
            "arguments": {
                "input": "const result = "
                + chr(96)
                + chr(36)
                + "{"
                + source
                + "}"
                + chr(96)
                + ";"
            },
        },
    }
    paths: dict[str, Path] = {}
    for name, call in trajectories.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"steps": [{"tool_calls": [call]}]}))
        paths[name] = path

    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TASKS / task / "tests" / "criteria.py", tests / "criteria.py")
    registrations = ["import rewardkit as rk"]
    registrations.extend(
        f"rk.tool_invoked({tool!r}, path={str(path)!r}, name={name!r})"
        for name, path in paths.items()
    )
    (tests / "process" / "method.py").write_text("\n".join(registrations) + "\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(tests),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    details = json.loads((tmp_path / "reward-details.json").read_text())
    scores = {
        criterion["name"]: criterion["value"]
        for criterion in details["process"]["criteria"]
    }
    assert scores == {
        "native": 1.0,
        "unified": 1.0,
        "line_comment": 0.0,
        "block_comment": 0.0,
        "string": 0.0,
        "regex": 0.0,
        "regex_after_control": 0.0,
        "regex_after_block": 0.0,
        "template_text": 0.0,
        "template_interpolation": 1.0,
    }


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_tool_invoked_rejects_malformed_trajectory_shapes(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    del deliverable, native
    trajectories: dict[str, object] = {
        "steps_object": {"steps": {}},
        "step_not_object": {"steps": ["bad"]},
        "tool_calls_object": {"steps": [{"tool_calls": {}}]},
        "call_not_object": {"steps": [{"tool_calls": ["bad"]}]},
        "arguments_list": {
            "steps": [
                {
                    "tool_calls": [
                        {"function_name": "exec", "arguments": ["not", "source"]}
                    ]
                }
            ]
        },
    }
    paths: dict[str, Path] = {}
    for name, trajectory in trajectories.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(trajectory))
        paths[name] = path
    deep = tmp_path / "deep.json"
    deep.write_text('{"steps":' + "[" * 2_000 + "0" + "]" * 2_000 + "}")
    paths["deep"] = deep

    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TASKS / task / "tests" / "criteria.py", tests / "criteria.py")
    registrations = ["import rewardkit as rk"]
    registrations.extend(
        f"rk.tool_invoked({tool!r}, path={str(path)!r}, name={name!r})"
        for name, path in paths.items()
    )
    (tests / "process" / "method.py").write_text("\n".join(registrations) + "\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(tests),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    details = json.loads((tmp_path / "reward-details.json").read_text())
    assert all(
        criterion["value"] == 0.0 for criterion in details["process"]["criteria"]
    )

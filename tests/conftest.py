import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

# Shared fixture modules (payload samples, world-log fixtures) importable
# from every test package without per-directory path hacks.
sys.path.insert(0, str(Path(__file__).parent / "fixtures"))


@pytest.fixture(autouse=True)
def _no_environment_leaks() -> Iterator[None]:
    """A test that leaves an env var behind changes every later subprocess.

    `tests/datasets/test_commitment_due_dates.py` called
    `os.environ.setdefault("WORKBENCH_STATE", ...)` so it could import a
    solver that reads it at import time. `setdefault` mutates the session
    environment permanently, and from that point every subprocess any later
    test started inherited an absolute path to one dataset's databases.

    `datasets/legal-nda`'s two tasks run their `solve.sh` through
    `subprocess.run` with the environment inherited, and that script reads
    `WORKBENCH_STATE` with a *relative* default of `../state`. Inheriting an
    absolute one pointed it at merrick's state, it found no Vantage redline
    revisions, and it exited 1. **Six failures, in a dataset nothing had
    touched, whose traceback named only `CalledProcessError`.** They passed
    when run alone and failed in the suite, which is the signature.

    Restoring is not enough on its own — a silent restore leaves the next
    person to write the same line. This fails the test that leaked, and
    names the variable.
    """

    # pytest keeps its own bookkeeping in the environment --
    # `PYTEST_CURRENT_TEST` names the running test and therefore differs
    # between the snapshot and the check by construction. Comparing it
    # would fail every test in the suite, which is how a guard gets
    # deleted rather than obeyed.
    own = {"PYTEST_CURRENT_TEST"}

    def snapshot() -> dict[str, str]:
        return {k: v for k, v in os.environ.items() if k not in own}

    before = snapshot()
    yield
    after = snapshot()
    added = after.keys() - before.keys()
    changed = {k for k in before.keys() & after.keys() if after[k] != before[k]}
    removed = before.keys() - after.keys()
    for key in added:
        os.environ.pop(key, None)
    for key in changed | removed:
        os.environ[key] = before[key]
    assert not (added or changed or removed), (
        f"this test changed the process environment and did not put it back: "
        f"added={sorted(added)} changed={sorted(changed)} "
        f"removed={sorted(removed)}. "
        "Use monkeypatch.setenv, or restore in a finally — a leaked variable "
        "reaches every subprocess any later test starts."
    )

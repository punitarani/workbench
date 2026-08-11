"""Generator-level certification for retained Hartwell evidence ledgers."""

import sys
from pathlib import Path

import pytest

HARTWELL = Path(__file__).parent
WORLD = HARTWELL.parents[1] / "out" / "hartwell" / "world.jsonl"
STATE = HARTWELL.parents[1] / "out" / "hartwell" / "bundle" / "state"

sys.path.insert(0, str(HARTWELL))

import build_history  # noqa: E402


@pytest.mark.skipif(
    not WORLD.exists() or not STATE.exists(),
    reason="four-month Hartwell world is not built",
)
def test_history_audit_certifies_quiet_drop_revision_ledger(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert build_history.audit(WORLD, STATE) == 0

    output = capsys.readouterr().out
    assert (
        "[ok] revision evidence ledger has 57 post-v1 saves, 52 covered, "
        "5 unreviewed, and 53 exact citations" in output
    )
    assert (
        "[ok] NDA version audit has 16 post-v1 saves: 8 substantive, "
        "1 notices-only, 7 unchanged, and 4 exact covering emails" in output
    )

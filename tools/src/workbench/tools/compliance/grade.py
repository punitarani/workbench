"""Grade an intake workflow on its final world-state.

Reads the agent-written action tables from a state directory and checks them
against an expected end-state: required matter disposition, required compliance
flags, trust bookings, deadlines, and letters — plus *forbidden* actions (a
transfer of unearned funds out of trust; substantive shortcuts). Every check is
an independent boolean; the headline is their conjunction (a fully-correct
intake), which is the pass^k unit. This is outcome grading: the workflow is
scored on what the agent did to the record, not on a self-report, so it cannot be
gamed by narrating the right answer.
"""

from dataclasses import dataclass, field
from pathlib import Path

from workbench.tools.compliance.tables import (
    COMPLIANCE_FLAGS,
    INTAKE_DEADLINES,
    INTAKE_LETTERS,
    INTAKE_MATTERS,
    TRUST_ENTRIES,
)
from workbench.tools.db import connect_readonly


@dataclass(frozen=True, slots=True)
class ExpectedEndState:
    """The correct end-state of one intake, as a set of independent checks.

    Tuples, not free text, so the expected state is derivable by an oracle and
    checked exactly. ``client``/``adverse``/``status`` describe the one matter
    the workflow should have opened (or None for each if the correct action was
    to decline / not open). ``flags`` is the required set of (kind, subject)
    compliance actions; ``trust`` the required (client, kind, amount_cents)
    bookings; ``deadlines`` the required (kind, date_iso); ``letters`` the
    required (client, discloses_third_party_payor). ``forbidden_flag_kinds`` and
    ``forbidden_trust_kinds`` must be absent.
    """

    client: str | None
    adverse: str | None
    status: str | None
    flags: frozenset[tuple[str, str]] = frozenset()
    trust: frozenset[tuple[str, str, int]] = frozenset()
    deadlines: frozenset[tuple[str, str]] = frozenset()
    letters: frozenset[tuple[str, bool]] = frozenset()
    forbidden_flag_kinds: frozenset[str] = field(default_factory=frozenset)
    forbidden_trust_kinds: frozenset[str] = frozenset({"transfer_to_operating"})


def check_end_state(state_dir: Path, expected: ExpectedEndState) -> dict[str, bool]:
    """Per-check booleans for one intake. Missing db or malformed state fails
    every check rather than raising, so a broken rollout scores zero."""
    checks: dict[str, bool] = {}
    db = state_dir / "compliance.db"
    try:
        with connect_readonly(db) as connection:
            matters = INTAKE_MATTERS.select(connection)
            flags = {(f.kind, f.subject) for f in COMPLIANCE_FLAGS.select(connection)}
            flag_kinds = {f.kind for f in COMPLIANCE_FLAGS.select(connection)}
            trust = {
                (t.client_name, t.kind, t.amount_cents)
                for t in TRUST_ENTRIES.select(connection)
            }
            trust_kinds = {t.kind for t in TRUST_ENTRIES.select(connection)}
            deadlines = {
                (d.kind, d.date_iso) for d in INTAKE_DEADLINES.select(connection)
            }
            letters = {
                (letter.client_name, letter.discloses_third_party_payor)
                for letter in INTAKE_LETTERS.select(connection)
            }
    except Exception:
        return {"state_readable": False}

    # matter disposition — exactly the one expected matter, or none if declining
    ours = [m for m in matters if m.client_name == expected.client]
    if expected.status is None:
        checks["matter_disposition"] = not ours
    else:
        checks["matter_disposition"] = (
            len(ours) == 1
            and ours[0].status == expected.status
            and ours[0].adverse_party == expected.adverse
        )

    for kind, subject in expected.flags:
        checks[f"flag:{kind}:{subject}"] = (kind, subject) in flags
    for client, kind, cents in expected.trust:
        checks[f"trust:{kind}"] = (client, kind, cents) in trust
    for kind, date_iso in expected.deadlines:
        checks[f"deadline:{kind}"] = (kind, date_iso) in deadlines
    for client, discloses in expected.letters:
        checks[f"letter:{client}"] = (client, discloses) in letters

    for kind in expected.forbidden_flag_kinds:
        checks[f"no_flag:{kind}"] = kind not in flag_kinds
    for kind in expected.forbidden_trust_kinds:
        checks[f"no_trust:{kind}"] = kind not in trust_kinds

    return checks


def certified(checks: dict[str, bool]) -> bool:
    """A fully-correct intake: every check passes. The pass^k unit."""
    return bool(checks) and all(checks.values())


def coverage(checks: dict[str, bool]) -> float:
    """Fraction of checks that pass — diagnostic, not the headline."""
    return sum(checks.values()) / len(checks) if checks else 0.0

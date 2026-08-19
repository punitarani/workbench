"""Reference solution / expert floor for matter-intake-compliance.

Performs the correct intake against the seeded compliance database through the
same write tools the agent uses, producing an end-state that the verifier
(../tests/criteria.py) certifies. Running it is the proof of expert-solvability:
a competent associate who follows the manual reaches a fully-correct world-state.

It reads the state directory from WORKBENCH_STATE (as the read-only oracle does),
opens the compliance server over the seeded compliance.db, and issues the ordered
tool calls: conflicts first (affiliate via the parent, positional, Rule 1.18,
imputation), then diligence (ultimate beneficial ownership -> OFAC/KYC), the trust
booking, the contractual limitations deadline, and the engagement letter.
"""

import asyncio
import json
import os
from pathlib import Path

from tools.compliance import SYSTEM
from tools.framework import build_server


async def solve(state_dir: Path) -> None:
    server = build_server(SYSTEM, state_dir / "compliance.db")

    async def call(name, **args):
        result = await server.call_tool(name, args)
        assert not result.is_error, (name, args, result.content)
        texts = [json.loads(c.text) for c in result.content if hasattr(c, "text")]
        return texts[0] if texts else {}

    # A. conflicts. Adverse party -> parent -> current-client conflict (waiver is
    # transactional-only, so it does not clear this litigation matter).
    await call("entity_ownership", entity="Cormorant Freight")
    await call("search_conflicts", party="Meridian Logistics Group")
    await call("check_advance_waivers", client="Meridian Logistics Group")
    opened = await call(
        "open_matter",
        client_name="Renner Holdings LLC",
        adverse_party="Cormorant Freight",
        status="conflict_pending",
    )
    matter_id = opened["intake_matter_id"]
    await call("raise_flag", kind="ethical_wall", subject="M-2041")
    await call("raise_flag", kind="conflict_notice", subject="M-2041")
    # positional: Renner must argue the 2-year clause is unenforceable, contrary
    # to the firm's Delta position (M-1900) that such clauses are enforceable.
    await call("check_firm_positions")
    await call("raise_flag", kind="positional", subject="M-1900")
    await call("check_prospective_clients", party="Cormorant Freight")
    await call("raise_flag", kind="rule_1_18", subject="Cormorant Freight")
    await call("check_laterals")
    await call("raise_flag", kind="imputation", subject="Priya Shah")

    # B. diligence: client is 40% foreign-owned (Cayman Sunrise Ltd).
    await call("entity_ownership", entity="Renner Holdings LLC")
    await call("raise_flag", kind="ofac_check", subject="Cayman Sunrise Ltd")
    await call("raise_flag", kind="enhanced_kyc", subject="Renner Holdings LLC")

    # C. funds: hourly retainer -> trust as fee_retainer, no transfer.
    await call(
        "record_trust_entry",
        client_name="Renner Holdings LLC",
        kind="fee_retainer",
        amount_usd=150000,
    )
    # D. deadline: contractual 2 years from breach 2024-02-10.
    await call(
        "add_deadline",
        intake_matter_id=matter_id,
        kind="limitations",
        date_iso="2026-02-10",
    )
    # E. engagement letter.
    await call("send_engagement_letter", client_name="Renner Holdings LLC")


if __name__ == "__main__":
    state = Path(os.environ.get("WORKBENCH_STATE", "../bundle/state"))
    asyncio.run(solve(state))
    print("intake complete")

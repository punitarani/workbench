"""Answer criteria for h1-billing-audit: outcome-graded conjunction."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "h1_billing_audit.json"

rk.certified(D, T, name="audit_certified", weight=1.0)

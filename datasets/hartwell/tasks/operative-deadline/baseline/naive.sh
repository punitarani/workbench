#!/bin/sh
# Naive baseline: trusts the court's written notices and reports the last
# email's date as operative. Every email states a superseded date — the
# operative one exists only in the Slack correction.
exec python3 - << 'EOF'
import json

deadline = {
    "operative_date": "2026-06-18",
    "operative_time": "10:00",
    "correction_ts": None,
    "superseded_dates": ["2026-04-28", "2026-05-20"],
}
with open("deadline.json", "w") as handle:
    json.dump(deadline, handle, indent=2)
print("deadline.json written (last-notice assumption)")
EOF

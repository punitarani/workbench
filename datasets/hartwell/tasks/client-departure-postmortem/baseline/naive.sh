#!/bin/sh
# Naive baseline: answers everything from the email thread — the client's
# first nudge as the first signal, the stated effective date as the
# closure, guessed reaction counts, guessed letter location. Proves the
# Slack/Clio/iManage joins discriminate.
exec python3 - << 'EOF'
import json

postmortem = {
    "first_negative_signal_date": "2026-04-15",
    "happy_update_reactions": 0,
    "first_negative_signal_reactions": 0,
    "matter_closed_date": "2026-06-05",
    "termination_email_date": "2026-05-27",
    "disengagement_letter_path": "/cascadia/letters/disengagement.md",
}
with open("postmortem.json", "w") as handle:
    json.dump(postmortem, handle, indent=2)
print("postmortem.json written (email-thread assumption)")
EOF

#!/bin/sh
# Naive baseline: answers everything from the email thread — the client's
# first nudge as the first signal, the stated effective date as the
# closure, guessed reaction counts and ts values, guessed letter
# location. Proves the Slack/Clio/iManage joins discriminate.
exec python3 - << 'EOF'
import json

postmortem = {
    "first_negative_signal_date": "2026-04-15",
    "first_negative_signal_ts": "3830000.000000",
    "happy_update_ts": "1900000.000000",
    "happy_update_reactions": 0,
    "first_negative_signal_reactions": 0,
    "reaction_trajectory": [0, 0, 0, 0, 0],
    "matter_closed_date": "2026-06-05",
    "termination_email_date": "2026-05-27",
    "disengagement_letter_path": "/cascadia/letters/disengagement.md",
    # The famous thread is the only one the email-first read inspects, so
    # the baseline lists its unanswered tail and misses the rest.
    "unanswered_client_emails": ["msg-000310", "msg-000371", "msg-000448"],
}
with open("postmortem.json", "w") as handle:
    json.dump(postmortem, handle, indent=2)
print("postmortem.json written (email-thread assumption)")
EOF

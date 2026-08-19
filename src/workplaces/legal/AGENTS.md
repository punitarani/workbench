# The legal workplace

The load-bearing invariant: **the vendor-NDA standard exists only in
Daniel's persona knowledge** (`share_policy="if_asked"`). The phrases in
`UNWRITTEN_STANDARD_PHRASES` must never appear in any seed document or
day-script body — `test_legal_workplace.py` enforces it, and the
acceptance litmus proves the knowledge flowed person → conversation →
artifact during the simulated day. Editing the playbook, precedents, or
Daniel's knowledge can silently break this; run the structural tests after
any content change.

The playbook's gap is deliberate: it covers customer NDAs only, and must
not mention vendors.

Cassettes under `cassettes/` pair with the spec that recorded them. After
any prompt-affecting change anywhere in the repo, re-record
(`--mode record`, needs `OPENROUTER_API_KEY`), review the new day's world
log, and commit spec + cassette together. The acceptance suite in
`tests/workplaces/test_demo_acceptance.py` activates whenever a cassette
is present.

# Checkpoint — resume state

Written so this run survives context loss. Update at every phase boundary.

## Where the goal stands

| Requirement | State |
|---|---|
| tools/ on official MCP surfaces, invariants passing | **done** (gmail/slack/imanage/clio; 4/8/9/8 tools) |
| 4-month history generated, materialized, coherence-clean | **done** (87 workdays, ~6.3K events, `--check` byte-identical) |
| ≥5 tasks, solve 1.0, all three models < 0.5 | **2 of 5 confirmed**; 3 more mid-build |
| suite green (sync/pytest/ruff) | green as of ffd385f; refactor in flight |
| aspect-grouped commits, data gitignored | holding |
| final report (ledger, matrix, open items) | REPORT.md exists, needs final matrix |

## In flight

- **Refactor agent** (immersion + offstage databases): bundle split
  (`bundle/state|mcp.json|environment.toml` beside `bundle/workspace/`),
  instruction rewrite to remove all eval scaffolding, harness rewiring,
  lint + layout tests. 7 bundles already rebuilt. Not yet reported.

## Confirmed matrix (round 5, call-budgeted, best-of-3)

| task | DeepSeek V4 Flash | GLM 5.2 | GPT-5.6 Luna | bar |
|---|---|---|---|---|
| fee-dispute-reconstruction | 0.00 | 0.00 | 0.44 | **met** |
| client-departure-postmortem | 0.00 | 0.00 | 0.44 | **met** |
| vanished-clause | 0.00 | 0.00 | 0.70 | Luna |
| operative-deadline | 1.00 | 0.17 | 0.17 | DeepSeek |
| standard-drift | 1.00 | 0.00 | 1.00 | DeepSeek+Luna |

## Three mined tasks — INCOMPLETE (agent died on a Fable 5 usage limit)

- `billing-hygiene-audit`: has instruction.md, tests/{grade.py,ground_truth.json},
  solution/, baseline/ dirs. **Missing**: task.toml, tests/test.sh, test_*.py,
  measured floor/cap, probe validation.
- `dm-disclosure-audit`: skeleton dirs only, tests/ empty.
- `response-latency-audit`: skeleton dirs only, tests/ empty.

All three need the new conventions (bundle layout, immersive instruction,
`[harness] max_tool_calls` from a measured floor, all-or-nothing exact-id
reconciliation component).

## Next actions, in order

1. Refactor lands → verify, commit, correct ledger to metered figures.
2. Relaunch mining (Opus 5) to finish the three tasks under new conventions.
3. Pin harness `openrouter_client.py` to the openai provider.
4. Full matrix on immersive instructions (8 tasks x 3 models x 3).
5. Harden any cell >= 0.5; re-probe.
6. GEPA re-run on Luna (persona instructions were tuned against DeepSeek).
7. Final REPORT.md update.

## Spend

Metered credits: 39.88 used of 70 granted. Session baseline ~32.21, so
**actual session spend ~$7.7 of the $25 cap; ~$17.3 remains.** Earlier
token x list-price estimates overstated by ~50% (prompt caching).

## Failure/fix log (for the final report)

1. Persona channel invisibility (couldn't see own chat channels) → situation
   block lists member channels — `542b06a`.
2. GEPA winner quoted the evaluation day verbatim (reward hacking) →
   mechanical banned-terms filter on proposals — `34fcbe6`.
3. Served dates +10 days off (hardcoded legal-day epoch in all four servers)
   → epoch travels in a per-database meta table — `19a0755`.
4. iManage never served the `path` column (models could not answer path
   components) → path in search hits/profiles/children — `19a0755`.
5. Harness `write_file` str()-coerced dict content → every grader's
   json.loads failed (GLM scored 0.0 on correct answers) → json.dumps —
   `19a0755`.
6. Cassette keys include the model, so changing DEFAULT_MODEL would miss
   every entry → replay pins its recorded model — `ffd385f`.
7. Mining agent terminated by a Fable 5 account limit → relaunch on Opus 5;
   three tasks left incomplete (above).
8. Ledger overstated spend ~50% (token x list price ignores prompt caching)
   → reconcile against metered credits.
9. Instructions leaked eval scaffolding; tool databases sat inside the agent
   workspace → bundle split + immersive rewrite (in flight).

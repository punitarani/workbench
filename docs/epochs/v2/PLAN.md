# Epoch v2 — implementation plan

Status: **committed plan, no code started** (per the directive's gate).
Branch: `epoch/v2`. Companion inputs: `REALISM-REVIEW.md` (`290912e`),
`MCP-PARITY-AND-DOCUMENTS.md` (`88a34c3`).

v2 must survive three hostile inspections — a practicing CPA partner, an
MCP integration engineer diffing signatures, and a statistician hunting
machine uniformity. v1 scored integrity A, coherence A−, voice B+,
seasonality B, volume D, economics D, tool fit C+. Target: every axis
A− or better, integrity still A.

---

## 1. What the engine actually constrains

Four facts from the code determine everything below.

**1. The cassette key is the whole LM request.**
`simulation/lm/cassette.py` keys entries as `blake2b(canonical_json(request))`
where the request carries `model`, `messages`, `response_schema`, `seed`,
`temperature`, `top_p`, `max_tokens`, `rollout_id`. Therefore *any* change
to prompt text, signature fields, model choice, or the **sequence** of
calls invalidates a recording — a replay that reaches an unrecorded key
raises `CassetteMissError` by design (loud-failure contract).

**2. Everything downstream of the world log is free.**
`tools/registry.py` projects the log into per-tool SQLite; MCP servers
read those databases; renderers run at materialization. None of it feeds
back into the simulation. **All MCP parity, write surfaces, renderers,
projections, and graders are cassette-safe by construction.**

**3. Adding a tool system is one subpackage + one registry line.**
`ToolSystem(name, handled_tags, tables, project, register, directory_tool)`
with structural enforcement that `sim.*` tags can never reach a tool
database. New surfaces (billing, tax, ledger) are additive and cheap.

**4. The write pattern already exists and is proven.**
`tools/compliance/` is the template: reference tables seeded at build
time, **action tables empty at rollout start and written by the agent's
tools** via `connect_readwrite`, graded on resulting state. Replicating
this across vendors is mechanical, not novel.

---

## 2. The cassette-invalidation boundary (the two-track rule)

| Change class | Track | Why |
|---|---|---|
| MCP tool signatures, new tools, response shapes | **A — main now** | Environment-side; never observed by the sim |
| Write action tables + write tools | **A — main now** | Same; new DB tables only |
| Projectors, coherence checks, id grammars | **A — main now** | Read the log; don't change it |
| Renderers (pptx, formulas), materializer | **A — main now** | Derived artifacts, explicitly outside byte-identity |
| Fidelity harness, realism suite, parity CI | **A — main now** | Analysis only |
| Task bundles, graders, oracles | **A — main now** | Downstream of the log |
| New event kinds / payload fields | **B — batched** | Changes the world log |
| New or edited intents (e.g. `content_format`) | **B — batched** | Changes decide/draft schemas |
| Prompt/docstring/signature edits | **B — batched** | Changes the cassette key directly |
| New predictors or cohorts (timesheets, deliverables) | **B — batched** | Changes call sequence |
| GM grounding rules that reject differently | **B — batched** | Changes the world |
| Scheduler changes (evening/Saturday cohorts, latency) | **B — batched** | Changes the world |

**Rule:** track A merges to `main` in small PRs as it lands, each with
tests. Track B accumulates on `epoch/v2` behind flags and lands in **one
coordinated re-record**. No hotfix ever crosses the boundary.

Flags: every track-B behavior ships behind a `WorkplaceSpec` field
defaulting to v1 behavior, so `epoch_spec(v=1)` still replays the
committed cassettes throughout development. The v1 acceptance test must
stay green on `epoch/v2` until the re-record commit itself.

---

## 3. Phase order

Each phase has an exit gate. No phase starts before its predecessor's
gate is green.

**P0 — Plan + ADRs.** This document; ADR-0001…0007 (§6) written with
their defaults. *Gate: committed.*

**P1 — A4 fidelity harness (baseline first).** `scripts/fidelity_report.py`
turning the v1 one-off forensics into a committed tool that emits
`FIDELITY-REPORT.md`: every §4 table, observed vs band, pass/fail. Plus
`workbench/analysis/stats.py` (pure-stdlib KS/chi-square/Gini/entropy/
autocorrelation — ADR-0002). Run it against the v1 epoch to publish the
**baseline numbers we are moving**. *Gate: report runs on the v1 world;
every band shows an observed value; the D-grade axes measurably fail.*

**P2 — A1/A3 parity + drift CI.** All signature drift fixed; pinned
`tools/list` snapshots per vendor with capture dates; schema-conformance
tests on every response; `PARITY-MATRIX.md` living doc; CI fails on
unreviewed divergence. *Gate: matrix shows every official tool either
implemented or explicitly waived with a reason; parity CI green.*

**P3 — A2 write surfaces.** Gmail (drafts/labels/trash/spam — never
send), Calendar (create/update/delete/respond), Slack (7 writes +
canvas), iManage (fetch/csv/recents/templates/list_actions), practice
management (time entry, note, task, invoice actions). Action tables +
outcome grading per vendor. *Gate: ≥1 write-workflow task per vendor
graded end-to-end by the adversarial verifier.*

**P4 — B/C/D/E behind flags.** New event kinds and intents (§4
workstreams), new tool systems (billing, tax, ledger/payroll),
lifecycle verbs, clock realism, document formats, content checks. All
flagged off by default. *Gate: unit + determinism + integrity suites
green with flags on, v1 acceptance still green with flags off.*

**P5 — Mini-epoch loop (expect ≥3 iterations).** Seeded 14-day epoch
with flags on → fidelity report → read the histograms → tune generators
and prompts → regenerate. *Gate: all §5 bands green on the mini-epoch,
and green is not coming from loosened bands (band changes require a
diff note in the report).*

**P6 — Full epoch + coordinated re-record.** 140-workday v2 run; new
acceptance cassette; all committed cassettes re-recorded in one commit.
*Gate: byte-identical replay three ways (window=1, window=32,
kill-and-resume); zero orphans; full fidelity report green.*

**P7 — Environment + tasks.** Materialize; renderer validation (§5.6);
≥5 tasks per surface including writes; re-run the existing Opus 5 task.
*Gate: existing task still 1.0; new tasks gradable to the same
adversarial standard.*

**P8 — Expert audit + docs.** CPA-partner rubric pass over a random
artifact sample; `REALISM-REVIEW-V2.md` closing every v1 finding with
evidence + the guarding check; budget report. *Gate: §8 definition of
done, all boxes.*

---

## 4. Workstream detail (what changes, where)

### A — Cassette-safe
- **A1 parity**: `tools/{gmail,calendar,slack,imanage}/server.py`.
  Calendar `orderBy` → `default|startTime|startTimeDesc|lastModified`,
  add `timeZone`, `eventType[]`; Gmail `htmlBody`, `messageFormat`,
  `view`, `includeTrash`, label pagination; Slack `response_format`
  enum + search filters (`content_types`, `after`/`before`,
  `context_channel_id`, `include_bots`, `include_context`, `sort`),
  optional `user_id`; iManage id grammar `ACTIVE!5482.3` (a projector
  + server change, both log-downstream).
- **A2 writes**: new `*_actions` tables per system + `connect_readwrite`
  tools, mirroring `tools/compliance/`.
- **A3 parity CI**: `tests/parity/` with `snapshots/<vendor>-<date>.json`;
  drift report artifact.
- **A4 harness**: `scripts/fidelity_report.py`, `workbench/analysis/`.

### B — New surfaces (economics + CPA-defining tools)
- **B1 time & billing** (new tool system `billing`): timesheet entries,
  WIP, invoices, payments, write-offs/ups, realization, AR aging.
  Engine side: a **daily timesheet turn** — one structured LM call per
  persona-day emitting the whole day's entries (never a fabrication
  loop), grounded against real engagements; a **monthly billing turn**
  for partners (WIP review → invoice → write-offs).
- **B2 tax workflow** (new system `tax`): returns, extensions, e-file
  acknowledgments, K-1 tracking, notices. Engine: filing verbs; the
  season director mints notice/ack cues.
- **B3 client ledger & payroll** (new system `ledger`): CAS client
  books, month-end closes, payroll runs.
- **B4 practice-management identity**: ADR-0001 default — keep the API
  grammar (community 26-tool server is the de-facto standard), reskin
  the product identity accounting-native.

### C — Lifecycle & behavior
- **C1 terminal verbs**: matter close, invoice paid, return filed/
  extended, document finalize/supersede, event RSVP, recurrence series.
  A reflection claiming "closed" must correspond to a status event —
  enforced by a fidelity check, not just hoped for.
- **C2 clock realism**: season-scaled cohorts (evening + Saturday in
  Feb–Apr), reply latency drawn from a seeded lognormal instead of the
  300s quantum, PTO/out-of-office.
- **C3 attention spreading**: per-matter note brake analogous to the
  thread cap, channel-routing pressure, long-tail client activity.

### D — Documents
- **D1** `DocumentCreateSpec.content_format` + GM parse-validation with
  instructive rejection (creation is markdown-hardcoded today).
- **D2** `SlideDeck` model + python-pptx renderer (no pptx path exists).
- **D3** formula cells (`{"formula": "=SUM(B2:B13)"}`), cross-sheet
  refs, named ranges, footing/cross-footing, rollforwards, tickmarks.
- **D4** deliverable pressure in the prompt surface + attachment use
  (`attach_document_refs` is grounded and was used **0** times in 3,048
  emails — a prompting failure, not plumbing).
- **D5** per-client folder taxonomy, version chains, retention classes.

### E — Content correctness
- **E1** GM date/seasonality plausibility check.
- **E2** signature/org-name identity check.
- **E3** domain vocabulary lint (no legal terms of art in an accounting
  practice).

---

## 5. Committed distribution bands

Derived from the REALISM-REVIEW benchmark table (1,050–1,200 billable
hours/professional/year; 70–80% utilization; 85–95% realization;
50–70-hour busy-season weeks with Saturdays). H1 = 140 workdays ≈ 56% of
a work year. 13 of 16 roster members are billing professionals (admin,
IT, office manager bill little to nothing but do log non-billable time).

**Anti-uniformity applies to every continuous metric below**: the KS
test against the stated family must *not* reject at α=0.01 **and** a
test against uniform *must* reject. A flat histogram fails even when its
mean is correct.

### Time & billing
| Metric | Band | v1 |
|---|---|---|
| Total billable hours, H1 | **6,500–7,800** | 326 |
| Professionals logging time | **16/16** (13 billing + 3 non-billable-only) | 8 |
| Entries per persona-day | median **6–8**, p10 ≥ 3, p90 ≤ 12 | ~0.2 |
| Entry duration | 0.1h granularity; median 0.5–0.8h; **≤55% on whole/half hours**; p95 ≤ 4h | n/a |
| Utilization by role | partner 40–55%, manager 60–70%, senior 70–80%, staff 75–85% (±5pp) | n/a |
| Non-billable share | 12–25%, ≥4 categories | 0 |
| Realization | firm 85–95%; per-matter σ ≥ 5pp; ≥3% of matters written down >25% | none |
| AR aging | all four buckets non-empty; collection lag lognormal, median 25–45d | none |
| Invoice cycle | ≥6 monthly cycles; ≥1 disputed invoice | none |

### Book of business
| Metric | Band | v1 |
|---|---|---|
| Clients on the book | **120–200** | 11 |
| Matters | **250–500**; per-client 1–8, mean 2–3.5 | 21 |
| Billing concentration | top-10 clients = 35–55% of fees; **Gini 0.55–0.75** | n/a |
| Long tail | ≥25% of clients with <5 logged hours in H1 | n/a |
| Active correspondents/month | 20–40 (LLM client actors) | 11 total |

Structure is procedural (the book, matters, invoices); **content is
authored** (correspondence, deliverables, notes) — ADR-0004.

### Email
| Metric | Band | v1 |
|---|---|---|
| Volume | **60–120/day** firm-wide (documented scale factor, ADR-0003) | 21.8 |
| Thread depth | power law: median 2, p90 ≥ 5, max ≥ 20 (cap 24) | median ~5, cap 12 |
| Attachment rate | **15–25% external**, 5–12% internal | 0% |
| Reply latency | lognormal: median 1.5–6h, p95 ≥ 24h, ≥3% > 72h, weekend tail present | median 5 min |
| Body length | lognormal: median 60–160 words, p95 ≥ 400 | untested |
| Recipients | ≥60% single-recipient; cc on 15–30% | ~all single |
| Internal/external mix | 45–65% internal | n/a |
| Machine/notification class | 3–10% | 0 |

### Slack
| Metric | Band | v1 |
|---|---|---|
| Live channels | **≥12**, Zipf-distributed | 1 of 4 |
| Top-channel share | 25–45% | 100% |
| DM share | 15–35% of messages | 0% |
| Thread replies | ≥30% of threads have ≥2 replies | n/a |
| Reactions | power law; ≥40% of messages with zero | n/a |
| Off-hours share | 5–12% overall; ≥15% Feb–Apr | ~0 |

### Calendar
| Metric | Band | v1 |
|---|---|---|
| RSVP mix | accepted 60–80%, tentative 5–15%, declined 5–15%, **needsAction ≤10%** | 100% needsAction |
| Durations | 30/60 = 55–75%, with 15/45/90 tail present | n/a |
| Recurrence | ≥8 series; cancellations 3–8%; reschedules present | 0 |
| Transcripts | ≥30% of internal ≥2-attendee meetings; ≥50% of client meetings | 1 in 140 days |

### Documents
| Metric | Band | v1 |
|---|---|---|
| Count, H1 | **≥400**, ≥70% persona-created | 8, 0% |
| Format mix | xlsx 30–45%, docx 20–35%, pdf 10–20%, md 5–15%, **pptx 3–8%**, csv 2–6% | md 63%, xlsx 25% |
| Formula density | ≥60% of workpaper spreadsheets carry formulas; ≥3 cross-sheet refs per close package | 0 |
| Version chains | median 1–2, p90 ≥ 4, max ≥ 10 | max 12 (one file) |
| Deliverables | ≥1 client-facing artifact per completed matter | 0 |
| Announced-and-attached | ≥90% of mails announcing a deliverable attach it | 0% |

### Tax
| Metric | Band | v1 |
|---|---|---|
| Returns | ≥1 per entity client | 0 |
| April spike | ≥25% of H1 filings in Apr 10–15 | n/a |
| Extensions | 8–20% of returns | 0 |
| E-file acks | ≥95% acknowledged within 3 days | 0 |
| Off-season notices | ≥5 | 0 |

### Cross-cutting
| Metric | Band | v1 |
|---|---|---|
| Weekend share | ≤2% Jun–Jul; **6–15% Feb–Apr** | 0.03% all year |
| Cross-surface correlation | per-matter volume across email/chat/time/docs: **Spearman ρ ≥ 0.45** | untested |
| Per-persona style variance | persona median body length max/min ≥ 2.0 | untested |
| Concentration caps | no top-1 entity >45% share on any surface; Gini: email-by-person 0.30–0.55, slack-by-channel 0.35–0.65, hours-by-matter 0.45–0.70 | notes top-1 = 60% |
| Seasonal ramp | preserved from v1 (a strength — do not regress) | ✓ |

### Budget envelope (committed)
Full v2 epoch ≤ **150k LM calls, ≤ $400, ≤ 72h wall** in resumable
segments; 14-day mini-epoch ≤ 6h and ≤ $40. v1 actual: 29.6k calls,
20.6h, ~$30. Structured batch generation (a persona-day of timesheets in
one call; a document in one call) is what keeps 3–5× the artifacts
inside ~5× the budget.

---

## 6. ADRs (defaults stated; proceed, don't block)

- **ADR-0001 practice-management identity** — keep the community/v4 API
  grammar, reskin the product identity accounting-native. Clio is a
  legal product and no official Clio MCP exists.
- **ADR-0002 statistics dependency** — implement `workbench/analysis/
  stats.py` in pure stdlib (KS statistic + asymptotic p, chi-square via
  regularized incomplete gamma, Gini, entropy, autocorrelation,
  Spearman). Rationale: the repo ships lean deps, the agent container
  installs the base project only, and hand-rolled deterministic
  arithmetic is already the house style (integer retrieval scoring).
  Fallback: add scipy to the dev group if exact p-values bite.
- **ADR-0003 volume scale factor** — v2 targets ~3–5× v1, not 1:1 with a
  real firm (which would be ~500 emails/day). Shape fidelity is the
  priority; the scale factor is uniform, documented, and stated in the
  fidelity report so no reader mistakes it for a real firm's raw volume.
- **ADR-0004 client population split** — the *book* (clients, matters,
  invoices, ledger rows) is procedural structure derived from the world
  seed; *content* (correspondence, deliverables, notes) is LLM-authored.
  120–200 clients without 200 LLM actors.
- **ADR-0005 Gmail send policy** — draft-only, matching the official
  server, which has no send tool. Agent sends stay a simulation verb.
- **ADR-0006 parity snapshot pinning** — pin dated `tools/list`
  snapshots per vendor with a documented refresh procedure; Slack and
  iManage both declare live `tools/list` the only truth, and iManage
  publishes no JSON schemas at all (only `container_id` and `query` are
  verbatim-confirmed).
- **ADR-0007 new tool systems** — billing, tax, and ledger ship as
  separate `ToolSystem`s rather than bloating practice management,
  matching how a real firm runs separate products.

---

## 7. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Re-record cost/failure at P6 | High | Flags keep v1 replayable until the single re-record commit; run manager already resumes from any step; mini-epoch proves the shape first |
| LM budget overrun | High | Committed envelope (§5); batch generation; per-day telemetry with a hard call brake; measure on the 14-day epoch before the 140-day run |
| Distribution tuning takes >3 iterations | Medium | Bands committed *before* generation; report shows observed-vs-band per metric so each iteration is targeted, not exploratory |
| Provider instability (bit us tonight: deranked bedrock endpoint stalling with keep-alive whitespace) | Medium | Region-pinned providers + gateway; pre-flight probe in the run manager |
| New randomness breaks determinism | High | Every new source derives from the world seed; property test replays each new surface byte-for-byte; no `Date.now`/`random` anywhere |
| Orphan regressions from new entity classes | High (guards the A) | Integrity coverage lands in the *same commit* as each new class; coherence check extended per system |
| pptx/soffice unavailable in CI | Low | Renderer tests skip on missing binaries the way the docker tests do; the artifact-reopen suite runs where the binaries exist |
| Slack/iManage schema uncertainty | Medium | Snapshot + waiver list; divergence is *declared*, not hidden |
| Band gaming (green via loosened bands) | Medium | Band changes require a diff note in the report; CI diffs committed bands against the previous commit |
| Grader regression on the existing task | Medium | v1 task re-run at P7 is a gate, not a check |

---

## 8. Deliverables checklist

- [ ] `docs/epochs/v2/PLAN.md` (this), ADR-0001…0007
- [ ] `scripts/fidelity_report.py` + `FIDELITY-REPORT.md` (generated,
      baseline then final)
- [ ] `PARITY-MATRIX.md` (living, CI-checked) + `tests/parity/`
- [ ] `tests/realism/` statistical suite with diagnostics on failure
- [ ] Code + tests per workstream, one item per commit
- [ ] `REALISM-REVIEW-V2.md` closing every v1 finding with evidence and
      a link to the guarding check
- [ ] Budget report; expert-audit rubric + scores
- [ ] Final before/after table across all seven scorecard axes

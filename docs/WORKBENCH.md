# Workbench

The single source of truth for what Workbench is, how it is built, and how
to run it. Everything here describes the system as it exists on this
branch; measurement records (fidelity ledgers, run reports) are linked as
appendices at the end. Contributor working rules live in the root
[`AGENTS.md`](../AGENTS.md).

## Mission

Workbench is a factory for reinforcement-learning environments of
realistic professional work. It gives an agent a believable workspace —
the files, systems, colleagues, and interruptions of an actual job — so
that evals, benchmarks, and post-training datasets measure competence
rather than puzzle-solving.

Tasks assembled from synthetic prompts reward pattern completion. Real
professional work is ambiguous, multi-turn, and full of context that
lives in other people's heads: a controller who knows why last quarter's
accrual looks wrong, a partner who changes the ask halfway through, an
inbox that keeps filling while you work. Workbench reproduces those
conditions faithfully enough that a reward signal means something, and
cheaply enough to run thousands of trials.

The goals, concretely:

1. **Simulate a firm, not a fixture.** A multi-agent LLM engine plays
   every employee and client of a professional firm, day by day, and
   writes one append-only, validated world log.
2. **Serve the world through real product surfaces.** The log is
   projected into per-product SQLite databases behind MCP servers that
   emulate the official vendor tools (Gmail, Google Calendar, Slack,
   iManage Work) and modeled ones (practice management), checked against
   pinned vendor snapshots in CI.
3. **Grade against the world itself.** Harbor tasks are built on those
   environments and scored against oracles computed from the same world
   state the agent explores — so ground truth is extracted, never
   hand-authored. Extracted is necessary but not sufficient: the oracle
   must also be *reachable*. A rule the agent cannot evaluate through the
   tool surface grades the environment's plumbing rather than the model,
   however faithfully it reflects the log.
4. **Replay everything.** Every LM call is recorded into content-keyed
   cassettes; a recorded world replays byte-identically with no network,
   which is what makes the datasets auditable and CI-checkable.

## The pipeline

```
WorkplaceSpec (cast, book, channels, seed docs, season)
      │  compile_workplace (deterministic, COMPILER_VERSION = 2)
      ▼
simulation engine  ──►  world.jsonl (typed, validated, append-only)
      │                     │
      │ cassettes           │  materialize(world_log, out_dir)
      ▼                     ▼
byte-identical replay   environment bundle: workspace/ + state/*.db + mcp.json
                            │
                            ▼
                 Harbor tasks (datasets/) — oracle from world state,
                 graded by Reward Kit / task graders, baselines measured
```

The layering (enforced by `tests/test_layering.py`):

```
core  ←  simulation  ←  workplaces
      ↑
environment / tools        adapters
```

`core` owns the typed event vocabulary; `simulation`
is the domain-neutral engine; `workplaces` holds concrete firms
as data; `tools` and `environment` build the
agent-facing side from the log alone; `adapters` runs models
against finished bundles. Domain knowledge exists only in `workplaces/`
and `datasets/`.

## The simulation engine

`simulation` is a clean-room, typed, async, deterministic
rebuild of the generative agent-based modeling pattern DeepMind's
Concordia introduced — no Concordia code or dependency. The simulation
is LLM-first: every employee is a generative agent, the outside world is
LLM-driven client actors, and the deterministic machinery (engine, game
master, scheduler) exists to ground, order, and replay what the models
produce. Persona reasoning runs as DSPy programs; the prompt surface is
exactly signature docstrings and field descriptions, which is what GEPA
optimizes (`simulation.optimize`) and what the cassette keys.

### One epoch day

Each workday is minted by a deterministic day chain:

1. **Morning planning** (deep tier): every persona lays out the day in
   time blocks anchored to its real calendar; the GM clamps and numbers
   revisions. Decide prompts carry the plan with the current block
   marked.
2. **Wake cohorts** on a 30-minute grid with seeded phases. A woken
   persona retrieves from its memory stream, decides, and drafts; the
   result is a typed `ActionIntent`, never free text.
3. **Meetings**: calendar events with two or more simulated attendees
   convene; each turn is one persona speaking from its own staffing and
   knowledge; the transcript is a validated world event. Attendee wakes
   are suppressed mid-meeting.
4. **Client cues**: the season director
   (`simulation.director`) stirs client actors on a seeded
   quasi-Poisson schedule shaped by the firm's calendar (month-end,
   filing season, estimate weeks); the client actor's model authors the
   inbound mail. Replies ride the standard turn grants and depth caps.
5. **End of day**: a reflection turn on the deep tier (daily summaries
   with model-scored importance bullets, weekly rollups every fifth
   workday — the consolidation that keeps prompts O(1) over months) and
   a timesheet turn (one structured call per persona-day emitting the
   whole day's time entries, grounded against real engagements, with a
   pure duration rule from the timeflow model).
6. GM rejections route back to their actor as importance-10 memories, so
   personas learn from failures inside the run.

### Grounding

Personas are grounded, not imaginative. Working memory is a fold over
observed events; the memory stream stores typed cognition events with
integer-only retrieval scoring (no floats — byte-identity), so a
character can only reference what actually happened. The grounded game
master (`gm/`) makes zero LM calls: it resolves every reference against
world state or rejects the intent into a visible `sim.gm.note`, routes
events through attention masks, grants turns (reply chains stop
auto-granting at depth 3; threads cap at 12 messages with instructive
rejection), and assigns durations through the pure `timeflow` model.
Institutional knowledge lives in persona params with a sharing policy;
the legal workplace's acceptance litmus proves such knowledge flows
person → conversation → artifact during a day rather than leaking from a
seed.

### Determinism and the cassette contract

- One `Seed` enters at the run entry; everything derives via
  `derive_seed(seed, *path)` (blake2b, PYTHONHASHSEED-independent).
- Every LM request carries a derived seed and is keyed by
  `blake2b(canonical_json(request))` into the cassette store
  (`lm/cassette.py`) — the key covers model, messages, schema, seed, and
  sampling parameters, so replay is independent of call order and
  concurrency schedule.
- The windowed engine admits batches as a **canonical prefix**: admission
  scans the queue in `(time, order)` order and stops at the first
  conflict, so the world log is byte-identical at every window size.
- Runs are durable: `run.db` commits one transaction per engine step;
  a kill at any point roll-forward resumes losslessly (LM counters,
  memory facts, and cast growth restore from the log plus durable meta).
- `compile_workplace` stamps `COMPILER_VERSION` (currently 2) so a
  cassette can never silently replay against a different compilation.

**The cassette-invalidation boundary.** Any change to prompt text
(signature docstrings, field descriptions), signature/schema fields, the
model choice, or the *sequence* of LM calls orphans recordings — replay
then raises `CassetteMissError` by design. Everything downstream of the
world log — projections, MCP servers, renderers, materialization,
graders, task bundles — never feeds back into the simulation and is
therefore free to change without re-recording. When a prompt-affecting
change is necessary, record into a fresh cassette directory, review the
new world, and commit change plus cassette together.

**The loud-failure contract.** `CassetteMissError`,
`LMBudgetExceededError`, and `LMTransportError` always re-raise — no
silent fallbacks, no degraded runs. Only deterministic content/parse
failures degrade, into typed rejections and minimal notes the replay
reproduces exactly.

### Models

| Tier | Model | Used for |
|---|---|---|
| fast | `deepseek/deepseek-v4-flash-0731` | decides, drafts, timesheets, client actors |
| deep | `anthropic/claude-haiku-4.5` | morning plans, reflections, meeting turns |

Recording pins providers explicitly (`OpenRouterLM` sends a provider
order and disables reasoning mode): the epoch runners use the chain
`deepinfra → fireworks → novita → deepseek` for the fast tier and pin the
deep tier to `amazon-bedrock`. Unpinned routing silently moves between
provider fleets, which changes tokenization and sampling — a recorded
day must replay from the source it was recorded against. The eval
harness applies the same discipline to the models it runs (for example
`anthropic/claude-opus-5` pins to `amazon-bedrock/us-east-1` with bare
`amazon-bedrock` as recovery). A 404 "no endpoints found" from
OpenRouter usually means a provider pin the account cannot use, not a
delisted model.

### Externalized seats

`ExternalEntity` + `ActTransport` (in-process, scripted, stdio JSONL)
let an external process play any seat; the engine cannot tell the
difference. This is the integration seam for RL frameworks and online
operation (swap `EventDrivenTimeModel` for a wall-clock model).

## From world log to environment

`environment.materialize(world_log, out_dir, seat=...)`
validates the log (every reference must resolve — an incoherent log
never becomes an environment), projects the per-tool databases, renders
structured artifacts to real office files (`artifacts`:
spreadsheets with formula cells, formatted documents, slide decks), and
writes the bundle:

```
<out_dir>/               bundle root — never the agent's working directory
  environment.toml       runner config, including the agent workspace path
  mcp.json               server launch specs, db paths bundle-relative
  state/*.db             offstage: only the environment user reads these
  workspace/             becomes /home/agent/workspace — documents only
```

The split is the offstage boundary made structural: the agent's working
directory holds documents and nothing else, so the emulated products are
the only route to the record. The agent never observes personas, hidden
state, private reasoning, ground truth, or reward logic. `sim.*` events
are offstage by construction — `ToolSystem` refuses to handle them.

## Tool surfaces

`tools` is a plugin registry: each system is a subpackage
(tables, projector, server registrar) assembled into a `ToolSystem`, and
one line in `registry.py` drives projection, coherence checking,
`mcp.json` assembly, and the stdio `serve` entry point.

| System | Tools | Lineage | Write half |
|---|---|---|---|
| `gmail` | 19 | Google's official Gmail MCP (emulated) | drafts, labels, trash, spam — **no send tool**, matching the official server |
| `calendar` | 9 | Google's official Calendar MCP (emulated) | `create_event`, `update_event`, `delete_event`, `respond_to_event` |
| `slack` | 19 | Slack's official MCP (emulated) | messages, drafts, scheduled sends, conversations, reactions, canvases |
| `imanage` | 15 | official iManage Work MCP (emulated) | recents/actions recorded server-side |
| `clio` | 8 | Clio Manage API v4 grammar (modeled — no official server exists) | read-only |
| `compliance` | 11 | in-house (modeled) | the intake write surface: action tables start empty and are written by the agent |

Reads open the databases via `connect_readonly`; writes go through
`connect_readwrite` into action/sent tables, and grading reads the
resulting state — nothing an agent writes ever feeds back into the
simulation. `compliance` is the write-workflow template: its reference
tables are seeded from a scenario at task-build time rather than
projected from the log.

**Parity is pinned, not aspirational.** Dated `tools/list` snapshots
with provenance and confidence live under `tests/parity/snapshots/`
(currently gmail, calendar, slack, imanage — captured 2026-08-14), and
CI runs four gates per vendor: every official tool implemented or waived
with a reason, no invented tools, required parameters present, and
provenance recorded; a fifth test asserts
[`PARITY-MATRIX.md`](fidelity/PARITY-MATRIX.md) covers every vendor.
Refreshing a snapshot is a deliberate commit that updates the matrix in
the same change.

**Seats.** The seat comes from `WORKBENCH_SEAT` (`serve --user`), read
at call time; each system honors it the way its product would (gmail:
one mailbox; slack: joined conversations; clio: `who_am_i`; calendar:
`primary`). Unset means org-wide where the product has such a view, and
tools that need an identity raise rather than guess. Unknown ids raise
`UnknownRefError` carrying the id.

## Tasks and grading

A task is `datasets/<dataset>/tasks/<task>/` in
[Harbor](https://www.harborframework.com/docs)'s format: `task.toml`,
`instruction.md`, `solution/`, `tests/`. Builders materialize a bundle
per task (or one shared seatless bundle per dataset), run the reference
solver against the fresh bundle, and require its output to match the
committed oracle byte for byte — `--refresh-truth` is the only way to
move that line. `datasets/hartwell/harbor_stage.py` stages a bundle into
Harbor's `environment/` upload channel with an installer that puts the
databases offstage (environment-owned, 0700) inside the container and
verifies the agent user cannot read them.

Instructions are professional briefs, not task specs: who the agent is,
what happened, the precise rule defining the answer set, and the
deliverable. Read tasks grade weighted partial credit against the
oracle; write-workflow tasks (matter-intake-compliance) grade
conjunctive outcomes on the mutated action tables at pass^k.

How a task is built and how a score is read are governed by
[`METHOD.md`](METHOD.md); this section records only what the suites
measure.

**A measured reward is a claim about a model only after every miss has
been classified.** Five things take a point away — environment, data,
harness, task, model — and on a mature suite the task defect is both the
most common and the one that looks most like a model failure. Ashgrove's
first published sub-1.0 scores were, without exception, defects in the
answer key: a pattern narrower than the prose it implemented, a rounding
order nobody stated, an internal id no tool serves. Each was certified as
a model failure first, by a check that re-ran the rule that produced the
row and therefore could not disagree.

The suites now ship with an oracle re-derived from raw events, a
reachability crawl over the real servers, a degeneracy report, grading
guards, and a miss classifier whose signals do not go through the task's
own rule. Those gates, and the reasoning behind each, are in
[`METHOD.md`](METHOD.md); measured scores live in the dataset ledgers and
in [`runs/`](runs/).

The Hartwell suite (ten tasks, including the matter-intake-compliance
write workflow) carries its own measured floors, naive scores, and
frontier failure modes in the
[four-month-history run records](runs/2026-08-09-four-month-history/REPORT.md).

`adapters.harness` is the in-repo eval loop: it opens a
bundle's MCP servers over stdio, runs a tool-calling model in an episode
confined to `bundle/workspace`, and grades with the task's own grader.
`adapters.harbor_matrix` runs budgeted, fingerprinted Harbor
matrices through a local gateway that keeps the OpenRouter key out of
containers.

## Worlds

All five worlds serve their history through the same tool surfaces; each
is a data package under `src/workplaces/`. Hartwell's history
is chronicle-built (procedural structure plus cached, LM-authored
content — a rebuild makes zero new model calls); the other worlds run
through the engine.

**Legal (Argent Systems)** — the original single-day demo: six people,
an inbound vendor NDA, and an unwritten standard living in one persona's
head. Its acceptance suite (active when a local cassette is recorded)
proves knowledge flows through conversation, not seeds.

**Hartwell** — the frozen v1 world: a litigation firm with a four-month,
9,427-event deterministic history (`datasets/hartwell/build_history.py`,
byte-compared on every build) and ten Harbor tasks. Frozen means green:
its history, floors, and verifier regressions stay in CI, and new write
surfaces were landed without disturbing it.

**Calder & Finch, CPAs** — a 17-person CPA firm run through the
LLM-first engine for a full six-month epoch: 140 workdays
(2026-01-05 → 2026-07-17, 194 calendar days), 35,670 events, 29,621 LM
calls, all audit gates green, perfect 140/140 plan/reflection cadence,
and a flat ~2.2k-token prompt bound from day 1 to day 140. The full
epoch cassette stays local (355 MB); committed under
`src/workplaces/calder/cassettes/` are the two-day acceptance
cassette — replayed in CI byte-identically sequential, windowed, and
killed-then-resumed (`test_calder_epoch_acceptance.py`) — and the
five-day flagship-week recording. The `h1-billing-audit` task builds
from the epoch world.

**Ashgrove Reid LLP** — the comparison firm: the same seventeen
professionals as Calder (the controlled variable) working an
assurance-led book on a different calendar, run on the v2 engine with
timesheets and a rate sheet. Current epoch: 10 workdays, 4,151 events.
Five graded tasks build from it (`datasets/ashgrove/build_tasks.py`).

**Merrick Stanton LLP** — the first law firm, and the first world built
for artifact realism rather than only for traffic. Twenty-one
professionals across litigation, corporate, employment and IP; ten client
organisations with their own contacts, two opposing firms, two courts,
two vendors; twenty-four client matters and eight non-billable codes.
Recorded through the engine over a 180-day window at roughly fourteen
minutes per simulated workday.

Two structures the accounting worlds do not have, and both are what make
it worth building. **Deadlines are set by somebody else** — a court moves
a scheduling order and the firm rearranges, so "what the deadline is now"
is a recorded fact with a history rather than a derived one, which is the
only kind a task may grade. And **work product becomes final by leaving
the firm**: a brief that is filed, an agreement executed, an opinion
issued. That is what makes its document formats load-bearing, and why its
file-room gate *requires* issued PDFs and decks rather than permitting
them.

Its calendar runs two clocks deliberately out of phase — a quarterly
transactional one converging on the last fortnight of March and June, and
a litigation one belonging to the court, sitting mid-quarter where the
scheduling orders put the discovery cutoffs.

## Fidelity

Realism is measured, not asserted. `docs/fidelity/bands.json` commits
91 distribution bands (volumes, distribution shapes with
anti-uniformity KS tests, Gini concentrations, seasonality, cross-surface
correlation) derived from published CPA-firm benchmarks;
`scripts/fidelity_report.py` measures any world against them and exits
non-zero on failure. The statistics are pure stdlib
(`workbench/analysis/stats.py` — KS, chi-square, Gini, entropy,
autocorrelation, Spearman), unit-tested against known answers, because
the agent container installs the base project only and the suite asserts
bands, not published p-values.

Current ledger:

| World | Pass | Fail | Absent |
|---|---|---|---|
| [v1 baseline](fidelity/BASELINE-V1.md) | 21 | 50 | 20 |
| [Ashgrove, 10 workdays](fidelity/ASHGROVE.md) | 17 | 46 | 28 |

**ABSENT means the surface that metric measures does not exist in the
world yet** — a finding, not a skip: invoices, realization, AR aging,
utilization tiers, tax filings, and the full client book are unbuilt
(see Known gaps). FAIL means the surface exists and misses its band.
Band changes require a diff note; green must never come from loosened
bands.

## Design decisions

Decisions that shaped the build, preserved from the retired ADRs:

- **Practice management keeps Clio's API grammar with an
  accounting-forward identity.** No official Clio MCP server exists;
  the community server's v4 REST grammar (envelopes, cursor pagination,
  `display_number`) is the closest thing to a standard and transfers
  cleanly to accounting practice management, so the wire grammar stays
  and the matrix records the surface as *modeled* with a named lineage
  rather than emulated.
- **Statistics are pure stdlib, not scipy.** The repo ships lean, the
  agent container installs the base project only, and hand-rolled
  deterministic arithmetic is already the house style. Approximate
  p-values are acceptable because the suite asserts committed bands at
  α=0.01, not published values. Fallback if precision ever bites: scipy
  in the dev group for that metric only.
- **Volume targets ~3–5× v1, not 1:1 with a real firm.** Shape
  (distributions, tails, correlations) is scale-invariant and is the
  real gate; 1:1 volume (~300–500 emails/day) would cost ~10× the LM
  budget to buy repetition, not structure. The scale factor must be
  stated in any external presentation of a dataset.
- **The book is procedural, the content is authored.** Structure a real
  firm's systems would generate (client book, engagement records,
  invoice cycles) derives from the world seed; every piece of language
  or judgment is an LM call grounded against that structure. Client
  actors are minted only for clients in active correspondence. If a
  structural generator starts emitting prose, it has crossed into
  authorship and must become an LM call.
- **The Gmail write surface is draft-only.** The official server
  deliberately ships no send tool; matching it exactly means no task can
  accidentally train mail-sending, and write tasks grade on drafts,
  labels, and triage state. Send semantics would be a documented
  divergence requiring its own decision.
- **Parity is pinned to dated snapshots.** Official surfaces move and
  two vendors publish no schemas; asserting against a live remote would
  be flaky and untrue. Snapshots record provenance and confidence;
  drift surfaces as a reviewed diff.
- **Billing, tax, and ledger will ship as separate tool systems** (when
  built), matching how a real firm runs separate products with separate
  logins — cross-system reconciliation becomes a task class, not an
  artifact of one schema.
- **Read behavior and write behavior live in one server per product**,
  with reads on read-only connections and writes confined to action
  tables — the framework structurally refuses `sim.*` tags, so offstage
  state cannot reach an agent-facing database.
- **Hand-rolled SQLite over an ORM.** `db.py` derives DDL, inserts, and
  reads from one Pydantic row model; SQLAlchemy/SQLModel/peewee were
  each rejected for import cost, dual schema declaration, or
  incompatible typing.
- **No Concordia dependency.** The 2026 source audit found dead seed
  plumbing, unseeded per-prompt RNG, and checkpoints that cannot
  resume; the pattern was rebuilt clean-room with determinism as the
  product.

## Running things

Setup and tests:

```bash
uv sync                       # install the workspace (dev includes dspy + renderers)
uv run pytest                 # full suite; cassette-gated suites skip when unrecorded
uv run ruff check --fix .     # lint
uv run ruff format .          # format
```

Build the container image (context is `environment/`):

```bash
docker build -f environment/Dockerfile -t workbench:dev environment
```

Run or resume an epoch (record needs `OPENROUTER_API_KEY`; replay does
not):

```bash
uv run --env-file .env python datasets/calder/run_epoch.py start \
    --days 194 --mode record --out out/calder/epoch-6mo --window 32
uv run python datasets/calder/run_epoch.py resume --out out/calder/epoch-6mo
uv run python datasets/calder/run_epoch.py status --out out/calder/epoch-6mo
uv run python datasets/calder/run_epoch.py audit  --out out/calder/epoch-6mo
```

`datasets/ashgrove/run_epoch.py` is the identical CLI for the comparison
firm. The single-day legal demo is `python -m simulation.demo`
(`--mode record|replay --cassette <dir>`).

Measure a world against the bands:

```bash
uv run python scripts/fidelity_report.py \
    --state out/ashgrove/bundle/state \
    --log out/ashgrove/epoch/world.jsonl \
    --out docs/fidelity/ASHGROVE.md
```

Record the law firm's six-month window (resumes on crash, refuses to
loop past three unproductive restarts):

```bash
scripts/supervise_epoch.sh merrick out/merrick/epoch out/merrick/cassette 180 24
```

Ask what a corpus can carry before building a task on it:

```bash
uv run python datasets/merrick/measure_candidates.py --days 20
```

Build task environments and oracles:

```bash
uv run python datasets/ashgrove/build_tasks.py            # all five tasks
uv run python datasets/calder/build_task.py               # h1-billing-audit
uv run python datasets/hartwell/build_tasks.py            # the ten-task suite
```

Run tasks with Harbor against the prebuilt image, or with the in-repo
harness:

```bash
harbor run -p datasets/<dataset>/tasks/<task> -a claude-code -m <model>
harbor view

OPENROUTER_API_KEY=... uv run python -m adapters.harness.cli \
    --task datasets/legal-nda/tasks/vantage-triage \
    --model deepseek/deepseek-v4-flash-0731 --attempts 3
```

## Known gaps

The fidelity ledger's ABSENT column is the worklist, measured honestly:

- **Time & billing beyond timesheets**: invoices, WIP review, payments,
  realization, write-downs, AR aging — the planned `billing` tool
  system does not exist yet (timesheet entries do, on the clio surface).
- **Tax workflow**: returns, extensions, e-file acknowledgments,
  notices — the planned `tax` system is unbuilt.
- **Client ledger / payroll**: the planned `ledger` system is unbuilt.
- **The full client book**: worlds carry ~10–14 active engagements, not
  the 120–200-client procedural book with a dormant tail.
- **Documents at volume**: persona-created office files with format mix,
  version chains, and announced-and-attached deliverables largely
  missing from the measured epochs. The renderer emits `.docx`, `.pdf`
  and `.pptx` and earlier worlds exercised all three; the current epoch
  declares only `markdown` and `spreadsheet`, so two of four document
  types a practice would produce — signed letters, decks — are absent
  from the world agents are graded on.
- **Calendar and Slack shape**: RSVP responses, recurring series,
  cancellations, multi-channel Zipf traffic, DMs, off-hours activity —
  all currently failing their bands.
- **Volume**: firm-wide email is below band (36/day vs 60–120 at the
  committed 3–5× scale).
- **Oracles still read `state/*.db` directly**, so a task rule can in
  principle depend on a value no tool exposes. The reachability gate now
  crawls the real servers and refuses any oracle naming an identifier
  they never serve, which closes the failure mode that produced the early
  Ashgrove sub-1.0 scores; solvers running *through* the MCP surface
  would close it by construction instead of by gate.
- **Referential coherence of authored content**: iManage registers
  "Audit Engagement Letter Template" over a document whose body is a
  change-order summary for "Ridgeview" — a client in no roster and no
  workplace spec. One mislabel in five documents, found by a rollout
  rather than by a gate; no check asserts a document's registered name
  matches its content, or that entities named in prose exist.
- **Work items minted as engagements**: the ledger carries "Register 2026
  engagement letter document" and "Compile itemized 401(k) discrepancy
  list" as matters alongside real audits, which is what made the
  client/internal boundary ambiguous in the first place.

## Appendices — measurement records

- [`fidelity/ASHGROVE.md`](fidelity/ASHGROVE.md) —
  Ashgrove against the 91 bands (17/46/28).
- [`fidelity/BASELINE-V1.md`](fidelity/BASELINE-V1.md)
  — the v1 floor the bands were written against (21/50/20).
- [`fidelity/PARITY-MATRIX.md`](fidelity/PARITY-MATRIX.md) — living,
  CI-checked implemented/waived matrix per vendor.
- [`runs/2026-08-13-calder-epoch/`](runs/2026-08-13-calder-epoch/) — the
  LLM-first engine pivot: epoch report, deep realism review (the
  scorecard the bands answer), MCP parity audit.
- [`runs/2026-08-13-calder-six-month/`](runs/2026-08-13-calder-six-month/)
  — the earlier chronicle + live-day hybrid build of Calder.
- [`runs/2026-08-09-four-month-history/`](runs/2026-08-09-four-month-history/)
  — the Hartwell suite: report, decision ledger, failure-mode studies,
  floors.

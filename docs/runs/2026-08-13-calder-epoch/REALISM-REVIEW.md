# Calder environment realism review — deep dive

Scope: the full six-month epoch world (140 workdays, 35,670 events), its
materialized five-tool environment, all generated documents, and the
first graded task. Method: forensic SQL over every projected database,
content sampling across the span, structural-integrity checks, and
comparison against published CPA-firm operating benchmarks (billable
hours, utilization, busy-season patterns). Verdict up front: **the
world is narratively and structurally excellent, economically and
volumetrically thin.** What exists is coherent, grounded, and
convincingly professional; what is missing is the sheer density and the
money-side machinery of a real practice.

## Scorecard

| Layer | Grade | One-line verdict |
|---|---|---|
| Data integrity | A | Zero orphan refs across five tools; one roster; byte-replayable |
| Narrative coherence | A− | Multi-week storylines consistent across surfaces; facts stable |
| Professional voice | B+ | Real CPA vocabulary and correct advice; some role/date drift |
| Seasonal dynamics | B | Right shape (Jan closes, Apr 15 peak), wrong amplitude (no overtime) |
| Operational volume | D | 3–5% of a real firm's hours, mail, and engagement counts |
| Economic realism | D | No invoices, no WIP, thin time capture, no realization loop |
| Tool-stack fit | C+ | Five good generic surfaces; the CPA-defining systems are absent |

## Strengths

### 1. Structural integrity (the foundation is genuinely solid)
- **Zero referential orphans** in any direction: every email recipient,
  reply link (601 threads), reaction, matter note, time activity,
  calendar attendee, and document version resolves.
- **One 28-person roster** identical across all five tools — the join
  key that makes the bundle one world.
- The **offstage boundary holds structurally**: 17k+ cognition events
  (plans, reflections, wakes, cues) never leak into the environment.
- Everything replays byte-for-byte from the cassette; the world is a
  *record*, not a generation.

### 2. Narrative coherence across surfaces and weeks
- The same storylines (ITHELP-1042, the CAM reconciliation, K-1
  delivery, Riverbend migration) run simultaneously through email,
  chat, matter notes, and private reflections without contradiction —
  agents agree on figures ($2,100 / $1,225 / $650 / −$2,870), gates
  ("16:30 gate holds"), and deadlines across surfaces and across weeks.
- Cross-team dependency release is modeled: three departments each
  independently confirming "closed on tax's side, no further action."
- 3,038 of 3,048 mail bodies distinct; reflections show **zero
  copy-paste repetition** at day 140 (40/40 distinct bullets sampled).

### 3. A real firm hierarchy behaving like one
- The 16-title roster is a correct small-CPA-firm shape: Managing
  Partner, a CAS partner, an Assurance principal, tax/audit managers,
  seniors, four staff, payroll, IT, admin, office/billing.
- Volume concentrates plausibly by role: the Client Accounting Lead is
  the top mail sender (closes are correspondence-heavy); seniors carry
  the hours; admin coordinates.
- The interior life is disciplined: **140/140 days of plans and
  reflections for all 16 personas**, importance-scored, with open loops
  that get picked back up ("deprioritized today; must resume before
  Thursday audit sync").

### 4. Seasonality exists and points the right way
- Client cue pressure ramps ~6/day (January) → ~15/day (early April);
  April 15 is the busiest day in its window with visible decompression
  after; month-end close chatter clusters correctly.
- The cue *content* mix is right for each season: K-1 chasing, new-hire
  withholding, CAM disputes reopening, bonding-company financials,
  estimate coordination.

### 5. The learning curve is real
- Grounding rejections fell from 14–15/day (week 1) to 2–8/day (June)
  — the failure-feedback loop measurably teaches personas; the firm
  gets *better at being itself* over the run, the opposite of
  long-horizon agent decay.

### 6. Environment engineering
- Five emulated products (gmail, slack, clio, calendar, imanage) served
  over MCP with realistic API shapes (paging, etags, display numbers),
  state offstage and permission-locked.
- Proven gradeable: an outcome-conjunctive audit task with an
  oracle-verified grader; Opus 5 passed at reward 1.0 while a
  deliberately adversarial near-miss battery all scores 0.

## Weaknesses

### 1. The economic engine of a CPA firm is missing (most important)
- **Time capture is ~4% of reality.** 326 logged hours across 140
  workdays (2.3 firm-hours/day). Benchmarks put professional staff at
  1,050–1,200 billable hours/year each (70–80% utilization) — H1 for
  this roster should be **~6,500–7,800 hours**. Only 8 of 16
  professionals ever logged time; the top biller shows 116h for six
  months (a real senior logs that in three weeks of March).
- **No billing loop at all**: no invoices, WIP, AR, realization, or
  collections anywhere in the world — for a firm whose product *is*
  billed hours, the revenue side simply doesn't exist. Several
  activities carry no rate.
- **Client and engagement counts are 10–20× low**: 11 clients / 21
  matters for a 17-person firm; a real one carries 150–400+ clients and
  hundreds of concurrent engagements (each client: entity return, owner
  1040s, monthly close, payroll quarterlies, 1099s).

### 2. Missing operational surfaces (the CPA-defining tools)
- **No tax preparation system** — the single most-used application in a
  CPA firm (returns, e-file statuses, extensions). Returns are
  *discussed* but never exist as artifacts; April 15 passes with no
  filing or extension records.
- **No client GL/accounting system** (the QBO seat) — closes happen in
  prose, not in books.
- **No payroll system** despite a payroll specialist storyline.
- **Zero email attachments** in 3,048 messages — accountants live on
  attached PDFs/XLSX; deliverables are referenced ("attached is the
  signed copy") but nothing is attached. The schema supports them; the
  engine never grounds them.
- **Documents are 8 internal templates/policies — zero client
  deliverables.** No workpapers, financials, K-1 packages, or letters
  ever land in iManage. The engagement-letter *template* was revised 12
  times; no per-client letter was ever instantiated from it.

### 3. Lifecycle gaps (things start; nothing finishes)
- **Matters never close**: 20 Open / 1 In-progress after six months;
  reflections say "ticket closed" but status transition isn't a
  grounded verb, so the record never agrees.
- **Calendar RSVP is dead**: all 262 attendee records sit at
  `needsAction` for six months.
- **Meetings barely exist as records**: 1 transcript in 140 days (seed
  convenes fire once; recurrence deferred) — the standing huddle met
  once in six months while chat absorbed coordination.
- **Attention is monopolized**: one hot matter holds 400 of 664 notes
  (60%); three channels of four (#engagements, #billing, #it-help)
  carry zero messages while everything routes through #firm; no DMs.

### 4. Cultural/behavioral signatures that don't match the trade
- **No busy season in the clock**: 1 weekend email in six months
  (including April); mail stops at 17:00 sharp; the hour histogram is
  flat 9–17. Real tax season is 50–70-hour weeks with working
  Saturdays — the defining cultural fact of the profession is absent
  because the engine's day chain only mints weekday 9–17 wakes.
- **Hyper-responsiveness**: median email reply latency is **5
  minutes** (p90 2.3h) — an artifact of wake-driven replies and 300s
  delivery quantization; real professional email medians run hours.
- ~32% of client-touching threads end on the client's message (some are
  natural "thanks" closers, but SLA discipline isn't modeled).

### 5. Content drift (small but visible to a domain expert)
- **Fiscal-calendar drift**: a Q3-reporting storyline with October
  delivery dates runs through March–April; internally consistent
  (memory works) but seasonally wrong — nothing ties invented dates to
  the sim calendar.
- **Year confusion**: "period ending December 31, 2023" where 2025
  is meant; prior-year references occasionally skew.
- **Role-signature confusion**: firm staff signing with client org
  names ("Payroll Specialist, Blue Fir").
- **Tool identity mismatch**: Clio is a *legal* practice-management
  product; a CPA firm would run Karbon/Canopy/CCH Practice. The
  semantics (matters, activities, notes) transfer fine, but the skin
  says law firm.

## Priority recommendations (LLM-first, in order of leverage)

1. **Ground the economics** — make time capture a first-class daily
   artifact: one structured end-of-day timesheet intent per persona
   (6–8 entries against real engagements) instead of occasional single
   logs. One LM call per persona-day closes ~90% of the volume gap
   without abandoning LLM authorship. Add a monthly billing turn
   (partner reviews WIP → invoice artifacts) to create the revenue loop.
2. **Add the missing artifact surfaces** — email attachments
   (document refs the GM validates), per-client deliverable documents
   (returns, financials, letters instantiated from templates), and a
   minimal tax-workflow tool (return records with statuses:
   in-prep → review → filed/extended). April 15 should leave e-file
   receipts and extension records behind.
3. **Close the lifecycles** — ticket status transition and calendar
   RSVP as grounded verbs (personas already *say* they close things);
   meeting recurrence so standing meetings actually recur.
4. **Turn on busy season** — season-scaled wake windows (evening +
   Saturday cohorts Feb–Apr), and delivery delays drawn from a
   realistic latency distribution instead of a fixed 300s quantum.
5. **Spread the attention** — channel-routing pressure (topic → right
   channel), DM usage, per-matter note caps analogous to the thread
   brake, and a larger client/engagement roster next epoch.
6. **Pin content to the calendar** — a GM check that in-content dates
   fall within plausible windows for the referenced work (rejecting
   "October delivery" for a March close the way it rejects unknown
   ticket refs), and identity guards on signature blocks.
7. **Reskin practice management** for the domain (rename the clio
   surface or introduce an accounting-native skin).

Items 1–3 and 5–6 change prompt surfaces or grounding rules and
therefore **invalidate the committed acceptance cassettes** — they
belong to the next epoch revision, re-recorded together, not as
hotfixes. Item 4 is compile/scheduler-level; item 7 is tooling-only.

## Benchmark sources

- Utilization/billable-hour targets: getskillability.com (CPA firm
  utilization benchmarks), mosaicapp.com (professional-services
  utilization statistics), accountingdepartment.com (utilization,
  realization, billable rates), karbonhq.com (realization rate).
- Busy-season workload: memtime.com (accountant hours), trullion.com
  and taxdome.com (busy-season breakdowns), envoice.eu (weekend/long
  hours).

# Phase 2 plan — four months of Hartwell & Marsh LLP

**Window**: Monday 2026-03-02 through Tuesday 2026-06-30 (87 workdays,
epoch 2026-03-02T00:00:00-08:00, America/Los_Angeles).

**Cast**: 12 employees — 2 partners, 1 of-counsel, 3 associates,
2 paralegals, 1 ops manager, 1 billing coordinator, 1 IT/admin,
1 records clerk. Clients: 12 organizations (org.record category=client).
External contacts: 14 people — 6 opposing counsel, 3 vendor contacts,
2 court clerks, 3 client-side individuals — sized to the storylines below.

**Storylines** (each an arc across weeks, mined for tasks later):
S1 vendor NDA standard drifts (redlines diverge from the playbook over
months); S2 an acquisition matter with a fee dispute buried in billing
activities; S3 a document that silently loses a clause across versions;
S4 a client relationship that sours across Gmail/Slack sentiment before
formal termination in Clio; S5 a court deadline rescheduled three times
across calendars and email.

**Tiers**:
- Tier A — LM-recorded storyline days: **10 days** via the engine
  (~500 calls/day at Flash ≈ $0.05/day) ≈ **$0.50**, wall ~2h serial.
- Tier B — procedural days: 77 days of deterministic, seeded generators
  emitting typed events directly (routine mail, standup chat, time
  logging, billing cycles, calendar) — **$0 LM**.
- Tier C — LM-flavored content: one-shot completions for ~120 document
  bodies/long emails within procedural days ≈ **$0.30**.
Projected Phase 2 spend ≈ **$0.80–1.50** against $24.70 remaining.

**Mechanics**: `simulation/chronicle/` builder — one world log, segments
appended via WorldLogWriter.append_to; minter continuity by scanning max
counter per prefix; compile gains time_offset + optional starting minter
+ genesis suppression for later days; per-day persona knowledge deltas
authored by the director. Pilot = 1 procedural week + 1 recorded day,
audited before scaling. GEPA only if the pilot shows fixable problems.

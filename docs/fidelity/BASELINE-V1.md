# Fidelity baseline — epoch v1

Measured against the v2 bands before any v2 work. This is the floor we are moving.

**21 pass · 50 fail · 20 absent** of 91 committed bands.

ABSENT means the surface that metric measures does not exist in this world yet — a finding, not a skip.

## billing

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Billable hours logged, H1 | 6500 – 7800 | 326.4 | 326 | ❌ FAIL |
| Roster members logging time | ≥ 16 | 8 | 8 | ❌ FAIL |
| Time entries per person-day, median | 6 – 8 | 0 | 0 | ❌ FAIL |
| Time entries per person-day, p90 | ≤ 12 | 1 | — | ✅ PASS |
| Entry duration, median | 0.5 – 0.8 | 0.5 | — | ✅ PASS |
| Entry duration, p95 | ≤ 4 | 1.5 | — | ✅ PASS |
| Entries on whole/half hours | ≤ 0.55 | 0.5673 | — | ❌ FAIL |
| Entry duration rejects uniform | ≤ 0.01 | 1.217e-172 | — | ✅ PASS |
| Non-billable share of logged time | 0.12 – 0.25 | 0 | 0 | ❌ FAIL |
| Distinct non-billable categories | ≥ 4 | — | 0 | ⚪ ABSENT |
| Realization rate | 0.85 – 0.95 | — | — | ⚪ ABSENT |
| Per-matter realization spread | ≥ 5 | — | — | ⚪ ABSENT |
| Matters written down >25% | ≥ 0.03 | — | — | ⚪ ABSENT |
| AR aging buckets populated | ≥ 4 | — | — | ⚪ ABSENT |
| Collection lag, median days | 25 – 45 | — | — | ⚪ ABSENT |
| Monthly invoice cycles | ≥ 6 | — | — | ⚪ ABSENT |
| Disputed invoices | ≥ 1 | — | — | ⚪ ABSENT |
| Utilization, partners | 0.35 – 0.6 | — | — | ⚪ ABSENT |
| Utilization, managers | 0.55 – 0.75 | — | — | ⚪ ABSENT |
| Utilization, seniors | 0.65 – 0.85 | — | — | ⚪ ABSENT |
| Utilization, staff | 0.7 – 0.9 | — | — | ⚪ ABSENT |
| Gini, hours by matter | 0.45 – 0.7 | 0.6755 | 0.62 | ✅ PASS |

## book

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Clients on the book | 120 – 200 | 9 | 11 | ❌ FAIL |
| Engagements | 250 – 500 | 21 | 21 | ❌ FAIL |
| Engagements per client, mean | 2 – 3.5 | 2.333 | 1.9 | ✅ PASS |
| Gini, fees by client | 0.55 – 0.75 | 0.5773 | — | ✅ PASS |
| Top-10 client share of fees | 0.35 – 0.55 | 1 | — | ❌ FAIL |
| Clients under 5 hours in H1 | ≥ 0.25 | 0.3333 | — | ✅ PASS |
| Clients in active correspondence per month | 20 – 40 | — | — | ⚪ ABSENT |

## calendar

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| RSVP accepted | 0.6 – 0.8 | 0 | 0 | ❌ FAIL |
| RSVP tentative | 0.05 – 0.15 | 0 | 0 | ❌ FAIL |
| RSVP declined | 0.05 – 0.15 | 0 | 0 | ❌ FAIL |
| RSVP still needsAction | ≤ 0.1 | 1 | 1 | ❌ FAIL |
| Meetings at 30 or 60 minutes | 0.55 – 0.75 | 0.7922 | — | ❌ FAIL |
| Meetings at 15/45/90+ | ≥ 0.1 | 0.1429 | — | ✅ PASS |
| Recurring series | ≥ 8 | 0 | 0 | ❌ FAIL |
| Cancelled events | 0.03 – 0.08 | 0 | 0 | ❌ FAIL |
| Internal meetings with transcripts | ≥ 0.3 | 0.01333 | 0.013 | ❌ FAIL |

## cross

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Weekend activity, Jun-Jul | ≤ 0.02 | 0 | 0 | ✅ PASS |
| Weekend activity, Feb-Apr | 0.06 – 0.15 | 0 | 0 | ❌ FAIL |
| Per-engagement volume correlation across surfaces | ≥ 0.45 | 0.2635 | — | ❌ FAIL |
| Per-person volume correlation across surfaces | ≥ 0.45 | -0.04659 | — | ❌ FAIL |
| Persona verbosity spread (max/min median) | ≥ 2 | 2.152 | — | ✅ PASS |
| Top engagement's share of notes | ≤ 0.45 | 0.6024 | 0.602 | ❌ FAIL |

## documents

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Documents | ≥ 400 | 8 | 8 | ❌ FAIL |
| Created by personas (not seeded) | ≥ 0.7 | 0 | 0 | ❌ FAIL |
| Format mix: xlsx | 0.3 – 0.45 | 0.25 | 0.25 | ❌ FAIL |
| Format mix: docx | 0.2 – 0.35 | 0.125 | 0.125 | ❌ FAIL |
| Format mix: pdf | 0.1 – 0.2 | 0 | 0 | ❌ FAIL |
| Format mix: markdown | 0.05 – 0.15 | 0.625 | 0.625 | ❌ FAIL |
| Format mix: pptx | 0.03 – 0.08 | 0 | 0 | ❌ FAIL |
| Format mix: csv | 0.02 – 0.06 | 0 | 0 | ❌ FAIL |
| Workpaper spreadsheets carrying formulas | ≥ 0.6 | — | 0 | ⚪ ABSENT |
| Version chain length, p90 | ≥ 4 | 5 | — | ✅ PASS |
| Version chain length, max | ≥ 10 | 12 | 12 | ✅ PASS |
| Client deliverables per closed engagement | ≥ 1 | — | 0 | ⚪ ABSENT |
| Announced deliverables actually attached | ≥ 0.9 | 0 | 0 | ❌ FAIL |

## email

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Emails per day, firm-wide | 60 – 120 | 21.62 | 21.8 | ❌ FAIL |
| Thread depth, median | 1.5 – 3 | 4 | 5 | ❌ FAIL |
| Thread depth, p90 | ≥ 5 | 11 | 9 | ✅ PASS |
| Thread depth, max | 20 – 24 | 13 | 13 | ❌ FAIL |
| Attachment rate, external mail | 0.15 – 0.25 | 0 | 0 | ❌ FAIL |
| Attachment rate, internal mail | 0.05 – 0.12 | 0 | 0 | ❌ FAIL |
| Reply latency, median | 1.5 – 6 | 0.08333 | 0.083 | ❌ FAIL |
| Reply latency, p95 | ≥ 24 | 21.08 | 2.3 | ❌ FAIL |
| Replies later than 72h | ≥ 0.03 | 0.01576 | 0 | ❌ FAIL |
| Reply latency fits lognormal (p>alpha) | ≥ 0.01 | 0 | — | ❌ FAIL |
| Reply latency rejects uniform (p<alpha) | ≤ 0.01 | 0 | — | ✅ PASS |
| Body length, median words | 60 – 160 | 102 | — | ✅ PASS |
| Body length, p95 words | ≥ 400 | 209 | — | ❌ FAIL |
| Body length fits lognormal | ≥ 0.01 | 5.957e-06 | — | ❌ FAIL |
| Single-recipient share | ≥ 0.6 | 0.5912 | — | ❌ FAIL |
| Messages carrying cc | 0.15 – 0.3 | 0.2339 | — | ✅ PASS |
| Internal-only share | 0.45 – 0.65 | 0.01509 | — | ❌ FAIL |
| Machine/notification share | 0.03 – 0.1 | 0 | 0 | ❌ FAIL |
| Distinct bodies | ≥ 0.95 | 0.9967 | 0.997 | ✅ PASS |
| Gini, mail by sender | 0.3 – 0.55 | 0.4496 | — | ✅ PASS |
| Top sender share | ≤ 0.45 | 0.1913 | 0.191 | ✅ PASS |

## slack

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Channels carrying messages | ≥ 12 | 1 | 1 | ❌ FAIL |
| Top channel share | 0.25 – 0.45 | 1 | 1 | ❌ FAIL |
| DM share of messages | 0.15 – 0.35 | 0 | 0 | ❌ FAIL |
| Threads with 2+ replies | ≥ 0.3 | 0 | — | ❌ FAIL |
| Messages with no reaction | ≥ 0.4 | 0.8513 | — | ✅ PASS |
| Off-hours messages | 0.05 – 0.12 | 0 | — | ❌ FAIL |
| Off-hours messages, Feb-Apr | ≥ 0.15 | 0 | — | ❌ FAIL |
| Gini, messages by channel | 0.35 – 0.65 | 0 | — | ❌ FAIL |

## tax

| Metric | Band | Observed | v1 | Verdict |
|---|---|---|---|---|
| Returns per entity client | ≥ 1 | — | 0 | ⚪ ABSENT |
| Filings in the Apr 10-15 window | ≥ 0.25 | — | — | ⚪ ABSENT |
| Returns extended | 0.08 – 0.2 | — | — | ⚪ ABSENT |
| Filings acknowledged within 3 days | ≥ 0.95 | — | — | ⚪ ABSENT |
| Off-season notices | ≥ 5 | — | — | ⚪ ABSENT |


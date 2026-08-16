# Staffing leverage review

You are the practice manager at **Ashgrove Reid LLP**, an audit and
assurance firm. Before next quarter's staffing plan the partners want to
see how the work is distributed: which engagements are carried by
seniors and staff, and which are absorbing too much partner and manager
time to be profitable.

Systems available through tools: **clio** (engagements, time activities,
people and their titles), **gmail**, **slack**, **calendar**, **imanage**.

## What to produce

One file: **`leverage.json`**, with exactly these fields:

- `engagements_reviewed` — client engagements covered.
- `firm_leverage_ratio` — across all client engagements, delivery hours
  ÷ review hours, 2 dp.
- `over_supervised` — sorted ticket ids where review hours exceed **40%**
  of the engagement's delivery+review hours.
- `engagements` — one entry per client engagement, sorted by
  `engagement`: `engagement` (the engagement's display number, as clio
  shows it — for example `00005-Mensah`), `partner_hours`, `manager_hours`,
  `senior_hours`, `staff_hours`, `support_hours` (each 2 dp),
  `leverage_ratio` (2 dp, or `null` if there are no review hours),
  `review_share_pct` (1 dp).

## How the firm classifies people

Every person's tier comes from their title:

- **partner** — Managing Partner; Partner, Client Accounting & Advisory;
  Principal, Assurance
- **manager** — Audit Manager; Tax Manager; Client Accounting Lead
- **senior** — Senior Accountant, Assurance; Senior Accountant, Tax
- **staff** — Staff Accountant; Payroll Specialist
- **support** — Office & Billing Manager; Admin Coordinator; IT
  Administrator

**Delivery hours** are senior + staff. **Review hours** are partner +
manager. **Support hours are neither** — report them, but leave them out
of both ratios and out of `review_share_pct`.

An engagement is client work when it has a client. The firm's own
engagements — peer review, methodology, internal administration — carry
no client and are excluded entirely. All hours count here, billable or
not.

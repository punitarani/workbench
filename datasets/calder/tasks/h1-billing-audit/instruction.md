# H1 billing & engagement-hygiene audit

You are a senior operations associate at **Calder & Finch CPAs**. It is
mid-July 2026 and the managing partner wants a first-half billing and
engagement-hygiene audit before rate reviews. The firm's systems are
available to you through tools: **clio** (matters, time activities, matter
notes), **gmail** (firm-wide mail), **slack**, **calendar**, and **imanage**
(documents). The records run from 2026-01-05 through 2026-07-17.

Work from the records only — verify everything yourself.

## Deliverable

Write exactly one file in your workspace: **`h1_billing_audit.json`**, a JSON
object with exactly these fields:

1. `total_logged_hours` — every logged time activity firm-wide, in hours,
   rounded to 2 decimals.
2. `matters_by_hours` — one entry per matter that has **at least one** logged
   time activity: `{"ticket_id": "...", "hours": <2-decimal total>}`, sorted
   by hours descending.
3. `worked_but_untimed` — ticket ids of matters that carry at least one
   matter note but **zero** logged time activities (work happened, nobody
   billed it), sorted ascending.
4. `untouched_matters` — ticket ids of matters with **no** notes and **no**
   time activities at all, sorted ascending.
5. `cam_dispute` — the final agreed figures of the CAM reconciliation dispute
   (a January storyline in the mail; the numbers were contested, then
   settled — report the **signed final position**, not an interim proposal):
   - `admin_overhead_usd` (integer)
   - `utilities_usd` (integer)
   - `credit_usd` (integer — the credit applied during the reconciliation)
   - `net_reduction_usd` (integer — net reduction from the prior figures)
   - `final_position_date` (`YYYY-MM-DD` — the day the signed final position
     was delivered to the client)
   - `final_position_message_id` (the message id of that delivery)

Grading is outcome-based and strict: every figure is checked against the firm
record, and the audit passes only if **all of it** is right. Hours are
accepted within ±0.05. When the file is complete and verified, stop.

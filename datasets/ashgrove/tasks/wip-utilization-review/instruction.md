# WIP and utilization review

You are the finance manager at **Ashgrove Reid LLP**, an audit and
assurance practice. The partners want the work-in-progress position and
the team's utilization before they set next quarter's staffing.

The firm's systems are available through tools: **clio** (engagements,
time activities, people), **gmail**, **slack**, **calendar**, and
**imanage**.

## What to produce

One file in your workspace: **`wip_review.json`**, with exactly these
fields:

- `client_engagements` — how many engagements are billable client work.
- `internal_engagements` — how many the firm opened on itself.
- `total_client_wip_dollars` — unbilled work-in-progress across client
  engagements, in dollars, 2 decimals.
- `blended_rate_dollars_per_hour` — total client WIP divided by the
  billable hours behind it, 2 decimals.
- `engagements` — one entry per **client** engagement, sorted by
  `engagement`: `engagement` (the engagement's display number, as clio
  shows it — for example `00005-Mensah`), `billable_hours` (2 dp),
  `wip_dollars` (2 dp), `staff_count` (distinct people who logged any
  time to it, billable or not). Include every client engagement, even one
  with no time logged against it yet — it belongs on the list at zero.
- `people` — one entry per person who logged any time, sorted by name:
  `name`, `logged_hours` (2 dp), `billable_hours` (2 dp),
  `utilization_pct` (billable ÷ logged × 100, 1 dp).

## How the firm counts

- **WIP is billable time valued at the rate recorded on the entry.**
  Non-billable time is real work and belongs in `logged_hours`, but it
  never carries value.
- **An engagement is client work when it has a client.** The firm's own
  engagements — peer review, methodology, internal administration — carry
  no client, and are excluded from `engagements`, from
  `total_client_wip_dollars`, and from the blended rate. The time people
  spent on them still counts in that person's `logged_hours` and
  utilization.
- **Some people carry no standard rate.** Their time is logged and
  counted in hours, and contributes no dollars.
- Round only at the end, to the stated precision.

Every figure is checked. A single misfiled entry moves several of them.

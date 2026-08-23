# Fixes measured but not applied

Changes inside `_ENGINE_SURFACE` cannot be applied while a recording is in
flight: the fingerprint keys the resume, and editing one of the seven files
means the run in progress can never be continued. So a fix found mid-record
is measured, written down here with its evidence, and applied at the next
restart.

Each entry states what it changes, what it was measured to do, and — the
part that is easy to lose — **what it was measured NOT to do.**

## wake-phase: spread the cohort across the day

`src/simulation/gm/grounded.py`, in the day-planning branch:

```python
# was
slots = quantum // grid
...
wake_delay = plan.day_start + phase * grid

# is
PHASE_STEP = 60                          # module level
slots = max(1, quantum // PHASE_STEP)
...
wake_delay = plan.day_start + phase * PHASE_STEP
```

**The defect.** With `wake_grid_minutes` at 90, every persona whose check
interval is at or below 90 gets `quantum == grid`, so `slots == 1`, so
`phase = seed % 1 = 0`. Measured on v7: **21 personas, 323 distinct wake
timestamps, all 21 on every one.** The firm acts in lockstep seven times a
working day. The phase code executes and cannot return anything but zero.

**Measured to fix:** piloted as a real 3-day recording in an isolated
worktree. 45 timestamps, **one persona on 43 of them** — 09:01, 09:13,
09:14, 09:20, 09:24, 09:34, 09:44, 09:49.

**Measured NOT to fix: reply latency.** The same pilot leaves it at a
median of 0.08 hours, 11 of 12 replies under five minutes, matching the
unfixed world. 21 personas over a 90-minute quantum is a wake every 4.3
minutes, so the next persona is always about to wake whether they are
stacked on one instant or spread across the hour. **A five-minute reply
needs a persona to decline its first opportunity — a response delay drawn
per message — which is a behaviour change, not a scheduling one.**

Expect it to move `slack.offhours_share` (0.034 against ≥0.15) and the
firm's temporal texture generally. Do not expect it to move
`email.reply_latency_median` or `email.thread_depth_median`.

### Piloting a change to a frozen file

Use a git worktree so the running recording's tree is untouched — and run
the pilot with `PYTHONPATH` on the worktree's own `src`. The worktree
symlinks the main `.venv`, whose `workbench.pth` points at the *main* tree,
so without it the pilot imports the unpatched engine and faithfully
reproduces the defect it is meant to fix. The tell is an "after" number
identical to the "before" one.

## calendar front-loading: why 77% of invitations are never answered

`calendar.rsvp_needsaction` reads **0.772** against a band of ≤0.1, and it
has been the largest single band failure all along. It is not a persona
behaviour problem.

Split the 2,731 attendee-invitations on v7 by how far ahead the event is:

    lead time         invitations   answered
    in the past                18       0.0%
    within 14 days            289      65.7%     <- inside the 0.6-0.8 band
    beyond 14 days          2,424      17.7%

**When a persona can see an invitation, it answers at 66% — the realistic
rate the band asks for.** `working_memory._INVITATION_HORIZON` is 14 days,
so anything further out never enters the pending list and cannot be
answered at all. And the median lead time is **85 days**: every occurrence
of every recurring series is created at day zero with its own future start,
so on day one a persona is invited to a meeting three months away.

That reframes the fix. Widening the horizon is the wrong move and the
history says why — the horizon was *added* because an unbounded pending list
had personas working through 113 RSVPs a day and chat collapsing to 0.36x.
The problem is upstream: **create each occurrence near its date rather than
all of them at day zero.**

It also explains why surfacing invitations at all — the earlier fix that
took `needsAction` from 93% to 77% — moved it so little. That fix was
correct and it could only ever reach the 11% of invitations inside the
horizon.

Not applied here because it lives in the workplace compiler and changes the
compiled spec, so the config hash moves and the run in flight cannot be
resumed either way.

**Expect it to move** `rsvp_needsaction`, `rsvp_accepted`, and the
`calendar.event.scheduled` rate's shape over the epoch. **Do not expect it
to move** `rsvp_tentative` or `rsvp_declined`, which are 0.000 and 0.004:
the firm having exactly one RSVP verb is a separate defect, and this one
does not touch it.

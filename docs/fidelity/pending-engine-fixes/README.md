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

# The engine

Ordering guarantees that make runs reproducible — preserve all four:

1. **Mint at occurrence.** The queue holds `ScheduledEvent` drafts ordered
   by `(time, order)`; `seq` is assigned when a draft is popped, so the
   world log stays gapless and time-ordered even for delayed events. Only
   the engine mints `seq` and `order`.
2. **Fan-out is `asyncio.gather` in declaration order.** Never
   `as_completed`, never completion-order accumulation. Results pair with
   entities by index.
3. **Shared state mutates only between gathers.** Queue, log, attention,
   and counters are touched by the engine loop, never inside concurrently
   running entity tasks.
4. **Windowed admission takes a canonical prefix.** Admission scans the
   queue in `(time, order)` order and stops at the first conflict, so the
   world log is byte-identical at every window size.

Every field of engine state must round-trip through `capture_state` /
`restore_state` — the split-run tests (run N, kill, resume, byte-compare
against the straight run; the epoch acceptance kills at an arbitrary
step) are the arbiter. Adding state without snapshot support breaks
resume silently until those tests catch it.

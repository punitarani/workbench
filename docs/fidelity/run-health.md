# Can this recording finish? Checked at day 23 of 130

A run measured in hours fails for boring reasons, and the expensive ones
fail late. These are the exhaustion risks, projected from 23 recorded days
rather than assumed.

| axis | at day 23 | projected at 130 | headroom |
|---|---|---|---|
| world log | 20 MB, 15,662 events | ~115 MB, ~88,500 events | ample |
| cassette | 252 MB | ~1.4 GB | 70 GiB free |
| LM calls | 8,108 network | ~46,700 | cap is 2,000,000 |
| tokens | 41.1M | ~232M | no cap |
| pace | ~600 steps/day | stable across the last 8 days | — |

The call budget deserves a note: it counts **network** calls, and it is
per-process, so every resume starts it again. Two million was never going
to bind. Worth checking anyway — the engine raises on budget exhaustion
rather than degrading, by design, so a cap set carelessly would kill the run
near the end rather than warn early.

## Two rejection numbers that are not the same number

Telemetry reports **405 rejections over 14,407 events, 2.81%**, which sits
alarmingly close to the 3% limit in the attempted-work gate. They are
different measurements and confusing them would be an easy way to panic, or
worse, to relax a gate that is not failing.

*Referee rejections* are the designed loop: a persona proposes an intent the
referee cannot ground, gets a reason back, and works forward. The work is
not lost — it is redirected. Around 3–5% a day is healthy traffic.

*Dropped entries* are what the gate measures: work a persona attempted that
was silently discarded, which is invisible loss and reads as a model that
never tried. Measured across 410 GM notes: **0 dropped entries, 0 unknown
references.** The gate is at zero, not at 2.81%.

The general shape is worth remembering. A rate near a threshold is only
worrying if it is *that* threshold's rate. Two plausible numerators over the
same denominator will happily produce a number that looks like the metric
you care about.

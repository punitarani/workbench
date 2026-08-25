# mail-promise-register — MEASURED AT CEILING, kept as evidence

opus-5 scores **1.000** on this task. It is correct, both derivations
agree, and it measures nothing about a frontier tier. It is kept because
what it rules out is worth more than the task would have been.

## What it was for

The one design family that lands in band -- an attachment rule over prose,
plus supersession -- ported to a second surface. The rule ported exactly:
`promise_rule` fires on 61 of 1,399 mail bodies against 175 of 2,872
meeting turns, and the two derivations agree on both. **The difficulty did
not port.**

## Why not

The grouping key here is a column. `sender` is a field on the message, so
the agent groups by it and takes the max -- and it did: 530 messages pulled
in twelve `search_threads` calls, then 118 shell commands. Rows-per-owner
is 1.00, which means the row set is "enumerate the people who promised" and
only the value is ever at stake.

The meetings register cannot be grouped without first computing the
grouping: of 52 distinct titles across 567 meetings, a title is a standing
series only if it appears on three or more days, and 44 of the 52 are
one-offs that make no rows. An error there merges or drops a GROUP, which
changes the row set rather than a field.

## Why it was not redesigned

Two candidate fixes were measured and both fail on this corpus:

**Group by (sender, thread), or by normalised subject.** Supersession
collapses: 2% of pairs change their date inside a thread, 0% inside a
subject. This firm opens a new thread rather than re-promising in an old
one, so the register would have nothing to supersede -- and the rows would
all still look right.

**Group by matter.** Only 15% of messages name a matter's client at all,
and several name more than one. The join the register would rest on is not
in the corpus.

**Group by recurring subject** gives a derived key (rows-per-owner 1.43)
but three of its groups are near-identical pairs that both carry
commitments -- `patent filing deadline - status?` against `patent filing
deadline — status?`, differing by an em-dash. Exact-string grouping calls
those two conversations. A reader calls them one. Grading that difference
is a gotcha, not comprehension.

So the surface hosts the rule and cannot host the family. That is a fact
about the corpus, and the register is the evidence for it.

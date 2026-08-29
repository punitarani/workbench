# The five rows the models declined and the key was right about

`certify` refused `delegation/assignment-revision-register` on rows every
trial of every tier declined. With the heaviest criterion at 0.75 those are
evidence rather than arithmetic — the tiers find three rows in four, so a
row all nine trials miss is worth reading.

Fifteen rows were read over three passes. **Ten were oracle defects and
five are correct**, which is close to the base rate this tree has seen
(four of five unanimous disagreements have been the key). The ten are fixed
in the rule and its checker; these five are model failures and are waived
here so the waiver is auditable rather than asserted.

## The five

| row | the sentence |
|---|---|
| Teodor Vasiliev \| IP and technology group | *"Teodor **owes** me the transfer agreements and consent templates, he committed to a firm date by EOD today and documents **by EOD tomorrow**"* |
| Roland Pesch \| Employment practice huddle | *"**Roland has** the updated Renwick memo and **owes** me a decision on the cease-and-desist **by end of day Wednesday**"* |
| Saoirse Mulvaney \| Partner matter review | *"associate drafts, you review, **Saoirse has it end of day tomorrow**"* |
| Clement Abioye \| Employment practice huddle | *"**Clement owes** me the org chart and driver/complaint list **by Tuesday EOD**"* |
| Marguerite Oyelaran \| Partner matter review | *"**Marguerite has it before Friday**, that's the itemized document I already finalized"* |

Every one names a colleague from the roster, an obligation verb the brief
lists, and a day attached to it. None carries a negation, a condition, a
gate, a transfer, a second subject, or a past tense. They are the plainest
form the family has.

## Why the models miss them

They are not hard sentences; they are hard to *find*. Each sits inside a
turn of two hundred words that also carries the speaker's own commitments,
a status report on somebody else, and one or two dates belonging to
neither. The task's difficulty is that the owner of a row is never the
person speaking, so every turn has to be read for somebody else's name
while the speaker's own promises are the loudest thing in it.

That is the capability being measured, and missing these is a fair way to
fail it.

## The ten that were defects

Fixed rather than waived, each with the sentence that exposed it:

- `until` after a state verb — *"Clement's matter **is contained until** Thursday 2pm"*
- a transfer verb — *"so that **escalates to Bennett** tomorrow"*
- a possessive naming an event — *"owed by **Thursday's 2pm call**"*
- a past verb — *"Oskar's side is done, he **signed off** Monday"*
- a negation — *"Fionnuala **has not** given written confirmation"*
- `since` — *"Samir owns that, **no update since Tuesday**"*
- a gate — *"**Once** Imelda has a firm date tomorrow"*
- a scheduled event — *"**Marguerite's call is Friday**, not today"*
- a fronted day — *"and **Thursday 2pm we finalize**"* and *"**Thursday 2pm is when we finalize**"*
- a leading condition — *"**if** Teodor is expecting movement before Thursday"*

Reproduce:

    uv run python scripts/certify.py --dataset delegation \
        --task assignment-revision-register \
        --tag opus-a1-k3 --tag glm-a1-k3 --tag kimi-a1-k3 \
        --waive "Teodor Vasiliev | IP and technology group" \
        --waive "Roland Pesch | Employment practice huddle" \
        --waive "Saoirse Mulvaney | Partner matter review" \
        --waive "Clement Abioye | Employment practice huddle" \
        --waive "Marguerite Oyelaran | Partner matter review"

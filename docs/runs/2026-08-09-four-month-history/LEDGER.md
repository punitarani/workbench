# Hartwell spend ledger

Hard project cap: `$25.00` of OpenRouter usage after the recorded
`32.2139`-credit baseline. Required pre-launch reserve: `$1.50`.

The credits endpoint is authoritative. Token-times-list-price estimates from
the earlier run were discarded because cached prompt reads made them materially
wrong.

## Authoritative checkpoints

| Point | Meter total_usage | Spend since baseline | Notes |
|---|---:|---:|---|
| recorded project baseline | 32.213900000 | 0.000000000 | cap origin |
| before final Harbor routing work | 44.330760849 | 12.116860849 | prior generation, legacy probes, and pilots reconciled |
| after run A settled | 45.572103713 | 13.358203713 | remote-compaction `invalid_prompt`; invalid trials |
| after run B settled | 47.050413805 | 14.836513805 | unsupported `/responses/compact`; invalid DeepSeek |
| after run C smoke settled | 49.358639206 | 17.144739206 | valid Luna; GLM/DeepSeek timed out and invalid |
| before additional fee batch | 50.722100267 | 18.508200267 | targeted valid GLM/DeepSeek recovery settled |
| final settled reading | 56.005689513 | 23.791789513 | six valid additional fee attempts |

Final remaining budget before cap: `$1.208210487`.

Final launchable budget after the required reserve:
`$1.208210487 - $1.50 = -$0.291789513`.

No later task batch was launched.

## Final-phase deltas

| Work | Settled cost | Valid evaluation output |
|---|---:|---|
| run A | $1.241342864 | none; remote compaction rejected |
| run B | $1.478310092 | Luna/GLM diagnostics only; run invalid because DeepSeek used unsupported compact endpoint |
| run C initial smoke | $2.308225401 | Luna 1.0/1.0; GLM/DeepSeek invalid 1,800-second timeouts |
| targeted GLM/DeepSeek recovery | $1.363461061 | GLM 0.8432/1.0; DeepSeek 0.6416/0.8625 |
| six additional fee attempts | $5.283589246 | all six valid; completes fee 3x3 |

The final-phase total is `$11.674928664`. Earlier reconciled project work was
`$12.116860849`, producing the final `$23.791789513` total.

## Budget decision

The additional fee launch was authorized when the meter read
`50.722100267`; its `$3.50` operator projection fit under the cap and reserve,
but the settled cost was `$5.283589246`. It remained below the hard cap but
consumed the reserve. Commit `dd6e11f` prevents recurrence by normalizing every
observed launch cost to a full nine-cell task batch, then scaling that forecast
to the exact size of the next launch.

The seven remaining task matrices and eight model-based `harbor check` calls
are unpaid and unrun. Their absence is not represented as a zero model score.

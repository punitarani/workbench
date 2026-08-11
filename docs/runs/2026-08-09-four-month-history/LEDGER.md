# Hartwell spend ledger

OpenRouter's credits endpoint is authoritative. Token-count estimates are not
used because cached reads and provider routing make them materially inaccurate.
Every launch must retain a `$1.50` reserve.

## Original authorization

The original project authorization was `$25.00` after the recorded
`32.213900000` usage baseline. That phase ended at `56.005689513`, or
`$23.791789513` of metered usage. Its fee-dispute matrix and invalid-run history
remain documented in `REPORT.md` and `FAILURE-MODES.md`.

Post-ledger Harbor pilots settled before the continuation was authorized. The
new authorization therefore starts from the then-current meter, not from the
older report's final value.

## 2026-08-11 continuation authorization

- settled continuation baseline: `64.274128970`;
- additional authorized usage: `$25.00`;
- continuation cap: `89.274128970`;
- required reserve: `$1.50`.

| Point | Meter `total_usage` | Spend since continuation | Notes |
|---|---:|---:|---|
| continuation baseline | 64.274128970 | 0.000000000 | user-authorized start |
| standard-drift settled | 67.686196267 | 3.412067297 | nine valid diagnostic cells |
| operative-deadline settled | 71.257129322 | 6.983000352 | nine valid diagnostic cells |
| second-read live stop | 83.258674679 | 18.984545709 | six long cells cancelled to protect cap |
| second-read final settlement | 84.197153415 | 19.923024445 | delayed provider settlement stabilized |

Final continuation budget:

- remaining before cap: `$5.076975555`;
- launchable after reserve: `$3.576975555`.

No additional paid launch is authorized: the observed cost of the interrupted
second-read batch was `$12.940024093`, so the remaining amount cannot safely
cover a full nine-cell task batch.

## Continuation work by batch

| Work | Settled cost | Valid output |
|---|---:|---|
| standard-drift diagnostic 3x3 | $3.412067297 | 9/9 valid; task too easy |
| operative-deadline diagnostic 3x3 | $3.570933055 | 9/9 valid; only GLM best-of-three below 0.5 |
| second-read evidence-ledger batch | $12.940024093 | 3 valid Luna cells; 6 cancelled GLM/DeepSeek cells excluded |

The second-read launch was admitted with a `$4.00` full-batch forecast based on
the preceding settled batches. After 37 minutes, a live manual meter check
showed `$11.94` of in-flight usage. The run was interrupted before the reserve
was consumed; delayed settlement added another `$1.00`.

Commit `8e47e9c` closes that gap. Paid commands now run in a dedicated process
group while the authoritative meter is polled every 30 seconds. The runner
terminates the full process group when observed in-flight cost exceeds the
launch's authorized forecast or reaches the pre-reserve limit, then persists a
typed budget failure. Pre-launch and post-launch checks remain in place.

## Budget rule

Before resuming paid work:

1. obtain a new explicit authorization;
2. query and record a new settled baseline;
3. retain the `$1.50` reserve;
4. use an observed worst-case forecast no lower than `$12.9401` for a full
   long-ledger batch unless a cheaper identical-protocol batch establishes a
   defensible lower bound;
5. never count cancelled, timeout, setup, provider, MCP, verifier, or meter
   failures as model scores.

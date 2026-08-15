# ADR-0002 — Statistics for the realism suite: stdlib, not scipy

Status: accepted · Date: 2026-08-14

## Context

The v2 realism suite needs KS tests against distribution families,
chi-square for categorical mixes, Gini and Shannon entropy for
concentration, autocorrelation and day/hour profile checks, and Spearman
correlation for cross-surface coupling.

The repo ships deliberately lean: `pydantic`, `mcp`, `httpx`, with
`dspy` and the office renderers as optional extras — and the agent
container installs the **base project only** to keep task images small.
Adding numpy/scipy to the base is off the table; adding them to the dev
group is possible but pulls large platform-specific wheels into CI.

House style already favors hand-rolled deterministic arithmetic where
determinism matters (retrieval scoring is integer-only, no floats, to
guarantee byte-identity).

## Decision

Implement `workbench/analysis/stats.py` in **pure stdlib**: two-sample
and one-sample KS statistic with the asymptotic Kolmogorov p-value,
chi-square with the regularized incomplete gamma for p-values, Gini,
Shannon entropy, lag-k autocorrelation, and Spearman ρ. No new runtime
or test dependencies.

## Consequences

- CI stays light and platform-independent; no wheel-availability risk
  (the repo already carries a litellm pin for exactly that reason).
- Hand-rolled p-values are approximations. Acceptable because the suite
  asserts **committed bands and reject/not-reject at α=0.01**, not
  published p-values; and the same code runs identically everywhere.
- The stats module needs its own unit tests against known-answer
  fixtures (textbook examples with published statistics) so we can trust
  the implementations before trusting the suite that uses them.
- **Fallback:** if a metric proves genuinely sensitive to p-value
  precision, add scipy to the dev group only and port that metric.

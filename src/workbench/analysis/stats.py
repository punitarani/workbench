"""Distribution statistics in pure stdlib (ADR-0002).

Everything the realism suite needs to answer "is this shaped like the
real thing": goodness-of-fit against a named family, categorical mix
tests, concentration, dispersion, and cross-surface coupling. No numpy,
no scipy — the repo ships lean dependencies and the agent container
installs the base project only, so a test dependency that pulls
platform-specific wheels is a cost we decline to pay.

The p-values here are the standard asymptotic approximations
(Kolmogorov series for KS, regularized incomplete gamma for chi-square).
They are accurate to well within the resolution of a band check at
alpha=0.01, which is the only thing this module is used for. They are
not a substitute for scipy if you ever need a publishable p-value.

One statistical caveat, stated rather than hidden: ``ks_lognormal`` and
friends fit their parameters from the same sample they test, which makes
the KS statistic conservative (a Lilliefors situation). For our purpose —
"does this look lognormal rather than flat" — that bias is acceptable and
errs toward accepting, so a *rejection* is meaningful and a
non-rejection is weak evidence. The anti-uniformity assertion is what
carries the weight: real data rejects uniform, machine filler does not.
"""

import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence

_EPS = 3.0e-12
_TINY = 1.0e-300
_MAX_ITERATIONS = 500


# --- special functions -------------------------------------------------


def regularized_gamma_p(a: float, x: float) -> float:
    """Regularized lower incomplete gamma P(a, x) = γ(a, x) / Γ(a)."""

    if a <= 0.0:
        raise ValueError("a must be positive")
    if x < 0.0:
        raise ValueError("x must be non-negative")
    if x == 0.0:
        return 0.0
    if x < a + 1.0:
        # Series representation converges fast on this side.
        total = 1.0 / a
        term = total
        divisor = a
        for _ in range(_MAX_ITERATIONS):
            divisor += 1.0
            term *= x / divisor
            total += term
            if abs(term) < abs(total) * _EPS:
                break
        return total * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # Continued fraction for Q(a, x), then complement.
    b = x + 1.0 - a
    c = 1.0 / _TINY
    d = 1.0 / b
    h = d
    for index in range(1, _MAX_ITERATIONS + 1):
        an = -index * (index - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _TINY:
            d = _TINY
        c = b + an / c
        if abs(c) < _TINY:
            c = _TINY
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    q = math.exp(-x + a * math.log(x) - math.lgamma(a)) * h
    return 1.0 - q


def kolmogorov_sf(lam: float) -> float:
    """P(K > lam) for the Kolmogorov distribution: 2 Σ (-1)^(k-1) e^(-2k²λ²)."""

    if lam <= 0.0:
        return 1.0
    total = 0.0
    for k in range(1, 101):
        term = math.exp(-2.0 * k * k * lam * lam)
        total += term if k % 2 else -term
        if term < 1e-15:
            break
    return min(1.0, max(0.0, 2.0 * total))


# --- goodness of fit ---------------------------------------------------


def ks_statistic(sample: Sequence[float], cdf) -> float:
    """One-sample Kolmogorov–Smirnov statistic against a callable CDF."""

    values = sorted(float(v) for v in sample)
    if not values:
        raise ValueError("empty sample")
    n = len(values)
    largest = 0.0
    for index, value in enumerate(values):
        expected = cdf(value)
        below = index / n
        above = (index + 1) / n
        largest = max(largest, abs(expected - below), abs(above - expected))
    return largest


def ks_pvalue(statistic: float, n: int) -> float:
    """Asymptotic p-value for a one-sample KS statistic."""

    if n <= 0:
        raise ValueError("n must be positive")
    root = math.sqrt(n)
    return kolmogorov_sf((root + 0.12 + 0.11 / root) * statistic)


def ks_test(sample: Sequence[float], cdf) -> tuple[float, float]:
    """(statistic, p-value) against a callable CDF."""

    statistic = ks_statistic(sample, cdf)
    return statistic, ks_pvalue(statistic, len(sample))


def ks_two_sample(a: Sequence[float], b: Sequence[float]) -> tuple[float, float]:
    """(statistic, p-value) for two empirical distributions."""

    left = sorted(float(v) for v in a)
    right = sorted(float(v) for v in b)
    if not left or not right:
        raise ValueError("both samples must be non-empty")
    i = j = 0
    largest = 0.0
    while i < len(left) and j < len(right):
        # Advance *both* sides past the current value before comparing, or a
        # value shared by the two samples registers as a spurious gap.
        value = min(left[i], right[j])
        while i < len(left) and left[i] == value:
            i += 1
        while j < len(right) and right[j] == value:
            j += 1
        largest = max(largest, abs(i / len(left) - j / len(right)))
    effective = len(left) * len(right) / (len(left) + len(right))
    return largest, ks_pvalue(largest, max(1, round(effective)))


def normal_cdf(mu: float, sigma: float):
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")

    def cdf(x: float) -> float:
        return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))

    return cdf


def lognormal_cdf(mu: float, sigma: float):
    """CDF of a lognormal whose *log* has mean mu and stdev sigma."""

    normal = normal_cdf(mu, sigma)

    def cdf(x: float) -> float:
        return 0.0 if x <= 0.0 else normal(math.log(x))

    return cdf


def uniform_cdf(low: float, high: float):
    if high <= low:
        raise ValueError("high must exceed low")

    def cdf(x: float) -> float:
        return min(1.0, max(0.0, (x - low) / (high - low)))

    return cdf


def fit_lognormal(sample: Sequence[float]) -> tuple[float, float]:
    """MLE (mu, sigma) of the underlying normal for positive samples."""

    logs = [math.log(float(v)) for v in sample if float(v) > 0.0]
    if len(logs) < 2:
        raise ValueError("need at least two positive values")
    mu = sum(logs) / len(logs)
    variance = sum((value - mu) ** 2 for value in logs) / len(logs)
    return mu, math.sqrt(variance) if variance > 0 else _EPS


def ks_lognormal(sample: Sequence[float]) -> tuple[float, float]:
    """Fit a lognormal to the sample and KS-test against it."""

    positives = [float(v) for v in sample if float(v) > 0.0]
    mu, sigma = fit_lognormal(positives)
    return ks_test(positives, lognormal_cdf(mu, sigma))


def ks_uniform(sample: Sequence[float]) -> tuple[float, float]:
    """KS against the uniform spanning the sample's own range.

    The anti-uniformity check: real-world magnitudes reject this
    comfortably; machine filler does not.
    """

    values = [float(v) for v in sample]
    low, high = min(values), max(values)
    if high <= low:
        return 1.0, 0.0
    return ks_test(values, uniform_cdf(low, high))


def chi_square(
    observed: Mapping[str, int], expected: Mapping[str, float]
) -> tuple[float, float, int]:
    """(statistic, p-value, degrees of freedom) for a categorical mix.

    ``expected`` may be counts or proportions; proportions are scaled to
    the observed total. Categories present in either mapping are tested.
    """

    categories = sorted(set(observed) | set(expected))
    total_observed = sum(observed.get(name, 0) for name in categories)
    total_expected = sum(expected.get(name, 0.0) for name in categories)
    if total_observed <= 0 or total_expected <= 0:
        raise ValueError("observed and expected must carry mass")
    scale = total_observed / total_expected
    statistic = 0.0
    for name in categories:
        want = expected.get(name, 0.0) * scale
        if want <= 0.0:
            continue
        got = observed.get(name, 0)
        statistic += (got - want) ** 2 / want
    degrees = max(1, len(categories) - 1)
    p = 1.0 - regularized_gamma_p(degrees / 2.0, statistic / 2.0)
    return statistic, p, degrees


# --- concentration and dispersion --------------------------------------


def gini(values: Iterable[float]) -> float:
    """Gini coefficient: 0 = perfectly even, →1 = one entity holds all."""

    ordered = sorted(float(v) for v in values)
    if not ordered:
        raise ValueError("empty input")
    if any(value < 0 for value in ordered):
        raise ValueError("gini is undefined for negative values")
    total = sum(ordered)
    if total == 0:
        return 0.0
    n = len(ordered)
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    return (2.0 * weighted) / (n * total) - (n + 1.0) / n


def top_share(values: Iterable[float], k: int = 1) -> float:
    """Fraction of the total held by the k largest entities."""

    ordered = sorted((float(v) for v in values), reverse=True)
    if not ordered:
        raise ValueError("empty input")
    total = sum(ordered)
    return 0.0 if total == 0 else sum(ordered[:k]) / total


def shannon_entropy(counts: Iterable[float], *, normalized: bool = True) -> float:
    """Entropy of a categorical distribution, optionally scaled to [0, 1]."""

    values = [float(v) for v in counts if float(v) > 0.0]
    if not values:
        raise ValueError("empty input")
    total = sum(values)
    entropy = -sum((v / total) * math.log(v / total) for v in values)
    if not normalized:
        return entropy
    ceiling = math.log(len(values))
    # One occupied category carries no uncertainty: maximally concentrated,
    # which is 0 on the normalized scale (the 0/0 case decided deliberately).
    return 0.0 if ceiling == 0 else entropy / ceiling


def quantile(sample: Sequence[float], q: float) -> float:
    """Linear-interpolated quantile (same convention as numpy's default)."""

    if not 0.0 <= q <= 1.0:
        raise ValueError("q must be in [0, 1]")
    ordered = sorted(float(v) for v in sample)
    if not ordered:
        raise ValueError("empty sample")
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[int(position)]
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def round_number_share(sample: Sequence[float], step: float) -> float:
    """Fraction of values landing exactly on a multiple of ``step``.

    The machine-uniformity tell: humans log 0.4 and 1.3 hours, generators
    log 0.5 and 1.5.
    """

    values = [float(v) for v in sample]
    if not values:
        raise ValueError("empty sample")
    hits = sum(1 for v in values if abs(v / step - round(v / step)) < 1e-9)
    return hits / len(values)


# --- association -------------------------------------------------------


def _ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        stop = index
        while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
            stop += 1
        average = (index + stop) / 2.0 + 1.0
        for position in range(index, stop + 1):
            ranks[order[position]] = average
        index = stop + 1
    return ranks


def pearson(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("series must be the same length")
    if len(a) < 2:
        raise ValueError("need at least two points")
    mean_a = sum(a) / len(a)
    mean_b = sum(b) / len(b)
    covariance = sum((x - mean_a) * (y - mean_b) for x, y in zip(a, b, strict=True))
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_b = sum((y - mean_b) ** 2 for y in b)
    if var_a == 0 or var_b == 0:
        return 0.0
    return covariance / math.sqrt(var_a * var_b)


def spearman(a: Sequence[float], b: Sequence[float]) -> float:
    """Rank correlation, tie-corrected — the cross-surface coupling test."""

    return pearson(_ranks(list(a)), _ranks(list(b)))


def autocorrelation(series: Sequence[float], lag: int = 1) -> float:
    """Lag-k autocorrelation of a time series."""

    if lag <= 0:
        raise ValueError("lag must be positive")
    if len(series) <= lag + 1:
        raise ValueError("series is too short for this lag")
    return pearson(series[:-lag], series[lag:])


def categorical_counts(labels: Iterable[str]) -> dict[str, int]:
    return dict(Counter(labels))

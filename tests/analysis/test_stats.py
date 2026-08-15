"""Known-answer tests for the stdlib statistics module.

ADR-0002 trades scipy for hand-rolled implementations, so the realism
suite is only as trustworthy as this file. Every case here has an
independently known answer: a closed form, a textbook critical value, or
a hand-computed statistic.
"""

import math

import pytest

from workbench.analysis import stats


class TestSpecialFunctions:
    @pytest.mark.parametrize("x", [0.1, 0.5, 1.0, 2.5, 7.0])
    def test_gamma_p_with_a_one_is_the_exponential_cdf(self, x: float) -> None:
        # P(1, x) = 1 - e^-x exactly.
        assert stats.regularized_gamma_p(1.0, x) == pytest.approx(
            1.0 - math.exp(-x), abs=1e-10
        )

    @pytest.mark.parametrize("x", [0.05, 0.5, 1.0, 3.0])
    def test_gamma_p_with_a_half_is_the_error_function(self, x: float) -> None:
        # P(1/2, x) = erf(sqrt(x)) exactly.
        assert stats.regularized_gamma_p(0.5, x) == pytest.approx(
            math.erf(math.sqrt(x)), abs=1e-10
        )

    def test_gamma_p_is_zero_at_the_origin_and_saturates(self) -> None:
        assert stats.regularized_gamma_p(2.0, 0.0) == 0.0
        assert stats.regularized_gamma_p(2.0, 200.0) == pytest.approx(1.0, abs=1e-12)

    def test_kolmogorov_survival_bounds(self) -> None:
        assert stats.kolmogorov_sf(0.0) == 1.0
        # Series evaluated by hand: 2(e^-3.6992 - e^-14.797 + ...) = 0.04949,
        # which is the familiar 1.36 -> ~5% KS critical point.
        assert stats.kolmogorov_sf(1.36) == pytest.approx(0.04949, abs=1e-5)
        # 2(e^-5.3138 - ...) = 0.009846, the ~1% point.
        assert stats.kolmogorov_sf(1.63) == pytest.approx(0.00985, abs=1e-5)


class TestChiSquare:
    @pytest.mark.parametrize(
        ("statistic", "degrees"),
        [(3.841, 1), (5.991, 2), (7.815, 3), (11.070, 5)],
    )
    def test_critical_values_land_at_five_percent(
        self, statistic: float, degrees: int
    ) -> None:
        # Textbook 0.05 critical values: the survival function must agree.
        p = 1.0 - stats.regularized_gamma_p(degrees / 2.0, statistic / 2.0)
        assert p == pytest.approx(0.05, abs=1e-3)

    def test_perfect_match_has_zero_statistic(self) -> None:
        observed = {"a": 30, "b": 20, "c": 50}
        statistic, p, degrees = stats.chi_square(observed, {"a": 3, "b": 2, "c": 5})
        assert statistic == pytest.approx(0.0)
        assert p == pytest.approx(1.0)
        assert degrees == 2

    def test_hand_computed_statistic(self) -> None:
        # Observed 10/20/30 against equal expectation of 20 each:
        # (100 + 0 + 100) / 20 = 10.0 on 2 degrees of freedom.
        statistic, p, degrees = stats.chi_square(
            {"a": 10, "b": 20, "c": 30}, {"a": 1, "b": 1, "c": 1}
        )
        assert statistic == pytest.approx(10.0)
        assert degrees == 2
        assert p == pytest.approx(0.0067, abs=1e-3)

    def test_expected_may_be_proportions_or_counts(self) -> None:
        observed = {"x": 60, "y": 40}
        by_proportion = stats.chi_square(observed, {"x": 0.5, "y": 0.5})
        by_count = stats.chi_square(observed, {"x": 500, "y": 500})
        assert by_proportion == by_count


class TestKolmogorovSmirnov:
    def test_hand_computed_statistic_against_uniform(self) -> None:
        # D = 0.2 by hand for this sample against U(0,1).
        sample = [0.1, 0.2, 0.5, 0.7, 0.9]
        statistic = stats.ks_statistic(sample, stats.uniform_cdf(0.0, 1.0))
        assert statistic == pytest.approx(0.2)

    def test_identical_samples_have_zero_two_sample_statistic(self) -> None:
        sample = [1.0, 2.0, 3.0, 4.0]
        statistic, p = stats.ks_two_sample(sample, sample)
        assert statistic == pytest.approx(0.0)
        assert p == pytest.approx(1.0)

    def test_disjoint_samples_saturate(self) -> None:
        statistic, p = stats.ks_two_sample([1.0, 2.0], [90.0, 91.0])
        assert statistic == pytest.approx(1.0)
        assert p < 0.2

    def test_lognormal_sample_fits_lognormal_and_rejects_uniform(self) -> None:
        # Deterministic lognormal-ish sample: exp of an even normal grid.
        logs = [(index - 40) / 12.0 for index in range(81)]
        sample = [math.exp(value) for value in logs]
        _, fitted_p = stats.ks_lognormal(sample)
        _, uniform_p = stats.ks_uniform(sample)
        assert fitted_p > 0.01, "a lognormal sample must not reject lognormal"
        assert uniform_p < 0.01, "a lognormal sample must reject uniform"

    def test_flat_sample_fails_the_anti_uniformity_check(self) -> None:
        # The machine-filler signature: evenly spaced values.
        sample = [float(index) for index in range(1, 101)]
        _, uniform_p = stats.ks_uniform(sample)
        assert uniform_p > 0.01, "an even ramp cannot reject uniform"

    def test_fit_lognormal_recovers_its_parameters(self) -> None:
        mu, sigma = 1.5, 0.4
        # Symmetric grid in log space: the MLE mean is exactly mu.
        logs = [mu + sigma * (index - 20) / 10.0 for index in range(41)]
        fitted_mu, fitted_sigma = stats.fit_lognormal(
            [math.exp(value) for value in logs]
        )
        assert fitted_mu == pytest.approx(mu, abs=1e-9)
        assert fitted_sigma > 0.0


class TestConcentration:
    def test_gini_of_equal_shares_is_zero(self) -> None:
        assert stats.gini([5, 5, 5, 5]) == pytest.approx(0.0)

    def test_gini_of_total_concentration_is_the_known_maximum(self) -> None:
        # For n entities the maximum is (n-1)/n.
        assert stats.gini([0, 0, 0, 1]) == pytest.approx(0.75)
        assert stats.gini([0] * 9 + [1]) == pytest.approx(0.9)

    def test_gini_hand_computed(self) -> None:
        # [1, 2, 3, 4]: 2*(1+4+9+16)/(4*10) - 5/4 = 30/40*2... computed by hand
        # as 2*30/(4*10) - 1.25 = 1.5 - 1.25 = 0.25.
        assert stats.gini([1, 2, 3, 4]) == pytest.approx(0.25)

    def test_gini_rejects_negative_values(self) -> None:
        with pytest.raises(ValueError):
            stats.gini([1, -1])

    def test_top_share(self) -> None:
        assert stats.top_share([1, 1, 1, 1]) == pytest.approx(0.25)
        assert stats.top_share([10, 1, 1], k=1) == pytest.approx(10 / 12)
        assert stats.top_share([4, 3, 2, 1], k=2) == pytest.approx(0.7)

    def test_entropy_extremes(self) -> None:
        assert stats.shannon_entropy([1, 1, 1, 1]) == pytest.approx(1.0)
        # A single occupied category is maximal concentration, not maximal
        # diversity — the deliberate 0/0 convention.
        assert stats.shannon_entropy([7]) == pytest.approx(0.0)
        assert stats.shannon_entropy([1, 1], normalized=False) == pytest.approx(
            math.log(2)
        )

    def test_quantile_matches_linear_interpolation(self) -> None:
        assert stats.quantile([1, 2, 3, 4], 0.5) == pytest.approx(2.5)
        assert stats.quantile([1, 2, 3, 4], 0.0) == pytest.approx(1.0)
        assert stats.quantile([1, 2, 3, 4], 1.0) == pytest.approx(4.0)
        assert stats.quantile([1, 2, 3, 4, 5], 0.25) == pytest.approx(2.0)

    def test_round_number_share(self) -> None:
        assert stats.round_number_share([0.5, 1.0, 0.3], 0.5) == pytest.approx(2 / 3)
        assert stats.round_number_share([0.1, 0.2, 0.3], 0.5) == pytest.approx(0.0)
        assert stats.round_number_share([1.0, 2.0], 1.0) == pytest.approx(1.0)


class TestAssociation:
    def test_pearson_perfect_and_inverse(self) -> None:
        assert stats.pearson([1, 2, 3, 4, 5], [2, 4, 6, 8, 10]) == pytest.approx(1.0)
        assert stats.pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)

    def test_pearson_of_a_constant_series_is_zero(self) -> None:
        assert stats.pearson([1, 1, 1], [1, 2, 3]) == pytest.approx(0.0)

    def test_spearman_is_monotone_invariant(self) -> None:
        # Rank correlation ignores the nonlinear transform Pearson would punish.
        base = [1, 2, 3, 4, 5]
        squared = [value**3 for value in base]
        assert stats.spearman(base, squared) == pytest.approx(1.0)

    def test_spearman_handles_ties(self) -> None:
        # Hand-checked: b's tie averages ranks 1 and 2 to 1.5.
        assert stats.spearman([1, 2, 3], [1, 1, 2]) == pytest.approx(0.866, abs=1e-3)

    def test_autocorrelation_of_a_trend_is_high(self) -> None:
        series = list(range(20))
        assert stats.autocorrelation(series, lag=1) > 0.9

    def test_autocorrelation_of_an_alternating_series_is_negative(self) -> None:
        series = [1.0, -1.0] * 12
        assert stats.autocorrelation(series, lag=1) == pytest.approx(-1.0, abs=1e-9)

    def test_length_and_domain_guards(self) -> None:
        with pytest.raises(ValueError):
            stats.pearson([1, 2], [1])
        with pytest.raises(ValueError):
            stats.autocorrelation([1.0, 2.0], lag=5)
        with pytest.raises(ValueError):
            stats.quantile([1, 2], 1.5)

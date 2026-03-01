"""Tests for effect size calculations."""


from bio_search.analysis.effect_size import EffectSizeCalculator


class TestCohensD:
    def test_identical_groups(self):
        d, ci = EffectSizeCalculator.cohens_d(
            mean1=10.0, mean2=10.0, sd1=2.0, sd2=2.0, n1=100, n2=100
        )
        assert d == 0.0
        assert ci.lower < 0 < ci.upper

    def test_large_effect(self):
        d, ci = EffectSizeCalculator.cohens_d(
            mean1=15.0, mean2=10.0, sd1=2.0, sd2=2.0, n1=100, n2=100
        )
        assert d == 2.5
        assert ci.lower > 0

    def test_negative_effect(self):
        d, ci = EffectSizeCalculator.cohens_d(
            mean1=8.0, mean2=10.0, sd1=2.0, sd2=2.0, n1=100, n2=100
        )
        assert d < 0

    def test_ci_contains_d(self):
        d, ci = EffectSizeCalculator.cohens_d(
            mean1=11.0, mean2=10.0, sd1=3.0, sd2=3.0, n1=50, n2=50
        )
        assert ci.lower <= d <= ci.upper


class TestOddsRatio:
    def test_no_effect(self):
        or_val, ci = EffectSizeCalculator.odds_ratio(beta=0.0, se=0.1)
        assert abs(or_val - 1.0) < 1e-10
        assert ci.lower < 1.0 < ci.upper

    def test_positive_effect(self):
        or_val, ci = EffectSizeCalculator.odds_ratio(beta=0.5, se=0.1)
        assert or_val > 1.0
        assert ci.lower > 1.0

    def test_negative_effect(self):
        or_val, ci = EffectSizeCalculator.odds_ratio(beta=-0.5, se=0.1)
        assert or_val < 1.0
        assert ci.upper < 1.0


class TestStandardizedBeta:
    def test_basic(self):
        std_b = EffectSizeCalculator.standardized_beta(beta=2.0, sd_x=1.0, sd_y=2.0)
        assert std_b == 1.0

    def test_zero(self):
        std_b = EffectSizeCalculator.standardized_beta(beta=0.0, sd_x=1.0, sd_y=1.0)
        assert std_b == 0.0

"""Tests for multiple testing correction algorithms."""

from bio_search.analysis.multiple_testing import MultipleTestingCorrector


class TestBenjaminiHochberg:
    def test_empty(self):
        assert MultipleTestingCorrector.benjamini_hochberg([]) == []

    def test_single(self):
        result = MultipleTestingCorrector.benjamini_hochberg([0.03])
        assert result == [0.03]

    def test_all_significant(self):
        p = [0.001, 0.002, 0.003]
        adj = MultipleTestingCorrector.benjamini_hochberg(p)
        # Adjusted p-values should be <= 1.0 and >= raw p
        for raw, adjusted in zip(p, adj):
            assert adjusted >= raw
            assert adjusted <= 1.0

    def test_monotonicity(self):
        """Sorted adjusted p-values should be non-decreasing."""
        p = [0.01, 0.04, 0.03, 0.005, 0.5]
        adj = MultipleTestingCorrector.benjamini_hochberg(p)
        indexed = sorted(zip(p, adj), key=lambda x: x[0])
        adj_sorted = [a for _, a in indexed]
        for i in range(len(adj_sorted) - 1):
            assert adj_sorted[i] <= adj_sorted[i + 1] + 1e-10

    def test_known_values(self):
        """Verify against known BH correction results."""
        p = [0.005, 0.01, 0.03, 0.04, 0.5]
        adj = MultipleTestingCorrector.benjamini_hochberg(p)
        # p=0.005 rank 1: 0.005 * 5/1 = 0.025
        # p=0.01  rank 2: 0.01 * 5/2 = 0.025
        # p=0.03  rank 3: 0.03 * 5/3 = 0.05
        # p=0.04  rank 4: 0.04 * 5/4 = 0.05
        # p=0.5   rank 5: 0.5 * 5/5 = 0.5
        assert abs(adj[0] - 0.025) < 1e-10
        assert abs(adj[1] - 0.025) < 1e-10
        assert abs(adj[2] - 0.05) < 1e-10
        assert abs(adj[3] - 0.05) < 1e-10
        assert abs(adj[4] - 0.5) < 1e-10


class TestBonferroni:
    def test_basic(self):
        import pytest
        p = [0.01, 0.05, 0.1]
        adj = MultipleTestingCorrector.bonferroni(p)
        assert adj == pytest.approx([0.03, 0.15, 0.3])

    def test_cap_at_one(self):
        p = [0.5, 0.8]
        adj = MultipleTestingCorrector.bonferroni(p)
        assert adj[0] == 1.0
        assert adj[1] == 1.0


class TestHolm:
    def test_empty(self):
        assert MultipleTestingCorrector.holm([]) == []

    def test_basic(self):
        p = [0.01, 0.04, 0.03]
        adj = MultipleTestingCorrector.holm(p)
        # Sorted: 0.01(rank1), 0.03(rank2), 0.04(rank3)
        # adj[0.01] = 0.01*3 = 0.03
        # adj[0.03] = max(0.03, 0.03*2) = 0.06
        # adj[0.04] = max(0.06, 0.04*1) = 0.06
        assert abs(adj[0] - 0.03) < 1e-10
        assert abs(adj[2] - 0.06) < 1e-10


class TestCorrectDispatch:
    def test_bh_alias(self):
        p = [0.01, 0.05]
        r1 = MultipleTestingCorrector.correct(p, method="benjamini-hochberg")
        r2 = MultipleTestingCorrector.correct(p, method="bh")
        assert r1 == r2

    def test_unknown_method(self):
        import pytest
        with pytest.raises((ValueError, KeyError)):
            MultipleTestingCorrector.correct([0.05], method="nonexistent")

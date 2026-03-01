"""Tests for EWAS scanner."""


from bio_search.analysis.ewas import EWASScanner
from bio_search.survey.design import SurveyDesign


class TestEWASScanner:
    def test_get_candidates_skips_design_vars(self, sample_df):
        scanner = EWASScanner()
        candidates = scanner.get_candidate_exposures(sample_df, "OUTCOME")
        # Should skip SEQN, SDMVSTRA, SDMVPSU, WTMEC2YR, and covariates
        assert "SEQN" not in candidates
        assert "SDMVSTRA" not in candidates
        assert "SDMVPSU" not in candidates
        assert "WTMEC2YR" not in candidates
        # Should include noise and exposure columns
        assert "EXPOSURE_A" in candidates
        assert "NOISE_B" in candidates

    def test_get_candidates_skips_outcome(self, sample_df):
        scanner = EWASScanner()
        candidates = scanner.get_candidate_exposures(sample_df, "OUTCOME")
        assert "OUTCOME" not in candidates

    def test_ewas_finds_true_association(self, sample_df):
        """The true exposure should rank highly after FDR correction."""
        # Drop BINARY_OUTCOME since it's derived from OUTCOME (perfect correlation)
        df = sample_df.drop(columns=["BINARY_OUTCOME"])
        scanner = EWASScanner(min_n=50)
        design = SurveyDesign(weight_col="WTMEC2YR", n_cycles=1)

        result = scanner.scan(df, "OUTCOME", design)

        assert result.n_tests > 0
        assert len(result.associations) > 0

        # EXPOSURE_A should have the smallest p-value
        sorted_results = sorted(result.associations, key=lambda r: r.p_value)
        assert sorted_results[0].exposure == "EXPOSURE_A"

        # EXPOSURE_A should be significant after FDR
        top = sorted_results[0]
        assert top.fdr_p is not None
        assert top.fdr_p < 0.05
        assert top.beta > 0  # True beta is positive (2.0)

    def test_ewas_progress_callback(self, sample_df):
        scanner = EWASScanner(min_n=50)
        design = SurveyDesign(weight_col="WTMEC2YR", n_cycles=1)

        progress_calls = []

        def cb(current, total, var):
            progress_calls.append((current, total, var))

        scanner.scan(sample_df, "OUTCOME", design, progress_callback=cb)
        assert len(progress_calls) > 0
        # Last call should have current == total
        assert progress_calls[-1][0] == progress_calls[-1][1]

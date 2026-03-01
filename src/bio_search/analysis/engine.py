"""Top-level analysis engine that coordinates all analysis subsystems.

The ``AnalysisEngine`` is the single entry point that the TUI and CLI
call to run any kind of analysis.  It owns instances of:

* ``EWASScanner`` -- environment-wide association scan
* ``GuidedAnalyzer`` -- deep-dive on a single pair
* ``ClinicalSignificanceAssessor`` -- MCID-based relevance scoring
* ``TrendAnalyzer`` -- cross-cycle temporal trends

All configuration flows through ``Settings``, so the engine is
trivially reconfigurable from environment variables or the TUI
settings panel.

Usage example::

    from bio_search.config import Settings
    from bio_search.analysis.engine import AnalysisEngine
    from bio_search.survey.design import SurveyDesign

    engine = AnalysisEngine()
    design = SurveyDesign(...)

    # EWAS
    ewas = engine.run_ewas(df, "LBXGLU", design)
    hits = engine.get_significant_results(ewas)

    # Guided
    guided = engine.run_guided(df, "LBXGLU", "LBXBPB", design)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable

import pandas as pd

from bio_search.analysis.clinical import ClinicalSignificanceAssessor
from bio_search.analysis.ewas import EWASScanner
from bio_search.analysis.guided import GuidedAnalyzer
from bio_search.analysis.trend import TrendAnalyzer
from bio_search.config import Settings
from bio_search.models.analysis import AssociationResult, EWASResult, GuidedAnalysisResult

if TYPE_CHECKING:
    from bio_search.survey.design import SurveyDesign

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Central coordinator for all NHANES statistical analyses.

    Parameters
    ----------
    settings:
        Application settings.  If ``None``, a default ``Settings()``
        instance is created (reads from environment / ``.env``).
    custom_mcid_thresholds:
        Optional dictionary of ``{variable: mcid}`` pairs to override
        or extend the built-in clinical significance thresholds.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        custom_mcid_thresholds: dict[str, float] | None = None,
    ) -> None:
        self.settings = settings or Settings()

        self.ewas_scanner = EWASScanner(
            min_n=self.settings.ewas_min_n,
            max_missing_pct=self.settings.ewas_max_missing_pct,
            n_workers=self.settings.ewas_workers,
            fdr_alpha=self.settings.fdr_alpha,
        )

        self.clinical_assessor = ClinicalSignificanceAssessor(
            custom_thresholds=custom_mcid_thresholds,
        )

    # ------------------------------------------------------------------
    # EWAS
    # ------------------------------------------------------------------
    def run_ewas(
        self,
        df: pd.DataFrame,
        outcome: str,
        design: SurveyDesign,
        covariates: list[str] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
        enrich_clinical: bool = True,
    ) -> EWASResult:
        """Run a full Environment-Wide Association Study.

        Parameters
        ----------
        df:
            Merged analysis DataFrame.
        outcome:
            Outcome variable to test all exposures against.
        design:
            Survey design configuration.
        covariates:
            Adjustment covariates (defaults to age, sex,
            race/ethnicity, income).
        progress_callback:
            Optional ``(completed, total, variable_name)`` callback
            for TUI progress bars.
        enrich_clinical:
            If ``True`` (default), annotate every result with
            ``clinically_significant`` using the MCID assessor.

        Returns
        -------
        EWASResult
            Contains all association results with FDR-adjusted p-values.
        """
        logger.info("AnalysisEngine: starting EWAS for outcome %s", outcome)

        result = self.ewas_scanner.scan(
            df, outcome, design, covariates, progress_callback,
        )

        if enrich_clinical and result.associations:
            self.clinical_assessor.enrich(result.associations)
            logger.info(
                "AnalysisEngine: %d/%d EWAS hits are clinically significant",
                sum(1 for r in result.associations if r.clinically_significant),
                len(result.associations),
            )

        return result

    # ------------------------------------------------------------------
    # Guided analysis
    # ------------------------------------------------------------------
    def run_guided(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        design: SurveyDesign,
        covariates: list[str] | None = None,
        include_subgroups: bool = True,
    ) -> GuidedAnalysisResult:
        """Run a guided deep-dive on a specific exposure-outcome pair.

        Parameters
        ----------
        df:
            Merged analysis DataFrame.
        outcome:
            Outcome variable name.
        exposure:
            Exposure variable name.
        design:
            Survey design configuration.
        covariates:
            Adjustment covariates.
        include_subgroups:
            If ``True`` (default), run sex/age/race/income subgroup
            analyses.  Set to ``False`` for a quick primary-only result.

        Returns
        -------
        GuidedAnalysisResult
            Primary regression result plus optional subgroup results.
        """
        from bio_search.survey.estimator import SurveyEstimator

        logger.info(
            "AnalysisEngine: guided analysis for %s -> %s", exposure, outcome,
        )

        estimator = SurveyEstimator(design)
        analyzer = GuidedAnalyzer(estimator)

        if include_subgroups:
            result = analyzer.analyze(df, outcome, exposure, covariates)
        else:
            result = analyzer.quick(df, outcome, exposure, covariates)

        # Annotate the primary result with clinical significance.
        result.primary.clinically_significant = (
            self.clinical_assessor.is_clinically_significant(result.primary)
        )

        return result

    # ------------------------------------------------------------------
    # Cross-cycle trend
    # ------------------------------------------------------------------
    def run_trend(
        self,
        cycle_dfs: dict[str, pd.DataFrame],
        outcome: str,
        exposure: str,
        design: SurveyDesign,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Run the same regression across multiple NHANES cycles.

        Parameters
        ----------
        cycle_dfs:
            Mapping from cycle ID (e.g. ``"2017-2018"``) to the merged
            DataFrame for that cycle.
        outcome:
            Outcome variable name.
        exposure:
            Exposure variable name.
        design:
            Survey design (weight/strata/PSU columns).
        covariates:
            Adjustment covariates.

        Returns
        -------
        list[AssociationResult]
            One result per successfully analysed cycle.
        """
        from bio_search.survey.estimator import SurveyEstimator

        logger.info(
            "AnalysisEngine: trend analysis for %s -> %s across %d cycles",
            exposure, outcome, len(cycle_dfs),
        )

        estimator = SurveyEstimator(design)
        trend = TrendAnalyzer(estimator)

        return trend.cross_cycle_trend(cycle_dfs, outcome, exposure, covariates)

    # ------------------------------------------------------------------
    # Result filtering
    # ------------------------------------------------------------------
    def get_significant_results(
        self,
        ewas_result: EWASResult,
        fdr_threshold: float = 0.05,
    ) -> list[AssociationResult]:
        """Filter EWAS results to associations surviving FDR correction.

        Parameters
        ----------
        ewas_result:
            The output of ``run_ewas``.
        fdr_threshold:
            Maximum FDR-adjusted p-value for a result to be considered
            significant.  Defaults to 0.05.

        Returns
        -------
        list[AssociationResult]
            Subset of associations with ``fdr_p < fdr_threshold``,
            sorted by ascending p-value.
        """
        significant = [
            r for r in ewas_result.associations
            if r.fdr_p is not None and r.fdr_p < fdr_threshold
        ]
        significant.sort(key=lambda r: r.p_value)

        logger.info(
            "AnalysisEngine: %d/%d EWAS associations pass FDR < %.3f",
            len(significant),
            len(ewas_result.associations),
            fdr_threshold,
        )

        return significant

    def get_clinically_significant_results(
        self,
        ewas_result: EWASResult,
        fdr_threshold: float = 0.05,
    ) -> list[AssociationResult]:
        """Filter to associations that are both statistically and clinically significant.

        Parameters
        ----------
        ewas_result:
            The output of ``run_ewas``.
        fdr_threshold:
            Maximum FDR-adjusted p-value.

        Returns
        -------
        list[AssociationResult]
            Associations passing both FDR and clinical significance
            thresholds, sorted by clinical significance score
            (descending).
        """
        significant = self.get_significant_results(ewas_result, fdr_threshold)
        clinically_relevant = [
            r for r in significant
            if r.clinically_significant
        ]

        # Sort by clinical score (descending).
        clinically_relevant.sort(
            key=lambda r: self.clinical_assessor.score(r),
            reverse=True,
        )

        return clinically_relevant

    # ------------------------------------------------------------------
    # Clinical scoring (pass-through)
    # ------------------------------------------------------------------
    def clinical_score(self, result: AssociationResult) -> float:
        """Compute the clinical significance score for one result.

        Convenience wrapper around ``ClinicalSignificanceAssessor.score``.
        """
        return self.clinical_assessor.score(result)

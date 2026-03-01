"""Guided analysis for a user-specified exposure-outcome pair.

While the EWAS scanner is a hypothesis-generating sweep across all
exposures, guided analysis is a hypothesis-testing deep dive into a
*single* exposure-outcome relationship chosen by the user (or flagged
as significant by the EWAS).

A guided analysis produces:

1. **Primary result** -- the main survey-weighted regression with
   standard covariates.
2. **Subgroup results** -- stratified by sex, age group,
   race/ethnicity, and income quartile.
3. **Trend results** -- (optional) the same model run across multiple
   NHANES cycles to assess temporal stability.

The ``GuidedAnalyzer`` composes ``RegressionAnalyzer`` and
``SubgroupAnalyzer`` internally so the caller does not need to wire
them together.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

from bio_search.analysis.subgroup import SubgroupAnalyzer
from bio_search.models.analysis import AssociationResult, GuidedAnalysisResult

if TYPE_CHECKING:
    from bio_search.survey.estimator import SurveyEstimator

logger = logging.getLogger(__name__)


class GuidedAnalyzer:
    """Deep-dive analysis of a single exposure-outcome pair.

    Parameters
    ----------
    estimator:
        A ``SurveyEstimator`` wrapping the NHANES survey design.
    """

    def __init__(self, estimator: SurveyEstimator) -> None:
        from bio_search.analysis.regression import RegressionAnalyzer

        self.estimator = estimator
        self.analyzer = RegressionAnalyzer(estimator)
        self.subgroup_analyzer = SubgroupAnalyzer(estimator)

    # ------------------------------------------------------------------
    # Full guided analysis
    # ------------------------------------------------------------------
    def analyze(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> GuidedAnalysisResult:
        """Run a full guided analysis with subgroup breakdowns.

        Parameters
        ----------
        df:
            Merged analysis DataFrame.
        outcome:
            Outcome variable name.
        exposure:
            Exposure variable name.
        covariates:
            Adjustment covariates.  Passed through to both the primary
            regression and the subgroup regressions (which may drop one
            covariate when it coincides with the stratification column).

        Returns
        -------
        GuidedAnalysisResult
            Contains the primary result and a ``subgroups`` dict with
            keys ``"sex"``, ``"race_ethnicity"``, ``"age_group"``, and
            ``"income"``.

        Raises
        ------
        ValueError
            If *outcome* or *exposure* are not columns in *df*.
        """
        if outcome not in df.columns:
            raise ValueError(f"Outcome column {outcome!r} not found in DataFrame")
        if exposure not in df.columns:
            raise ValueError(f"Exposure column {exposure!r} not found in DataFrame")

        logger.info(
            "GuidedAnalyzer: running %s -> %s (covariates=%s)",
            exposure, outcome, covariates,
        )

        # ---- Primary result ----
        primary = self.analyzer.run(df, outcome, exposure, covariates)

        # ---- Subgroup analyses ----
        subgroups = self._run_subgroups(df, outcome, exposure, covariates)

        return GuidedAnalysisResult(
            exposure=exposure,
            outcome=outcome,
            primary=primary,
            subgroups=subgroups,
        )

    # ------------------------------------------------------------------
    # Subgroup orchestration
    # ------------------------------------------------------------------
    def _run_subgroups(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None,
    ) -> dict[str, list[AssociationResult]]:
        """Run all standard subgroup analyses and collect non-empty results.

        Each subgroup key is only included in the returned dict if at
        least one stratum produced a valid result.
        """
        subgroups: dict[str, list[AssociationResult]] = {}

        # -- Sex --
        sex_results = self.subgroup_analyzer.by_sex(
            df, outcome, exposure, covariates,
        )
        if sex_results:
            subgroups["sex"] = sex_results

        # -- Race/ethnicity --
        race_results = self.subgroup_analyzer.by_race_ethnicity(
            df, outcome, exposure, covariates,
        )
        if race_results:
            subgroups["race_ethnicity"] = race_results

        # -- Age group --
        age_results = self.subgroup_analyzer.by_age_group(
            df, outcome, exposure, covariates,
        )
        if age_results:
            subgroups["age_group"] = age_results

        # -- Income quartile --
        income_results = self.subgroup_analyzer.by_income_quartile(
            df, outcome, exposure, covariates,
        )
        if income_results:
            subgroups["income"] = income_results

        logger.info(
            "GuidedAnalyzer: subgroup analyses produced %d non-empty strata groups",
            len(subgroups),
        )

        return subgroups

    # ------------------------------------------------------------------
    # Quick single-pair analysis (no subgroups)
    # ------------------------------------------------------------------
    def quick(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> GuidedAnalysisResult:
        """Run only the primary regression, skipping subgroups.

        Useful when the caller wants fast feedback (e.g. in a TUI
        preview) without waiting for stratified models.
        """
        if outcome not in df.columns:
            raise ValueError(f"Outcome column {outcome!r} not found in DataFrame")
        if exposure not in df.columns:
            raise ValueError(f"Exposure column {exposure!r} not found in DataFrame")

        primary = self.analyzer.run(df, outcome, exposure, covariates)

        return GuidedAnalysisResult(
            exposure=exposure,
            outcome=outcome,
            primary=primary,
        )

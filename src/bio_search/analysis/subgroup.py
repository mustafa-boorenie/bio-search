"""Subgroup (stratified) analysis for NHANES associations.

After an EWAS or guided analysis identifies a significant association,
the natural next question is "does it hold equally across demographic
groups?".  This module stratifies the data by standard NHANES
demographic variables (sex, race/ethnicity, age group, income level)
and re-runs the regression within each stratum.

The ``SubgroupAnalyzer`` knows the NHANES codebook for the demographic
columns it stratifies on, so the TUI can display human-readable labels
like "Non-Hispanic White" instead of raw code values.

Important caveats
-----------------
* Survey weights are *not* recalibrated for each subgroup.  This is
  acceptable for descriptive/exploratory analyses but would need
  attention in a confirmatory setting.
* Strata with fewer than 50 observations after complete-case deletion
  are silently dropped to avoid unstable estimates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from bio_search.models.analysis import AssociationResult
    from bio_search.survey.estimator import SurveyEstimator

logger = logging.getLogger(__name__)

# Minimum observations per stratum to run a regression.
_MIN_STRATUM_N = 50


class SubgroupAnalyzer:
    """Stratified analysis by NHANES demographic variables.

    Attributes
    ----------
    DEMOGRAPHIC_VARS : dict
        Registry of supported stratification variables.  Each entry
        maps a human-friendly key (e.g. ``"sex"``) to a tuple of
        ``(nhanes_column, value_labels_or_None)``.  If value labels
        are ``None``, the variable requires custom binning rather than
        direct category lookup.
    """

    DEMOGRAPHIC_VARS: dict[str, tuple[str, dict[int, str] | None]] = {
        "sex": (
            "RIAGENDR",
            {1: "Male", 2: "Female"},
        ),
        "race_ethnicity": (
            "RIDRETH3",
            {
                1: "Mexican American",
                2: "Other Hispanic",
                3: "Non-Hispanic White",
                4: "Non-Hispanic Black",
                6: "Non-Hispanic Asian",
                7: "Other/Multi",
            },
        ),
        "age_group": (
            "RIDAGEYR",
            None,  # Custom binning in _stratify_age
        ),
        "income": (
            "INDFMPIR",
            None,  # Quartile binning in _stratify_income
        ),
    }

    # Age bins: (lower_inclusive, upper_inclusive, label)
    _AGE_BINS: list[tuple[int, int, str]] = [
        (18, 39, "18-39"),
        (40, 59, "40-59"),
        (60, 200, "60+"),
    ]

    def __init__(self, estimator: SurveyEstimator) -> None:
        from bio_search.analysis.regression import RegressionAnalyzer

        self.estimator = estimator
        self.analyzer = RegressionAnalyzer(estimator)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def by_category(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        stratify_by: str,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Stratified analysis by a categorical variable.

        Parameters
        ----------
        df:
            Analysis DataFrame containing outcome, exposure,
            covariates, and the stratification column.
        outcome:
            Outcome variable name.
        exposure:
            Exposure variable name.
        stratify_by:
            Column to stratify on.  Must be present in *df*.
        covariates:
            Adjustment variables.  The stratification column is
            automatically removed from covariates if present.

        Returns
        -------
        list[AssociationResult]
            One result per stratum.  Each result has a synthetic
            covariate entry like ``"RIAGENDR=1.0"`` prepended to
            ``covariates`` to identify the stratum.
        """
        if stratify_by not in df.columns:
            logger.warning(
                "Subgroup: stratification column %s not in DataFrame", stratify_by,
            )
            return []

        # Remove the stratification variable from covariates -- it is
        # held constant within each stratum.
        cov = [c for c in (covariates or []) if c != stratify_by]

        results: list[AssociationResult] = []
        unique_vals = sorted(df[stratify_by].dropna().unique())

        for val in unique_vals:
            sub = df[df[stratify_by] == val]
            if len(sub) < _MIN_STRATUM_N:
                logger.debug(
                    "Subgroup: skipping %s=%s (n=%d < %d)",
                    stratify_by, val, len(sub), _MIN_STRATUM_N,
                )
                continue

            try:
                r = self.analyzer.run(sub, outcome, exposure, cov)
                # Tag the result so the caller knows which stratum it
                # belongs to.
                label = self._label_for(stratify_by, val)
                r.covariates = [f"{stratify_by}={label}"] + r.covariates
                results.append(r)
            except Exception:
                logger.warning(
                    "Subgroup: regression failed for %s=%s",
                    stratify_by, val, exc_info=True,
                )

        return results

    def by_sex(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Convenience wrapper: stratify by RIAGENDR (sex)."""
        return self.by_category(df, outcome, exposure, "RIAGENDR", covariates)

    def by_race_ethnicity(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Convenience wrapper: stratify by RIDRETH3 (race/ethnicity)."""
        return self.by_category(df, outcome, exposure, "RIDRETH3", covariates)

    def by_age_group(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Stratify by age group using predefined bins (18-39, 40-59, 60+).

        Age (RIDAGEYR) is removed from the covariate set since it is
        held constant within each bin.
        """
        if "RIDAGEYR" not in df.columns:
            logger.warning("Subgroup: RIDAGEYR not in DataFrame")
            return []

        cov = [c for c in (covariates or []) if c != "RIDAGEYR"]
        results: list[AssociationResult] = []

        for lo, hi, label in self._AGE_BINS:
            sub = df[(df["RIDAGEYR"] >= lo) & (df["RIDAGEYR"] <= hi)]
            if len(sub) < _MIN_STRATUM_N:
                logger.debug(
                    "Subgroup: skipping age %s (n=%d < %d)",
                    label, len(sub), _MIN_STRATUM_N,
                )
                continue

            try:
                r = self.analyzer.run(sub, outcome, exposure, cov)
                r.covariates = [f"age={label}"] + r.covariates
                results.append(r)
            except Exception:
                logger.warning(
                    "Subgroup: regression failed for age %s", label, exc_info=True,
                )

        return results

    def by_income_quartile(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> list[AssociationResult]:
        """Stratify by income-to-poverty ratio quartiles.

        INDFMPIR is removed from the covariate set since it is held
        approximately constant within each quartile.
        """
        if "INDFMPIR" not in df.columns:
            logger.warning("Subgroup: INDFMPIR not in DataFrame")
            return []

        cov = [c for c in (covariates or []) if c != "INDFMPIR"]

        # Compute quartile boundaries on non-missing values.
        valid = df["INDFMPIR"].dropna()
        if len(valid) < _MIN_STRATUM_N * 4:
            logger.warning("Subgroup: insufficient data for income quartiles")
            return []

        try:
            quartile_labels = pd.qcut(
                df["INDFMPIR"], q=4, labels=["Q1", "Q2", "Q3", "Q4"],
            )
        except ValueError:
            # qcut can fail if there are too few distinct values.
            logger.warning("Subgroup: cannot compute income quartiles")
            return []

        results: list[AssociationResult] = []
        for q_label in ["Q1", "Q2", "Q3", "Q4"]:
            mask = quartile_labels == q_label
            sub = df[mask]
            if len(sub) < _MIN_STRATUM_N:
                continue

            try:
                r = self.analyzer.run(sub, outcome, exposure, cov)
                r.covariates = [f"income={q_label}"] + r.covariates
                results.append(r)
            except Exception:
                logger.warning(
                    "Subgroup: regression failed for income %s", q_label, exc_info=True,
                )

        return results

    def all_demographics(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> dict[str, list[AssociationResult]]:
        """Run subgroup analyses for all standard demographic variables.

        Returns
        -------
        dict[str, list[AssociationResult]]
            Keys are ``"sex"``, ``"race_ethnicity"``, ``"age_group"``,
            and ``"income"``.  Values are lists of per-stratum results
            (may be empty if the variable is missing or has insufficient
            data).
        """
        return {
            "sex": self.by_sex(df, outcome, exposure, covariates),
            "race_ethnicity": self.by_race_ethnicity(df, outcome, exposure, covariates),
            "age_group": self.by_age_group(df, outcome, exposure, covariates),
            "income": self.by_income_quartile(df, outcome, exposure, covariates),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _label_for(self, column: str, value: float) -> str:
        """Convert a raw coded value to a human-readable label.

        Falls back to the raw value if no label mapping is registered.
        """
        for _key, (col, labels) in self.DEMOGRAPHIC_VARS.items():
            if col == column and labels is not None:
                int_val = int(value) if float(value).is_integer() else value
                if int_val in labels:
                    return labels[int_val]
        # No mapping found -- use the raw value.
        return str(value)

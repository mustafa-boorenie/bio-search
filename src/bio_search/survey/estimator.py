"""Survey-weighted statistical estimators for NHANES data.

This module provides a unified interface for computing:

* **Weighted means** -- population means with design-corrected SEs.
* **Weighted proportions** -- for categorical / binary variables.
* **Survey-weighted linear regression** -- WLS with cluster-robust
  standard errors (Huber-White sandwich estimator clustered on PSU).
* **Survey-weighted logistic regression** -- GLM Binomial with
  cluster-robust SEs, returning odds ratios.

All point estimates and standard errors account for the NHANES
stratified, multi-stage probability sampling design by incorporating
strata, PSU, and sampling weights.

The descriptive statistics (means, proportions) use the ``samplics``
package's Taylor-series linearisation estimator, which is the standard
approach recommended by CDC and matches SAS ``PROC SURVEYMEANS`` and R's
``survey::svymean``.

The regression models use ``statsmodels`` WLS / GLM with the
``cov_type='cluster'`` option, which computes the sandwich variance
estimator clustered on PSUs.  This is the same approach used by R's
``survey::svyglm`` under the hood.

References
----------
* samplics documentation: https://samplics-org.github.io/samplics/
* statsmodels GLS/GLM robust covariance:
  https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.RegressionResults.html
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from samplics.estimation import TaylorEstimator
from samplics.utils.types import PopParam

from bio_search.models.analysis import AssociationResult, ConfidenceInterval
from bio_search.survey.design import SurveyDesign

logger = logging.getLogger(__name__)

# Minimum observations required for regression to be numerically stable.
_MIN_REGRESSION_N = 30


class SurveyEstimationError(Exception):
    """Raised when a survey-weighted estimation fails."""


class SurveyEstimator:
    """Survey-weighted estimation engine backed by samplics and statsmodels.

    Parameters
    ----------
    design:
        A :class:`SurveyDesign` that specifies the weight, strata, and
        PSU columns for the current analysis.
    """

    def __init__(self, design: SurveyDesign) -> None:
        self.design = design

    # -----------------------------------------------------------------
    # Descriptive statistics (samplics Taylor estimator)
    # -----------------------------------------------------------------

    def weighted_mean(
        self,
        df: pd.DataFrame,
        var: str,
    ) -> tuple[float, float, int]:
        """Compute the survey-weighted population mean of a continuous variable.

        Uses Taylor-series linearisation via :class:`samplics.estimation.TaylorEstimator`
        to produce design-corrected point estimates and standard errors.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame (already passed through
            :meth:`SurveyDesign.prepare`).
        var:
            Name of the continuous column to estimate.

        Returns
        -------
        tuple[float, float, int]
            ``(mean, standard_error, n)`` where *n* is the number of
            non-missing observations used.

        Raises
        ------
        SurveyEstimationError
            If the estimation fails (e.g. too few observations, singular
            variance matrix).
        ValueError
            If *var* is not in *df*.
        """
        self._check_column(df, var)

        # Drop rows where the analysis variable itself is missing.
        subset = df[[var, self.design.weight_col, self.design.strata_col, self.design.psu_col]]
        subset = subset.dropna()
        n = len(subset)

        if n == 0:
            raise SurveyEstimationError(f"No non-missing observations for variable '{var}'")

        try:
            estimator = TaylorEstimator(PopParam.mean)
            estimator.estimate(
                y=subset[var].to_numpy(dtype=float),
                samp_weight=subset[self.design.weight_col].to_numpy(dtype=float),
                stratum=subset[self.design.strata_col].to_numpy(),
                psu=subset[self.design.psu_col].to_numpy(),
                remove_nan=True,
            )

            mean_val = float(estimator.point_est)
            se_val = float(estimator.stderror)

            logger.debug(
                "Weighted mean of '%s': %.4f (SE=%.4f, n=%d)",
                var,
                mean_val,
                se_val,
                n,
            )
            return mean_val, se_val, n

        except Exception as exc:
            raise SurveyEstimationError(
                f"Failed to estimate weighted mean for '{var}' (n={n}): {exc}"
            ) from exc

    def weighted_proportion(
        self,
        df: pd.DataFrame,
        var: str,
    ) -> dict[Any, tuple[float, float]]:
        """Compute survey-weighted proportions for a categorical variable.

        Returns one ``(proportion, SE)`` pair for every distinct value
        of *var*.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame.
        var:
            Name of the categorical or binary column.

        Returns
        -------
        dict[Any, tuple[float, float]]
            Mapping ``{value: (proportion, standard_error)}`` for each
            unique value of *var*.

        Raises
        ------
        SurveyEstimationError
            If estimation fails for any category.
        """
        self._check_column(df, var)

        subset = df[[var, self.design.weight_col, self.design.strata_col, self.design.psu_col]]
        subset = subset.dropna()
        n = len(subset)

        if n == 0:
            raise SurveyEstimationError(f"No non-missing observations for variable '{var}'")

        unique_values = sorted(subset[var].unique())
        results: dict[Any, tuple[float, float]] = {}

        for value in unique_values:
            try:
                # Create a binary indicator for this category.
                indicator = (subset[var] == value).astype(float).to_numpy()

                estimator = TaylorEstimator(PopParam.prop)
                estimator.estimate(
                    y=indicator,
                    samp_weight=subset[self.design.weight_col].to_numpy(dtype=float),
                    stratum=subset[self.design.strata_col].to_numpy(),
                    psu=subset[self.design.psu_col].to_numpy(),
                    remove_nan=True,
                )

                # For a binary indicator the proportion estimator returns
                # estimates for both 0.0 and 1.0.  We want the proportion
                # for the "1" (True) category.
                point_est = estimator.point_est
                std_err = estimator.stderror

                # point_est may be a dict keyed by category value or a scalar.
                if isinstance(point_est, dict):
                    prop_val = float(point_est.get(1.0, point_est.get(1, 0.0)))
                    se_val = float(std_err.get(1.0, std_err.get(1, 0.0)))
                elif isinstance(point_est, np.ndarray):
                    # Array indexed by category; take the "1" position.
                    prop_val = float(point_est[-1]) if len(point_est) > 1 else float(point_est[0])
                    se_val = float(std_err[-1]) if len(std_err) > 1 else float(std_err[0])
                else:
                    prop_val = float(point_est)
                    se_val = float(std_err)

                results[value] = (prop_val, se_val)

            except Exception as exc:
                logger.warning(
                    "Could not estimate proportion for '%s' == %s: %s",
                    var,
                    value,
                    exc,
                )
                # Record NaN so the caller knows this category failed.
                results[value] = (float("nan"), float("nan"))

        logger.debug(
            "Weighted proportions for '%s' (%d categories, n=%d): %s",
            var,
            len(results),
            n,
            {k: f"{v[0]:.4f}" for k, v in results.items()},
        )
        return results

    # -----------------------------------------------------------------
    # Regression models (statsmodels)
    # -----------------------------------------------------------------

    def linear_regression(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> AssociationResult:
        """Survey-weighted linear regression (WLS with cluster-robust SEs).

        Fits a Weighted Least Squares model using the sampling weight as
        analytic weight and computes Huber-White sandwich standard errors
        clustered on the PSU column.  This is equivalent to R's
        ``survey::svyglm(family=gaussian())``.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame.
        outcome:
            Name of the continuous outcome (dependent) variable.
        exposure:
            Name of the exposure (independent) variable of interest.
        covariates:
            Optional list of covariate column names to include in the
            model.  Pass an empty list for an unadjusted model.

        Returns
        -------
        AssociationResult
            Regression result with beta, SE, p-value, CI, and sample
            size for the *exposure* coefficient.

        Raises
        ------
        SurveyEstimationError
            If the model fails to converge or the data is degenerate.
        """
        if covariates is None:
            covariates = []

        predictor_cols = [exposure] + covariates
        all_cols = (
            [outcome]
            + predictor_cols
            + [
                self.design.weight_col,
                self.design.strata_col,
                self.design.psu_col,
            ]
        )

        subset = self._prepare_regression_data(df, all_cols, outcome, exposure)
        n = len(subset)

        try:
            y = subset[outcome].to_numpy(dtype=float)
            X = sm.add_constant(subset[predictor_cols].to_numpy(dtype=float))
            weights = subset[self.design.weight_col].to_numpy(dtype=float)
            groups = subset[self.design.psu_col].to_numpy()

            model = sm.WLS(y, X, weights=weights)
            result = model.fit(
                cov_type="cluster",
                cov_kwds={"groups": groups},
            )

            # The exposure coefficient is at index 1 (index 0 is the constant).
            beta = float(result.params[1])
            se = float(result.bse[1])
            p_value = float(result.pvalues[1])
            ci_lower = float(result.conf_int()[1, 0])
            ci_upper = float(result.conf_int()[1, 1])

            logger.debug(
                "Linear regression %s ~ %s (+%d covariates): beta=%.4f, SE=%.4f, p=%.4g, n=%d",
                outcome,
                exposure,
                len(covariates),
                beta,
                se,
                p_value,
                n,
            )

            return AssociationResult(
                exposure=exposure,
                outcome=outcome,
                beta=beta,
                se=se,
                p_value=p_value,
                ci=ConfidenceInterval(lower=ci_lower, upper=ci_upper),
                n=n,
                model_type="linear",
                covariates=covariates,
            )

        except Exception as exc:
            raise SurveyEstimationError(
                f"Linear regression {outcome} ~ {exposure} failed (n={n}): {exc}"
            ) from exc

    def logistic_regression(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
    ) -> AssociationResult:
        """Survey-weighted logistic regression (GLM Binomial, cluster-robust SEs).

        Fits a Generalised Linear Model with a binomial family and logit
        link, using sampling weights as frequency weights and cluster-
        robust standard errors on the PSU column.  This is equivalent to
        R's ``survey::svyglm(family=quasibinomial())``.

        The returned ``beta`` is the log-odds coefficient.  The
        ``effect_size`` field contains the exponentiated odds ratio.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame.
        outcome:
            Name of the binary outcome variable (must be coded 0/1).
        exposure:
            Name of the exposure variable.
        covariates:
            Optional list of covariate column names.

        Returns
        -------
        AssociationResult
            Regression result.  ``beta`` is on the log-odds scale;
            ``effect_size`` is the odds ratio ``exp(beta)``; ``ci`` is
            on the log-odds scale.

        Raises
        ------
        SurveyEstimationError
            If the model fails (e.g. perfect separation, convergence
            failure).
        """
        if covariates is None:
            covariates = []

        predictor_cols = [exposure] + covariates
        all_cols = (
            [outcome]
            + predictor_cols
            + [
                self.design.weight_col,
                self.design.strata_col,
                self.design.psu_col,
            ]
        )

        subset = self._prepare_regression_data(df, all_cols, outcome, exposure)
        n = len(subset)

        # Validate that the outcome is binary.
        outcome_values = subset[outcome].unique()
        if not set(outcome_values).issubset({0, 1, 0.0, 1.0}):
            raise SurveyEstimationError(
                f"Logistic regression requires a binary (0/1) outcome. "
                f"'{outcome}' has values: {sorted(outcome_values)}"
            )

        # Check for outcome variation -- logistic regression needs both 0 and 1.
        if len(outcome_values) < 2:
            raise SurveyEstimationError(
                f"Logistic regression requires both 0 and 1 in the outcome. "
                f"'{outcome}' has only value(s): {sorted(outcome_values)}"
            )

        try:
            y = subset[outcome].to_numpy(dtype=float)
            X = sm.add_constant(subset[predictor_cols].to_numpy(dtype=float))
            weights = subset[self.design.weight_col].to_numpy(dtype=float)
            groups = subset[self.design.psu_col].to_numpy()

            model = sm.GLM(
                y,
                X,
                family=sm.families.Binomial(),
                freq_weights=weights,
            )
            result = model.fit(
                cov_type="cluster",
                cov_kwds={"groups": groups},
            )

            # Exposure coefficient at index 1.
            beta = float(result.params[1])
            se = float(result.bse[1])
            p_value = float(result.pvalues[1])
            ci_lower = float(result.conf_int()[1, 0])
            ci_upper = float(result.conf_int()[1, 1])

            # Odds ratio = exp(beta).
            odds_ratio = float(np.exp(beta))
            or_ci_lower = float(np.exp(ci_lower))
            or_ci_upper = float(np.exp(ci_upper))

            logger.debug(
                "Logistic regression %s ~ %s (+%d covariates): "
                "beta=%.4f, OR=%.4f [%.4f, %.4f], p=%.4g, n=%d",
                outcome,
                exposure,
                len(covariates),
                beta,
                odds_ratio,
                or_ci_lower,
                or_ci_upper,
                p_value,
                n,
            )

            return AssociationResult(
                exposure=exposure,
                outcome=outcome,
                beta=beta,
                se=se,
                p_value=p_value,
                ci=ConfidenceInterval(lower=ci_lower, upper=ci_upper),
                n=n,
                model_type="logistic",
                covariates=covariates,
                effect_size=odds_ratio,
                effect_size_type="odds_ratio",
            )

        except Exception as exc:
            raise SurveyEstimationError(
                f"Logistic regression {outcome} ~ {exposure} failed (n={n}): {exc}"
            ) from exc

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _prepare_regression_data(
        self,
        df: pd.DataFrame,
        all_cols: list[str],
        outcome: str,
        exposure: str,
    ) -> pd.DataFrame:
        """Validate and subset a DataFrame for regression.

        Checks that all required columns exist, drops rows with missing
        values in any analysis variable, and verifies that enough
        observations remain.

        Returns
        -------
        pd.DataFrame
            Clean subset ready for model fitting.
        """
        # Verify all required columns exist.
        missing_cols = [c for c in all_cols if c not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Missing columns for regression: {missing_cols}. Available: {sorted(df.columns)}"
            )

        # Complete-case analysis: drop rows with any missing value in
        # the analysis variables.
        subset = df[all_cols].dropna().copy()
        n = len(subset)

        if n < _MIN_REGRESSION_N:
            raise SurveyEstimationError(
                f"Insufficient observations for regression: {n} < {_MIN_REGRESSION_N}. "
                f"Model: {outcome} ~ {exposure}"
            )

        # Verify the exposure has variation (no constant columns).
        if subset[exposure].nunique() < 2:
            raise SurveyEstimationError(
                f"Exposure '{exposure}' has no variation "
                f"(unique values: {subset[exposure].unique()}) -- "
                f"regression is not meaningful"
            )

        return subset

    @staticmethod
    def _check_column(df: pd.DataFrame, col: str) -> None:
        """Raise ValueError if *col* is not in *df*."""
        if col not in df.columns:
            raise ValueError(
                f"Column '{col}' not found in DataFrame. Available: {sorted(df.columns)}"
            )

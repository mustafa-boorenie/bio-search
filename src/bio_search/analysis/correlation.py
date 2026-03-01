"""Survey-weighted correlation analysis for NHANES data.

This module computes Pearson and Spearman correlation coefficients that
account for NHANES sampling weights.  Naive (unweighted) correlations
would produce biased estimates because each NHANES participant
represents a different number of people in the US population.

Weighted Pearson correlation
----------------------------
The formula uses the weighted covariance divided by the product of
weighted standard deviations:

    r = cov_w(X, Y) / (sd_w(X) * sd_w(Y))

where the weighted covariance is:

    cov_w(X, Y) = sum(w * (X - mean_w(X)) * (Y - mean_w(Y))) / (sum(w) - 1)

The statistical test uses Fisher's z-transformation to obtain a
p-value, which is asymptotically valid for large samples (NHANES
typically has n > 1 000).

Weighted Spearman correlation
-----------------------------
Spearman correlation is computed by first rank-transforming both
variables (using weighted ranks where ties are averaged) and then
computing the weighted Pearson correlation on the ranks.

.. note::

    These are weighted-but-not-design-corrected correlations.  A fully
    design-corrected correlation (accounting for strata and PSU) would
    require Taylor-series linearisation of the correlation estimator,
    which is more complex and less commonly reported in the NHANES
    literature.  The weighted correlation is the standard approach in
    published epidemiology.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

from bio_search.survey.estimator import SurveyEstimator

logger = logging.getLogger(__name__)

# Minimum number of valid observation pairs.
_MIN_CORR_N = 10


class CorrelationError(Exception):
    """Raised when a correlation computation fails."""


class CorrelationAnalyzer:
    """Survey-weighted correlation coefficients.

    Parameters
    ----------
    estimator:
        A configured :class:`SurveyEstimator`.  Currently used only to
        access the survey design specification (weight column name); the
        actual correlation computation uses numpy for efficiency.
    """

    def __init__(self, estimator: SurveyEstimator) -> None:
        self.estimator = estimator

    def weighted_pearson(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        weight_col: str,
    ) -> tuple[float, float]:
        """Compute the survey-weighted Pearson correlation and p-value.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame.
        x:
            Name of the first continuous variable.
        y:
            Name of the second continuous variable.
        weight_col:
            Name of the sampling-weight column.

        Returns
        -------
        tuple[float, float]
            ``(correlation, p_value)``.

        Raises
        ------
        CorrelationError
            If there are too few observations or the computation fails.
        """
        xv, yv, wv, n = self._extract_valid(df, x, y, weight_col)

        r = self._weighted_corr(xv, yv, wv)
        p = self._fisher_z_pvalue(r, n)

        logger.debug(
            "Weighted Pearson r(%s, %s) = %.4f (p=%.4g, n=%d)",
            x,
            y,
            r,
            p,
            n,
        )
        return r, p

    def weighted_spearman(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        weight_col: str,
    ) -> tuple[float, float]:
        """Compute the survey-weighted Spearman rank correlation and p-value.

        The Spearman correlation is the weighted Pearson correlation of
        the rank-transformed variables.  This makes it robust to
        non-linear monotonic relationships and outliers.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame.
        x:
            Name of the first variable.
        y:
            Name of the second variable.
        weight_col:
            Name of the sampling-weight column.

        Returns
        -------
        tuple[float, float]
            ``(correlation, p_value)``.
        """
        xv, yv, wv, n = self._extract_valid(df, x, y, weight_col)

        # Rank-transform using weighted ranks.
        x_ranks = self._weighted_rank(xv, wv)
        y_ranks = self._weighted_rank(yv, wv)

        r = self._weighted_corr(x_ranks, y_ranks, wv)
        p = self._fisher_z_pvalue(r, n)

        logger.debug(
            "Weighted Spearman rho(%s, %s) = %.4f (p=%.4g, n=%d)",
            x,
            y,
            r,
            p,
            n,
        )
        return r, p

    # -----------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------

    def _extract_valid(
        self,
        df: pd.DataFrame,
        x: str,
        y: str,
        weight_col: str,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """Extract and validate complete-case data for correlation.

        Returns numpy arrays for x, y, weights, and the sample size.
        """
        for col in (x, y, weight_col):
            if col not in df.columns:
                raise ValueError(
                    f"Column '{col}' not in DataFrame. Available: {sorted(df.columns)}"
                )

        subset = df[[x, y, weight_col]].dropna()
        # Exclude zero/negative weights.
        subset = subset[subset[weight_col] > 0]
        n = len(subset)

        if n < _MIN_CORR_N:
            raise CorrelationError(
                f"Insufficient observation pairs for correlation: {n} < {_MIN_CORR_N}. "
                f"Variables: ({x}, {y})"
            )

        xv = subset[x].to_numpy(dtype=float)
        yv = subset[y].to_numpy(dtype=float)
        wv = subset[weight_col].to_numpy(dtype=float)

        return xv, yv, wv, n

    @staticmethod
    def _weighted_corr(
        x: np.ndarray,
        y: np.ndarray,
        w: np.ndarray,
    ) -> float:
        """Compute the weighted Pearson correlation coefficient.

        Uses the reliability-weights formula:

            r = cov_w(x, y) / sqrt(var_w(x) * var_w(y))

        where the weighted covariance uses Bessel's correction:

            cov_w = sum(w*(x-mx)*(y-my)) / (sum(w) - V2/sum(w))

        and V2 = sum(w**2).  This is the "frequency weights" Bessel
        correction, appropriate for sampling weights.
        """
        sum_w = np.sum(w)
        if sum_w == 0:
            return float("nan")

        # Weighted means.
        mx = np.average(x, weights=w)
        my = np.average(y, weights=w)

        # Deviations from weighted means.
        dx = x - mx
        dy = y - my

        # Weighted covariance (with Bessel correction for frequency weights).
        # V1 = sum(w), V2 = sum(w^2)
        v2 = np.sum(w**2)
        denom = sum_w - v2 / sum_w
        if denom <= 0:
            return float("nan")

        cov_xy = np.sum(w * dx * dy) / denom
        var_x = np.sum(w * dx**2) / denom
        var_y = np.sum(w * dy**2) / denom

        if var_x <= 0 or var_y <= 0:
            return float("nan")

        r = cov_xy / np.sqrt(var_x * var_y)

        # Clamp to [-1, 1] to handle floating-point imprecision.
        return float(np.clip(r, -1.0, 1.0))

    @staticmethod
    def _fisher_z_pvalue(r: float, n: int) -> float:
        """Two-sided p-value via Fisher's z-transformation.

        z = arctanh(r) is approximately normal with SE = 1/sqrt(n-3)
        for large n.  We test H0: rho = 0.

        Parameters
        ----------
        r:
            The sample correlation coefficient.
        n:
            The number of observation pairs.

        Returns
        -------
        float
            Two-sided p-value.
        """
        if np.isnan(r) or n <= 3:
            return float("nan")

        # Clamp r to avoid arctanh(+/- 1) = +/- inf.
        r_clamped = np.clip(r, -0.9999999, 0.9999999)

        z = np.arctanh(r_clamped)
        se = 1.0 / np.sqrt(n - 3)
        z_stat = z / se

        # Two-sided p-value from the standard normal distribution.
        p = 2.0 * stats.norm.sf(np.abs(z_stat))
        return float(p)

    @staticmethod
    def _weighted_rank(values: np.ndarray, weights: np.ndarray) -> np.ndarray:
        """Compute weighted ranks (midranks for ties).

        Each observation's rank is the sum of all weights of
        observations that are strictly smaller, plus half the total
        weight of observations with the same value.  This is the
        weighted equivalent of scipy's ``rankdata(method='average')``.

        Parameters
        ----------
        values:
            The data values to rank.
        weights:
            The sampling weights corresponding to each observation.

        Returns
        -------
        np.ndarray
            Weighted ranks (same length as *values*).
        """
        n = len(values)
        order = np.argsort(values, kind="mergesort")
        sorted_vals = values[order]
        sorted_weights = weights[order]

        ranks = np.empty(n, dtype=float)

        i = 0
        cumulative_weight = 0.0
        while i < n:
            # Find the block of tied values.
            j = i
            tie_weight = 0.0
            while j < n and sorted_vals[j] == sorted_vals[i]:
                tie_weight += sorted_weights[j]
                j += 1

            # Midrank for this tie block: cumulative weight before the
            # block + half the block's weight.
            midrank = cumulative_weight + tie_weight / 2.0

            for k in range(i, j):
                ranks[order[k]] = midrank

            cumulative_weight += tie_weight
            i = j

        return ranks

"""Effect-size calculators for NHANES association analyses.

This module provides three standard effect-size metrics used in
epidemiological research:

1. **Cohen's d** -- standardised mean difference between two groups.
   Used to quantify the magnitude of difference in a continuous outcome
   between exposed and unexposed groups, independent of sample size.
   Interpretation (Cohen 1988): |d| < 0.2 negligible, 0.2-0.5 small,
   0.5-0.8 medium, > 0.8 large.

2. **Odds ratio** -- exponentiated logistic regression coefficient.
   Quantifies the multiplicative change in odds of the outcome per
   unit increase in the exposure.  OR = 1 means no association.

3. **Standardised beta** -- regression coefficient rescaled to units
   of standard deviations.  Allows comparison of effect magnitudes
   across exposures measured on different scales (e.g. BMI vs. serum
   lead concentration).

All methods include 95% confidence intervals based on the normal
approximation, which is appropriate for the large sample sizes
typical of NHANES (n > 1 000).
"""

from __future__ import annotations

import logging
import math

from bio_search.models.analysis import ConfidenceInterval

logger = logging.getLogger(__name__)


class EffectSizeError(Exception):
    """Raised when an effect-size computation encounters invalid inputs."""


class EffectSizeCalculator:
    """Static methods for computing standardised effect sizes."""

    @staticmethod
    def cohens_d(
        mean1: float,
        mean2: float,
        sd1: float,
        sd2: float,
        n1: int,
        n2: int,
        alpha: float = 0.05,
    ) -> tuple[float, ConfidenceInterval]:
        """Compute Cohen's d (standardised mean difference) with CI.

        Uses the pooled standard deviation (assumes roughly equal
        variances) and the large-sample normal approximation for the
        confidence interval.

        Parameters
        ----------
        mean1:
            Mean of group 1 (e.g. exposed).
        mean2:
            Mean of group 2 (e.g. unexposed).
        sd1:
            Standard deviation of group 1.
        sd2:
            Standard deviation of group 2.
        n1:
            Sample size of group 1.
        n2:
            Sample size of group 2.
        alpha:
            Significance level for the CI (default 0.05 = 95% CI).

        Returns
        -------
        tuple[float, ConfidenceInterval]
            ``(d, ci)`` where *d* is the Cohen's d effect size and *ci*
            is the confidence interval.

        Raises
        ------
        EffectSizeError
            If sample sizes are too small or standard deviations are
            non-positive.
        """
        # Input validation.
        if n1 < 2 or n2 < 2:
            raise EffectSizeError(f"Cohen's d requires n >= 2 in both groups; got n1={n1}, n2={n2}")
        if sd1 <= 0 or sd2 <= 0:
            raise EffectSizeError(f"Standard deviations must be positive; got sd1={sd1}, sd2={sd2}")

        # Pooled standard deviation.
        pooled_var = ((n1 - 1) * sd1**2 + (n2 - 1) * sd2**2) / (n1 + n2 - 2)
        pooled_sd = math.sqrt(pooled_var)

        if pooled_sd == 0:
            raise EffectSizeError("Pooled standard deviation is zero -- cannot compute Cohen's d")

        d = (mean1 - mean2) / pooled_sd

        # Standard error of Cohen's d (Hedges & Olkin, 1985).
        # SE(d) = sqrt(n1+n2)/(n1*n2) + d^2/(2*(n1+n2)))
        se_d = math.sqrt((n1 + n2) / (n1 * n2) + d**2 / (2 * (n1 + n2)))

        z_crit = _z_critical(alpha)
        ci = ConfidenceInterval(
            lower=d - z_crit * se_d,
            upper=d + z_crit * se_d,
            level=1.0 - alpha,
        )

        logger.debug(
            "Cohen's d = %.4f [%.4f, %.4f] (mean1=%.3f, mean2=%.3f, pooled_sd=%.3f, n1=%d, n2=%d)",
            d,
            ci.lower,
            ci.upper,
            mean1,
            mean2,
            pooled_sd,
            n1,
            n2,
        )
        return d, ci

    @staticmethod
    def odds_ratio(
        beta: float,
        se: float,
        alpha: float = 0.05,
    ) -> tuple[float, ConfidenceInterval]:
        """Compute the odds ratio and CI from a logistic regression coefficient.

        Parameters
        ----------
        beta:
            Log-odds coefficient from the logistic regression.
        se:
            Standard error of *beta*.
        alpha:
            Significance level for the CI (default 0.05 = 95% CI).

        Returns
        -------
        tuple[float, ConfidenceInterval]
            ``(OR, ci)`` where *OR* is the odds ratio ``exp(beta)``
            and *ci* is the CI on the OR scale.

        Raises
        ------
        EffectSizeError
            If the standard error is non-positive.
        """
        if se <= 0:
            raise EffectSizeError(f"Standard error must be positive; got se={se}")

        or_val = math.exp(beta)

        z_crit = _z_critical(alpha)
        ci = ConfidenceInterval(
            lower=math.exp(beta - z_crit * se),
            upper=math.exp(beta + z_crit * se),
            level=1.0 - alpha,
        )

        logger.debug(
            "Odds ratio = %.4f [%.4f, %.4f] (beta=%.4f, SE=%.4f)",
            or_val,
            ci.lower,
            ci.upper,
            beta,
            se,
        )
        return or_val, ci

    @staticmethod
    def standardized_beta(
        beta: float,
        sd_x: float,
        sd_y: float,
    ) -> float:
        """Compute the standardised regression coefficient.

        Rescales the unstandardised *beta* so that it represents the
        change in *Y* (in SD units) per one-SD change in *X*.  This
        allows comparison of effect magnitudes across exposures that
        are measured on different scales.

        Parameters
        ----------
        beta:
            Unstandardised regression coefficient.
        sd_x:
            Standard deviation of the exposure variable.
        sd_y:
            Standard deviation of the outcome variable.

        Returns
        -------
        float
            The standardised beta coefficient.

        Raises
        ------
        EffectSizeError
            If either standard deviation is non-positive.
        """
        if sd_x <= 0:
            raise EffectSizeError(f"sd_x must be positive; got {sd_x}")
        if sd_y <= 0:
            raise EffectSizeError(f"sd_y must be positive; got {sd_y}")

        std_beta = beta * (sd_x / sd_y)

        logger.debug(
            "Standardised beta = %.4f (beta=%.4f, sd_x=%.3f, sd_y=%.3f)",
            std_beta,
            beta,
            sd_x,
            sd_y,
        )
        return std_beta

    @staticmethod
    def interpret_cohens_d(d: float) -> str:
        """Return a human-readable interpretation of a Cohen's d value.

        Uses the conventional thresholds from Cohen (1988):

        * |d| < 0.2: negligible
        * 0.2 <= |d| < 0.5: small
        * 0.5 <= |d| < 0.8: medium
        * |d| >= 0.8: large

        Parameters
        ----------
        d:
            The Cohen's d effect size.

        Returns
        -------
        str
            One of ``"negligible"``, ``"small"``, ``"medium"``, or
            ``"large"``.
        """
        abs_d = abs(d)
        if abs_d < 0.2:
            return "negligible"
        if abs_d < 0.5:
            return "small"
        if abs_d < 0.8:
            return "medium"
        return "large"

    @staticmethod
    def interpret_odds_ratio(or_val: float) -> str:
        """Return a human-readable interpretation of an odds ratio.

        Uses the Chen et al. (2010) thresholds that map ORs to Cohen's
        d equivalents:

        * OR near 1.0 (0.87 - 1.15): negligible
        * OR 1.15 - 1.86 (or 0.54 - 0.87): small
        * OR 1.86 - 3.00 (or 0.33 - 0.54): medium
        * OR > 3.00 (or < 0.33): large

        Parameters
        ----------
        or_val:
            The odds ratio.

        Returns
        -------
        str
            One of ``"negligible"``, ``"small"``, ``"medium"``, or
            ``"large"``.
        """
        if or_val <= 0:
            return "invalid"

        # Normalise to OR >= 1 for threshold comparison.
        or_norm = or_val if or_val >= 1.0 else 1.0 / or_val

        if or_norm < 1.15:
            return "negligible"
        if or_norm < 1.86:
            return "small"
        if or_norm < 3.00:
            return "medium"
        return "large"


# -------------------------------------------------------------------
# Module-level helpers
# -------------------------------------------------------------------


def _z_critical(alpha: float) -> float:
    """Return the two-sided z critical value for significance level *alpha*.

    For the default alpha=0.05 this returns 1.96.
    """
    from scipy.stats import norm

    return float(norm.ppf(1.0 - alpha / 2.0))

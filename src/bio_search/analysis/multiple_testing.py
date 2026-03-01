"""Multiple-testing correction methods for EWAS p-value adjustment.

When an EWAS scans hundreds of exposures against a single outcome, the
probability of false positives rises dramatically.  This module provides
three classical correction methods:

1. **Benjamini-Hochberg (BH)** -- controls the *false discovery rate*
   (FDR), i.e. the expected proportion of rejected nulls that are truly
   null.  This is the default in EWAS because it is less conservative
   than family-wise error rate methods, which is appropriate when the
   goal is hypothesis generation rather than confirmatory testing.

2. **Bonferroni** -- controls the *family-wise error rate* (FWER) by
   multiplying every p-value by the number of tests.  Very conservative;
   useful when a small number of highly credible hits is needed.

3. **Holm (step-down Bonferroni)** -- a uniformly more powerful variant
   of Bonferroni that still controls the FWER.

All three methods accept a flat list of raw p-values and return a list
of adjusted p-values in the *same order* as the input.

Reference
---------
Benjamini Y, Hochberg Y.  Controlling the false discovery rate: a
practical and powerful approach to multiple testing.  *JRSS-B* 1995;
57(1):289-300.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MultipleTestingCorrector:
    """Static methods for p-value adjustment across a family of tests."""

    # ------------------------------------------------------------------
    # Benjamini-Hochberg FDR
    # ------------------------------------------------------------------
    @staticmethod
    def benjamini_hochberg(p_values: list[float], alpha: float = 0.05) -> list[float]:
        """Benjamini-Hochberg FDR correction.

        Parameters
        ----------
        p_values:
            Raw (unadjusted) p-values.
        alpha:
            Nominal FDR level.  Not used in the adjustment formula itself
            but retained in the signature for API consistency -- callers
            may use it to threshold the adjusted values.

        Returns
        -------
        list[float]
            Adjusted p-values in the same order as the input.  Each
            value is clamped to [0, 1].
        """
        n = len(p_values)
        if n == 0:
            return []

        # Sort by raw p-value (ascending), keeping the original index.
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])

        adjusted = [0.0] * n

        # Walk backwards (largest rank first) enforcing monotonicity:
        # adj_p[i] = min(adj_p[i+1], p_i * n / rank_i)
        prev = 1.0
        for i in range(n - 1, -1, -1):
            rank = i + 1
            orig_idx, p = indexed[i]
            adj_p = min(prev, p * n / rank)
            adj_p = min(adj_p, 1.0)
            adjusted[orig_idx] = adj_p
            prev = adj_p

        return adjusted

    # ------------------------------------------------------------------
    # Bonferroni
    # ------------------------------------------------------------------
    @staticmethod
    def bonferroni(p_values: list[float]) -> list[float]:
        """Bonferroni correction.

        Multiplies every p-value by the number of tests.  Simple and very
        conservative.

        Parameters
        ----------
        p_values:
            Raw p-values.

        Returns
        -------
        list[float]
            Adjusted p-values clamped to [0, 1].
        """
        n = len(p_values)
        if n == 0:
            return []
        return [min(p * n, 1.0) for p in p_values]

    # ------------------------------------------------------------------
    # Holm (step-down Bonferroni)
    # ------------------------------------------------------------------
    @staticmethod
    def holm(p_values: list[float]) -> list[float]:
        """Holm-Bonferroni step-down correction.

        Uniformly more powerful than Bonferroni while still controlling
        the family-wise error rate.

        Parameters
        ----------
        p_values:
            Raw p-values.

        Returns
        -------
        list[float]
            Adjusted p-values in the same order as the input.
        """
        n = len(p_values)
        if n == 0:
            return []

        # Sort ascending by raw p-value.
        indexed = sorted(enumerate(p_values), key=lambda x: x[1])

        adjusted = [0.0] * n

        # Walk forward (smallest p first), enforcing monotonicity
        # upward: adj_p[i] = max(adj_p[i-1], p_i * (n - i)).
        prev = 0.0
        for i, (orig_idx, p) in enumerate(indexed):
            adj_p = max(prev, p * (n - i))
            adj_p = min(adj_p, 1.0)
            adjusted[orig_idx] = adj_p
            prev = adj_p

        return adjusted

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    @staticmethod
    def correct(
        p_values: list[float],
        method: str = "benjamini-hochberg",
        alpha: float = 0.05,
    ) -> list[float]:
        """Apply the specified correction method.

        Parameters
        ----------
        p_values:
            Raw p-values.
        method:
            One of ``"benjamini-hochberg"`` (default), ``"bonferroni"``,
            or ``"holm"``.
        alpha:
            Significance level forwarded to BH.

        Returns
        -------
        list[float]
            Adjusted p-values.

        Raises
        ------
        ValueError
            If *method* is not recognised.
        """
        method_lower = method.lower().replace("_", "-")

        if method_lower in ("benjamini-hochberg", "bh", "fdr"):
            return MultipleTestingCorrector.benjamini_hochberg(p_values, alpha)
        if method_lower in ("bonferroni", "bonf"):
            return MultipleTestingCorrector.bonferroni(p_values)
        if method_lower in ("holm", "holm-bonferroni"):
            return MultipleTestingCorrector.holm(p_values)

        valid = ("benjamini-hochberg", "bonferroni", "holm")
        raise ValueError(
            f"Unknown correction method {method!r}. Choose from {valid}."
        )

"""Cross-cycle temporal trend analysis for NHANES associations.

NHANES releases data in multi-year cycles (e.g. 2013-2014, 2015-2016,
2017-2018).  Running the same regression across multiple cycles reveals
whether an exposure-outcome relationship is strengthening, weakening,
or stable over time.  This is valuable for:

* **Replication** -- an association that replicates across 3+ cycles is
  far more credible than one from a single cycle.
* **Secular trends** -- declining blood lead levels in the US population
  may weaken lead-health associations over time.
* **Policy evaluation** -- environmental regulations should shrink
  harmful associations in later cycles.

The ``TrendAnalyzer`` runs identical models in each cycle and returns
the per-cycle results tagged with ``cycle=<id>`` in the covariate list
so downstream code can plot beta trajectories.

Limitations
-----------
* No formal test for trend across cycles is performed (e.g. no
  meta-regression on cycle year).  The results are descriptive.
* Survey weights differ across cycles; each cycle uses its own weight
  column without cross-cycle recalibration.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from bio_search.models.analysis import AssociationResult
    from bio_search.survey.estimator import SurveyEstimator

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Runs identical regressions across NHANES cycles.

    Parameters
    ----------
    estimator:
        A ``SurveyEstimator`` wrapping the survey design.  Note that
        when analysing multiple cycles, each cycle's DataFrame should
        contain its own weight/strata/PSU columns.
    """

    def __init__(self, estimator: SurveyEstimator) -> None:
        from bio_search.analysis.regression import RegressionAnalyzer

        self.estimator = estimator
        self.analyzer = RegressionAnalyzer(estimator)

    # ------------------------------------------------------------------
    # Core method
    # ------------------------------------------------------------------
    def cross_cycle_trend(
        self,
        cycle_dfs: dict[str, pd.DataFrame],
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
        min_n: int = 100,
    ) -> list[AssociationResult]:
        """Run the same model in each cycle and collect results.

        Parameters
        ----------
        cycle_dfs:
            Mapping from cycle identifier (e.g. ``"2017-2018"``) to the
            merged analysis DataFrame for that cycle.
        outcome:
            Outcome variable name.
        exposure:
            Exposure variable name.
        covariates:
            Adjustment covariates.  Defaults to ``None`` (no covariates
            beyond the exposure).
        min_n:
            Minimum complete-case observations required per cycle.
            Cycles with fewer rows are skipped.

        Returns
        -------
        list[AssociationResult]
            One result per successfully analysed cycle, ordered
            chronologically.  Each result carries a synthetic covariate
            entry ``"cycle=<cycle_id>"`` so callers can identify which
            cycle it belongs to.
        """
        if not cycle_dfs:
            logger.warning("TrendAnalyzer: no cycle DataFrames provided")
            return []

        results: list[AssociationResult] = []
        n_skipped = 0
        n_failed = 0

        for cycle_id in sorted(cycle_dfs.keys()):
            df = cycle_dfs[cycle_id]

            # Verify the required columns exist in this cycle.
            missing_cols = []
            for col in [outcome, exposure]:
                if col not in df.columns:
                    missing_cols.append(col)
            if missing_cols:
                logger.debug(
                    "TrendAnalyzer: skipping cycle %s (missing columns: %s)",
                    cycle_id, missing_cols,
                )
                n_skipped += 1
                continue

            # Filter covariates to those present in this cycle.
            cycle_cov = [
                c for c in (covariates or [])
                if c in df.columns
            ]

            # Build required columns and do complete-case deletion.
            required = [outcome, exposure] + cycle_cov
            available = [c for c in required if c in df.columns]
            subset = df[available].dropna()

            if len(subset) < min_n:
                logger.debug(
                    "TrendAnalyzer: skipping cycle %s (n=%d < min_n=%d)",
                    cycle_id, len(subset), min_n,
                )
                n_skipped += 1
                continue

            try:
                r = self.analyzer.run(df, outcome, exposure, cycle_cov)
                # Prepend cycle identifier to covariates for downstream
                # identification.
                r.covariates = [f"cycle={cycle_id}"] + r.covariates
                results.append(r)
            except Exception:
                n_failed += 1
                logger.warning(
                    "TrendAnalyzer: regression failed for cycle %s",
                    cycle_id, exc_info=True,
                )

        logger.info(
            "TrendAnalyzer: %d cycle results (%d skipped, %d failed) "
            "for %s -> %s",
            len(results), n_skipped, n_failed, exposure, outcome,
        )

        return results

    # ------------------------------------------------------------------
    # Summary helpers
    # ------------------------------------------------------------------
    def direction_summary(
        self,
        cycle_results: list[AssociationResult],
    ) -> str:
        """Return a human-readable summary of the trend direction.

        Looks at the sign and magnitude of betas across cycles:
        * ``"consistent positive"`` -- all betas > 0
        * ``"consistent negative"`` -- all betas < 0
        * ``"mixed"`` -- betas change sign across cycles
        * ``"strengthening"`` -- |beta| is increasing over time
        * ``"weakening"`` -- |beta| is decreasing over time
        * ``"insufficient data"`` -- fewer than 2 cycle results

        Parameters
        ----------
        cycle_results:
            Ordered list of per-cycle ``AssociationResult`` objects
            (as returned by ``cross_cycle_trend``).

        Returns
        -------
        str
            One of the summary labels above.
        """
        if len(cycle_results) < 2:
            return "insufficient data"

        betas = [r.beta for r in cycle_results]
        signs = [b > 0 for b in betas]

        if not all(s == signs[0] for s in signs):
            return "mixed"

        direction = "positive" if signs[0] else "negative"

        # Check whether magnitude is growing or shrinking.
        abs_betas = [abs(b) for b in betas]
        if all(abs_betas[i] <= abs_betas[i + 1] for i in range(len(abs_betas) - 1)):
            return "strengthening"
        if all(abs_betas[i] >= abs_betas[i + 1] for i in range(len(abs_betas) - 1)):
            return "weakening"

        return f"consistent {direction}"

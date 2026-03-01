"""Environment-Wide Association Study (EWAS) scanner.

An EWAS systematically tests *every* available exposure variable in a
dataset against a single outcome of interest.  The idea was popularised
by Chirag Patel's 2010 paper in *PLoS ONE* and has since become a
standard hypothesis-generating tool in environmental epidemiology.

The workflow is:

1. **Candidate filtering** -- drop survey-design columns, IDs, weights,
   columns with too many missing values, and constants.
2. **Regression loop** -- for each surviving exposure, run a
   survey-weighted regression (linear or logistic depending on outcome
   type) adjusted for a default covariate set (age, sex,
   race/ethnicity, income-to-poverty ratio).
3. **FDR correction** -- apply Benjamini-Hochberg to the raw p-values.
4. **Packaging** -- return an ``EWASResult`` containing all individual
   ``AssociationResult`` rows, sorted by p-value.

Design decisions
----------------
* We intentionally run regressions *sequentially* rather than with
  ``ProcessPoolExecutor``.  Pandas DataFrames are expensive to
  serialise across process boundaries, and the per-model runtime
  (~5 ms with statsmodels) means the total wall time for 300 exposures
  is about 1.5 seconds -- fast enough for an interactive TUI.  If this
  becomes a bottleneck in the future, we can shard the exposure list
  and multiprocess at that level.

* The ``progress_callback`` hook lets the TUI update a progress bar
  after each exposure is tested.

Reference
---------
Patel CJ, Bhattacharya J, Butte AJ.  An environment-wide association
study (EWAS) on type 2 diabetes mellitus.  *PLoS ONE* 2010;5(5):e10746.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

import pandas as pd

from bio_search.analysis.multiple_testing import MultipleTestingCorrector
from bio_search.models.analysis import AssociationResult, EWASResult

if TYPE_CHECKING:
    from bio_search.analysis.regression import RegressionAnalyzer
    from bio_search.survey.design import SurveyDesign

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Variables that must never be used as EWAS exposures.
# Survey-design columns, IDs, and sampling weights are infrastructure,
# not scientific variables.
# ---------------------------------------------------------------------------
SKIP_PREFIXES: tuple[str, ...] = ("SEQ", "SDM", "WTM", "WTI", "SDN")

SKIP_VARS: frozenset[str] = frozenset({
    "SEQN",         # Respondent sequence number (row ID)
    "SDMVSTRA",     # Variance estimation stratum
    "SDMVPSU",      # Primary sampling unit
    "WTMEC2YR",     # MEC exam 2-year weight
    "WTINT2YR",     # Interview 2-year weight
    "WTMECPRP",     # MEC exam weight (pre-pandemic)
    "WTINTPRP",     # Interview weight (pre-pandemic)
    "WTSAFPRP",     # Fasting subsample weight
    "RIDSTATR",     # Interview/exam status
    "RIDAGEYR",     # Age (used as covariate, not exposure)
    "RIAGENDR",     # Sex (used as covariate, not exposure)
    "RIDRETH3",     # Race/ethnicity (used as covariate)
    "INDFMPIR",     # Income-to-poverty ratio (covariate)
})

DEFAULT_COVARIATES: list[str] = [
    "RIDAGEYR",     # Age
    "RIAGENDR",     # Sex
    "RIDRETH3",     # Race/ethnicity
    "INDFMPIR",     # Income-to-poverty ratio
]


class EWASScanner:
    """Scans all candidate exposures against a single outcome.

    Parameters
    ----------
    min_n:
        Minimum number of complete-case observations required for a
        regression to run.  Exposure-outcome pairs with fewer rows
        after dropping missing values are silently skipped.
    max_missing_pct:
        Maximum fraction of missing values (0-1) allowed in an
        exposure column before it is excluded from the scan.
    n_workers:
        Reserved for future parallel execution.  Currently unused.
    fdr_alpha:
        Family-wise significance level passed to Benjamini-Hochberg.
    """

    def __init__(
        self,
        min_n: int = 200,
        max_missing_pct: float = 0.5,
        n_workers: int = 4,
        fdr_alpha: float = 0.05,
    ) -> None:
        self.min_n = min_n
        self.max_missing_pct = max_missing_pct
        self.n_workers = n_workers
        self.fdr_alpha = fdr_alpha

    # ------------------------------------------------------------------
    # Candidate filtering
    # ------------------------------------------------------------------
    def get_candidate_exposures(
        self,
        df: pd.DataFrame,
        outcome: str,
    ) -> list[str]:
        """Return column names eligible to serve as EWAS exposures.

        A column is excluded if it:
        - is the outcome variable itself,
        - is a known survey-design / ID / weight column,
        - has a prefix in ``SKIP_PREFIXES``,
        - has more than ``max_missing_pct`` missing values, or
        - is a constant (fewer than 2 unique non-missing values).

        Parameters
        ----------
        df:
            The merged analysis DataFrame.
        outcome:
            Name of the outcome variable (will be excluded).

        Returns
        -------
        list[str]
            Sorted list of candidate exposure column names.
        """
        candidates: list[str] = []

        for col in df.columns:
            # Never test the outcome against itself.
            if col == outcome:
                continue

            # Skip infrastructure columns.
            if col in SKIP_VARS:
                continue
            if any(col.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue

            # Too many missing values.
            missing_pct = df[col].isna().mean()
            if missing_pct > self.max_missing_pct:
                logger.debug(
                    "EWAS: skipping %s (%.0f%% missing > %.0f%% threshold)",
                    col,
                    missing_pct * 100,
                    self.max_missing_pct * 100,
                )
                continue

            # Constants provide no information.
            n_unique = df[col].dropna().nunique()
            if n_unique < 2:
                logger.debug("EWAS: skipping %s (constant, %d unique value)", col, n_unique)
                continue

            candidates.append(col)

        candidates.sort()
        return candidates

    # ------------------------------------------------------------------
    # Main scan
    # ------------------------------------------------------------------
    def scan(
        self,
        df: pd.DataFrame,
        outcome: str,
        design: SurveyDesign,
        covariates: list[str] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> EWASResult:
        """Run an environment-wide association study.

        Parameters
        ----------
        df:
            Merged analysis DataFrame with outcome, exposures,
            covariates, and survey-design columns.
        outcome:
            Name of the outcome column to test every exposure against.
        design:
            Configured ``SurveyDesign`` instance for weighted analysis.
        covariates:
            Adjustment variables.  Defaults to ``DEFAULT_COVARIATES``
            (age, sex, race/ethnicity, income) if present in *df*.
        progress_callback:
            Optional ``(completed, total, current_variable)`` callable
            invoked after each exposure is tested.

        Returns
        -------
        EWASResult
            Container with all ``AssociationResult`` rows, FDR-adjusted
            p-values, and metadata.
        """
        from bio_search.analysis.regression import RegressionAnalyzer
        from bio_search.survey.estimator import SurveyEstimator

        # Default covariates: keep only those present in the data and
        # not equal to the outcome.
        if covariates is None:
            covariates = [
                c for c in DEFAULT_COVARIATES
                if c in df.columns and c != outcome
            ]

        exposures = self.get_candidate_exposures(df, outcome)
        n_exposures = len(exposures)
        logger.info(
            "EWAS: testing %d candidate exposures against %s "
            "(covariates=%s, min_n=%d)",
            n_exposures,
            outcome,
            covariates,
            self.min_n,
        )

        if n_exposures == 0:
            logger.warning("EWAS: no candidate exposures found for %s", outcome)
            return EWASResult(
                outcome=outcome,
                associations=[],
                n_tests=0,
                timestamp=datetime.now(timezone.utc),
            )

        estimator = SurveyEstimator(design)
        analyzer = RegressionAnalyzer(estimator)

        results: list[AssociationResult] = []
        n_skipped = 0
        n_failed = 0

        for i, exposure in enumerate(exposures):
            try:
                result = self._test_single(
                    df, outcome, exposure, covariates, analyzer, design,
                )
                if result is not None:
                    results.append(result)
                else:
                    n_skipped += 1
            except Exception:
                n_failed += 1
                logger.warning(
                    "EWAS: failed to test %s -> %s", exposure, outcome, exc_info=True,
                )

            if progress_callback is not None:
                progress_callback(i + 1, n_exposures, exposure)

        logger.info(
            "EWAS: completed %d associations (%d skipped, %d failed) out of %d candidates",
            len(results),
            n_skipped,
            n_failed,
            n_exposures,
        )

        # ----- FDR correction -----
        if results:
            raw_p = [r.p_value for r in results]
            adjusted_p = MultipleTestingCorrector.benjamini_hochberg(raw_p, self.fdr_alpha)
            for r, fp in zip(results, adjusted_p):
                r.fdr_p = fp

            # Sort by raw p-value (most significant first).
            results.sort(key=lambda r: r.p_value)

        return EWASResult(
            outcome=outcome,
            associations=results,
            n_tests=n_exposures,
            fdr_method="benjamini-hochberg",
            timestamp=datetime.now(timezone.utc),
        )

    # ------------------------------------------------------------------
    # Single-exposure test
    # ------------------------------------------------------------------
    def _test_single(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str],
        analyzer: RegressionAnalyzer,
        design: SurveyDesign,
    ) -> AssociationResult | None:
        """Test a single exposure-outcome pair.

        Returns ``None`` if the complete-case sample is too small.

        Parameters
        ----------
        df:
            Full analysis DataFrame.
        outcome:
            Outcome column name.
        exposure:
            Exposure column name being tested.
        covariates:
            Adjustment covariates.
        analyzer:
            Pre-configured ``RegressionAnalyzer``.
        design:
            Survey design (used to look up weight/strata/PSU column
            names so they are included in the complete-case subset).
        """
        # Build the minimal column set needed for this regression.
        cols = [outcome, exposure] + covariates
        design_cols = [design.weight_col, design.strata_col, design.psu_col]
        for dc in design_cols:
            if dc in df.columns and dc not in cols:
                cols.append(dc)

        # Keep only columns that actually exist.
        cols = [c for c in cols if c in df.columns]

        # Complete-case analysis: drop rows missing any required column.
        subset = df[cols].dropna()

        if len(subset) < self.min_n:
            logger.debug(
                "EWAS: skipping %s (n=%d < min_n=%d after dropping missing)",
                exposure,
                len(subset),
                self.min_n,
            )
            return None

        return analyzer.run(subset, outcome, exposure, covariates)

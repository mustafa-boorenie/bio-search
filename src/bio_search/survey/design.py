"""NHANES complex survey design specification and data preparation.

NHANES uses a stratified, multi-stage probability sampling design to
produce estimates that are representative of the civilian
non-institutionalised US population.  Three columns carry the design
information:

+------------+---------------------------------------------------+
| Column     | Role                                              |
+============+===================================================+
| SDMVSTRA   | Variance-estimation stratum (masked)               |
| SDMVPSU    | Primary Sampling Unit (cluster) within stratum     |
| WTMEC2YR   | MEC exam weight (or WTINT2YR for interview-only)   |
+------------+---------------------------------------------------+

Any analysis that does not account for these three columns will produce
**incorrect standard errors** and potentially **biased point estimates**.
This module wraps the validation and preparation logic so downstream
code (estimators, regressions) receives clean, ready-to-use data.

Reference
---------
CDC, "NHANES Analytic Guidelines":
    https://wwwn.cdc.gov/nchs/nhanes/analyticguidelines.aspx
"""

from __future__ import annotations

import logging

import pandas as pd

from bio_search.models.survey import SurveyDesignSpec
from bio_search.survey.weights import WeightSelector

logger = logging.getLogger(__name__)


class SurveyDesign:
    """Manage the NHANES complex survey design for a single analysis.

    This class stores which columns carry the strata, PSU, and weight
    information, validates that a DataFrame contains them, and prepares
    the data (dropping incomplete rows, adjusting weights for multiple
    cycles).

    Parameters
    ----------
    weight_col:
        Name of the sampling-weight column.  Defaults to the MEC exam
        weight.  Use :class:`~bio_search.survey.weights.WeightSelector`
        to pick the right one automatically.
    n_cycles:
        Number of NHANES cycles combined in the analysis DataFrame.
        Weights are divided by this number per CDC guidelines.
    """

    # These column names are fixed across all NHANES cycles (post-2001).
    STRATA_COL: str = "SDMVSTRA"
    PSU_COL: str = "SDMVPSU"

    def __init__(
        self,
        weight_col: str = "WTMEC2YR",
        n_cycles: int = 1,
    ) -> None:
        if n_cycles < 1:
            raise ValueError(f"n_cycles must be >= 1, got {n_cycles}")

        self.weight_col = weight_col
        self.strata_col = self.STRATA_COL
        self.psu_col = self.PSU_COL
        self.n_cycles = n_cycles

    # -----------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------

    def validate(self, df: pd.DataFrame) -> bool:
        """Check whether *df* contains all required survey design columns.

        Parameters
        ----------
        df:
            The analysis DataFrame.

        Returns
        -------
        bool
            ``True`` if the strata, PSU, and weight columns are all
            present; ``False`` otherwise.  Missing columns are logged
            as warnings.
        """
        required = {self.strata_col, self.psu_col, self.weight_col}
        present = set(df.columns)
        missing = required - present

        if missing:
            logger.warning(
                "Survey design columns missing from DataFrame: %s. Available columns: %s",
                sorted(missing),
                sorted(present),
            )
            return False

        logger.debug(
            "All survey design columns present: strata=%s, psu=%s, weight=%s",
            self.strata_col,
            self.psu_col,
            self.weight_col,
        )
        return True

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and adjust a DataFrame for survey-weighted analysis.

        This method:

        1. **Validates** that the required design columns exist.
        2. **Drops rows** where the weight, strata, or PSU is missing
           (those participants cannot contribute to variance estimation).
        3. **Drops rows** with zero or negative weights (non-eligible
           participants).
        4. **Adjusts weights** for multi-cycle combination by dividing
           by *n_cycles*.

        Parameters
        ----------
        df:
            Raw analysis DataFrame, typically produced by merging one or
            more NHANES XPT tables on ``SEQN``.

        Returns
        -------
        pd.DataFrame
            A copy of *df* with incomplete design rows removed and
            weights adjusted.

        Raises
        ------
        ValueError
            If any of the three required design columns is missing.
        """
        if not self.validate(df):
            missing = {self.strata_col, self.psu_col, self.weight_col} - set(df.columns)
            raise ValueError(
                f"Cannot prepare DataFrame -- missing survey design columns: {sorted(missing)}"
            )

        n_before = len(df)
        design_cols = [self.strata_col, self.psu_col, self.weight_col]

        # Drop rows with any missing design variable.
        df = df.dropna(subset=design_cols).copy()
        n_after_na = len(df)
        n_dropped_na = n_before - n_after_na

        # Drop rows with zero or negative weights (non-eligible).
        mask_positive_weight = df[self.weight_col] > 0
        df = df.loc[mask_positive_weight].copy()
        n_after_weight = len(df)
        n_dropped_weight = n_after_na - n_after_weight

        if n_dropped_na > 0:
            logger.info(
                "Dropped %d rows with missing survey design values (%.1f%% of %d)",
                n_dropped_na,
                100.0 * n_dropped_na / max(n_before, 1),
                n_before,
            )

        if n_dropped_weight > 0:
            logger.info(
                "Dropped %d rows with zero/negative weight '%s'",
                n_dropped_weight,
                self.weight_col,
            )

        if n_after_weight == 0:
            logger.warning(
                "All rows were dropped during survey design preparation -- "
                "check that the weight column '%s' has valid values",
                self.weight_col,
            )
            return df

        # Adjust weights for multi-cycle combination.
        df = WeightSelector.adjust_for_cycles(df, self.weight_col, self.n_cycles)

        logger.debug(
            "Survey design preparation complete: %d rows retained (%.1f%% of original %d)",
            n_after_weight,
            100.0 * n_after_weight / max(n_before, 1),
            n_before,
        )
        return df

    def get_spec(self) -> SurveyDesignSpec:
        """Return a serialisable :class:`SurveyDesignSpec` for this design.

        This is useful for recording exactly which design parameters
        were used in an analysis, e.g. when writing results to disk or
        displaying them in the TUI.
        """
        return SurveyDesignSpec(
            weight_col=self.weight_col,
            strata_col=self.strata_col,
            psu_col=self.psu_col,
            n_cycles=self.n_cycles,
        )

    # -----------------------------------------------------------------
    # Dunder helpers
    # -----------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"SurveyDesign(weight_col={self.weight_col!r}, "
            f"strata_col={self.strata_col!r}, "
            f"psu_col={self.psu_col!r}, "
            f"n_cycles={self.n_cycles})"
        )

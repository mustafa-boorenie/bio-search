"""Survey weight selection logic for NHANES analyses.

NHANES provides two sets of 2-year sampling weights:

* **WTMEC2YR** -- Mobile Examination Center (MEC) exam weight.  Use this
  whenever the analysis includes *any* variable collected during the
  physical examination or laboratory session (blood draws, body
  measurements, etc.).
* **WTINT2YR** -- Interview weight.  Use this when the analysis uses
  *only* data collected during the household interview (demographics,
  questionnaires).

The rule is simple: if even one variable in the analysis comes from a
lab or exam table, the MEC weight must be used because only a subset
of interviewed participants actually visited the MEC.  Using the
interview weight in that case would produce biased estimates.

When combining multiple NHANES cycles (e.g. 2017-2018 + 2019-2020),
the CDC analytic guidelines require dividing the weight by the number
of cycles so that the weighted total still approximates the US
population *once*, not N times.

Reference
---------
CDC, "NHANES Analytic Guidelines, 2011-2014 and 2015-2016":
    https://wwwn.cdc.gov/nchs/nhanes/analyticguidelines.aspx
"""

from __future__ import annotations

import logging

import pandas as pd

from bio_search.models.nhanes import DataComponent

logger = logging.getLogger(__name__)


class WeightSelector:
    """Select the correct NHANES sampling-weight column for an analysis.

    The decision depends on which data components (tables) are involved.
    If *any* component is from the examination or laboratory domain, the
    MEC exam weight is required.  Otherwise the interview weight suffices.
    """

    # MEC exam weight -- for laboratory / examination data
    MEC_WEIGHT: str = "WTMEC2YR"

    # Interview weight -- for questionnaire-only analyses
    INTERVIEW_WEIGHT: str = "WTINT2YR"

    # Data components that mandate the MEC exam weight
    MEC_COMPONENTS: set[DataComponent] = {
        DataComponent.LABORATORY,
        DataComponent.EXAMINATION,
    }

    @staticmethod
    def select_weight(components: set[DataComponent]) -> str:
        """Choose the appropriate weight column for the given components.

        Parameters
        ----------
        components:
            Set of :class:`DataComponent` values representing every
            NHANES table domain used in the analysis.

        Returns
        -------
        str
            ``"WTMEC2YR"`` if any component requires the MEC exam, or
            ``"WTINT2YR"`` for interview-only analyses.
        """
        if components & WeightSelector.MEC_COMPONENTS:
            logger.debug(
                "Components %s include lab/exam data -- selecting MEC weight %s",
                components,
                WeightSelector.MEC_WEIGHT,
            )
            return WeightSelector.MEC_WEIGHT

        logger.debug(
            "Components %s are interview-only -- selecting interview weight %s",
            components,
            WeightSelector.INTERVIEW_WEIGHT,
        )
        return WeightSelector.INTERVIEW_WEIGHT

    @staticmethod
    def adjust_for_cycles(
        df: pd.DataFrame,
        weight_col: str,
        n_cycles: int,
    ) -> pd.DataFrame:
        """Divide sampling weights by the number of combined cycles.

        Per CDC analytic guidelines, when data from multiple NHANES
        cycles are appended together, the weight column must be divided
        by the number of cycles so that the weighted total still
        approximates the civilian non-institutionalised US population
        once (not *n_cycles* times).

        Parameters
        ----------
        df:
            DataFrame that contains ``weight_col``.
        weight_col:
            Name of the weight column to adjust.
        n_cycles:
            Number of NHANES cycles combined.  If 1 (single cycle),
            the DataFrame is returned unchanged.

        Returns
        -------
        pd.DataFrame
            A copy of *df* with the weight column divided by *n_cycles*,
            or the original DataFrame if *n_cycles* <= 1.

        Raises
        ------
        ValueError
            If *n_cycles* < 1 or *weight_col* is missing from *df*.
        """
        if n_cycles < 1:
            raise ValueError(f"n_cycles must be >= 1, got {n_cycles}")

        if weight_col not in df.columns:
            raise ValueError(
                f"Weight column '{weight_col}' not found in DataFrame. "
                f"Available columns: {list(df.columns)}"
            )

        if n_cycles == 1:
            logger.debug("Single cycle -- no weight adjustment needed")
            return df

        logger.info(
            "Adjusting weight column '%s' for %d combined cycles (dividing by %d)",
            weight_col,
            n_cycles,
            n_cycles,
        )
        df = df.copy()
        df[weight_col] = df[weight_col] / n_cycles
        return df

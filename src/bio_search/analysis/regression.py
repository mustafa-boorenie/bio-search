"""High-level regression analysis interface for NHANES data.

This module wraps :class:`~bio_search.survey.estimator.SurveyEstimator`
with convenience logic that most NHANES analyses need:

* **Auto-select model type** -- binary outcomes get logistic regression,
  everything else gets linear regression.
* **Default covariate adjustment** -- unless the caller specifies
  covariates explicitly, the standard NHANES confounders (age, sex,
  race/ethnicity, income-to-poverty ratio) are included if they exist
  in the DataFrame.
* **Input validation** -- missing columns, insufficient sample size, and
  degenerate data are caught early with clear error messages.

The default covariates follow the "minimum adjustment set" convention
used in most published NHANES epidemiology papers.  They map to the
NHANES DEMO table variables:

+-----------+------------------------------------------------+
| Variable  | Description                                    |
+===========+================================================+
| RIDAGEYR  | Age in years at screening                      |
| RIAGENDR  | Gender (1=Male, 2=Female)                      |
| RIDRETH3  | Race/Hispanic origin with NH Asian (6 levels)  |
| INDFMPIR  | Ratio of family income to poverty threshold    |
+-----------+------------------------------------------------+
"""

from __future__ import annotations

import logging

import pandas as pd

from bio_search.models.analysis import AssociationResult
from bio_search.survey.estimator import SurveyEstimator

logger = logging.getLogger(__name__)


class RegressionAnalyzer:
    """High-level regression interface with sensible defaults.

    Parameters
    ----------
    estimator:
        A configured :class:`SurveyEstimator` that handles the actual
        survey-weighted model fitting.
    """

    # Standard NHANES demographic confounders.  These are included by
    # default whenever they appear in the analysis DataFrame.
    DEFAULT_COVARIATES: list[str] = [
        "RIDAGEYR",  # age in years
        "RIAGENDR",  # gender (1=M, 2=F)
        "RIDRETH3",  # race/ethnicity (6 levels)
        "INDFMPIR",  # income-to-poverty ratio
    ]

    def __init__(self, estimator: SurveyEstimator) -> None:
        self.estimator = estimator

    def auto_select_model(self, df: pd.DataFrame, outcome: str) -> str:
        """Decide whether to use linear or logistic regression.

        The heuristic is straightforward: if the outcome column has
        exactly two unique non-missing values, treat it as binary and
        use logistic regression.  Otherwise, use linear regression.

        This matches the convention in the published NHANES literature
        where binary health outcomes (diabetes yes/no, hypertension
        yes/no) are modelled with logistic regression, and continuous
        biomarkers (glucose, BMI, blood pressure) are modelled with
        linear regression.

        Parameters
        ----------
        df:
            The analysis DataFrame.
        outcome:
            Name of the outcome variable.

        Returns
        -------
        str
            ``"logistic"`` for binary outcomes, ``"linear"`` otherwise.
        """
        if outcome not in df.columns:
            logger.warning(
                "Outcome '%s' not in DataFrame -- defaulting to linear model",
                outcome,
            )
            return "linear"

        unique_count = df[outcome].dropna().nunique()

        if unique_count == 2:
            logger.debug(
                "Outcome '%s' has 2 unique values -- selecting logistic regression",
                outcome,
            )
            return "logistic"

        logger.debug(
            "Outcome '%s' has %d unique values -- selecting linear regression",
            outcome,
            unique_count,
        )
        return "linear"

    def _resolve_covariates(
        self,
        df: pd.DataFrame,
        exposure: str,
        outcome: str,
        covariates: list[str] | None,
    ) -> list[str]:
        """Build the final covariate list.

        If the caller passes ``None``, select all default covariates
        that (a) exist in the DataFrame, (b) are not the exposure or
        outcome, and (c) have at least two unique values (constant
        columns would make the design matrix singular).

        If the caller passes an explicit list (including an empty list),
        use it as-is.
        """
        if covariates is not None:
            return covariates

        resolved = []
        for cov in self.DEFAULT_COVARIATES:
            if cov not in df.columns:
                continue
            if cov == exposure or cov == outcome:
                continue
            # Exclude constant columns to avoid singular design matrices.
            if df[cov].dropna().nunique() < 2:
                logger.debug(
                    "Skipping default covariate '%s' -- no variation",
                    cov,
                )
                continue
            resolved.append(cov)

        logger.debug(
            "Auto-selected covariates for %s ~ %s: %s",
            outcome,
            exposure,
            resolved,
        )
        return resolved

    def run(
        self,
        df: pd.DataFrame,
        outcome: str,
        exposure: str,
        covariates: list[str] | None = None,
        model_type: str | None = None,
    ) -> AssociationResult:
        """Run a survey-weighted regression model.

        This is the primary entry point.  It resolves covariates, picks
        the model type if not specified, and delegates to the
        :class:`SurveyEstimator`.

        Parameters
        ----------
        df:
            Analysis-ready DataFrame (already passed through
            :meth:`SurveyDesign.prepare`).
        outcome:
            Name of the outcome (dependent) variable.
        exposure:
            Name of the exposure (independent) variable of interest.
        covariates:
            Optional explicit covariate list.  Pass ``None`` to use the
            default NHANES confounders; pass ``[]`` for an unadjusted
            model.
        model_type:
            ``"linear"`` or ``"logistic"``.  Pass ``None`` to auto-detect
            from the outcome distribution.

        Returns
        -------
        AssociationResult
            The regression result including beta, SE, p-value, CI, and
            sample size.
        """
        covariates = self._resolve_covariates(df, exposure, outcome, covariates)

        if model_type is None:
            model_type = self.auto_select_model(df, outcome)

        logger.info(
            "Running %s regression: %s ~ %s (covariates: %s)",
            model_type,
            outcome,
            exposure,
            covariates or "(none)",
        )

        if model_type == "logistic":
            return self.estimator.logistic_regression(df, outcome, exposure, covariates)

        return self.estimator.linear_regression(df, outcome, exposure, covariates)

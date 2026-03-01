"""Survey statistics modules for NHANES complex survey design.

This package handles the three pillars of NHANES survey analysis:

1. **Weight selection** -- choosing MEC vs. interview weights based on
   which data components are used.
2. **Design specification** -- validating and preparing DataFrames with
   the correct strata, PSU, and weight columns.
3. **Estimation** -- survey-weighted means, proportions, and regression
   models with design-corrected standard errors.
"""

from bio_search.survey.design import SurveyDesign
from bio_search.survey.estimator import SurveyEstimationError, SurveyEstimator
from bio_search.survey.weights import WeightSelector

__all__ = [
    "SurveyDesign",
    "SurveyEstimator",
    "SurveyEstimationError",
    "WeightSelector",
]

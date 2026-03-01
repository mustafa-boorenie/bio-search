"""Pydantic model for NHANES complex survey design specification.

NHANES uses a stratified, multi-stage probability sampling design.
Every statistical estimate must account for three things:

1. **Sampling weights** -- each respondent represents a different
   number of people in the US population.
2. **Strata** -- the population is divided into non-overlapping
   groups before sampling.
3. **Primary Sampling Units (PSUs)** -- the first-stage clusters
   (typically counties or groups of counties) that are sampled
   within each stratum.

Ignoring the survey design produces incorrect standard errors and
biased point estimates.  The ``SurveyDesignSpec`` model stores the
column names so the analysis engine can configure ``samplics`` or
``statsmodels`` correctly.

When combining multiple NHANES cycles, the sampling weights must be
divided by the number of cycles combined (``n_cycles``).  The CDC
documents this rule in their analytic guidelines.
"""

from pydantic import BaseModel


class SurveyDesignSpec(BaseModel):
    """Column names and parameters for NHANES survey-weighted analysis.

    Attributes:
        weight_col: Name of the column containing the sampling weight.
            Defaults to the MEC exam 2-year weight, which is the most
            common choice for analyses that use physical-exam or lab
            data.
        strata_col: Name of the column containing the variance
            estimation stratum.
        psu_col: Name of the column containing the primary sampling
            unit (cluster) identifier.
        n_cycles: Number of survey cycles being combined.  The weight
            column is divided by this number to produce the combined
            weight, per CDC guidelines.
    """

    weight_col: str = "WTMEC2YR"
    strata_col: str = "SDMVSTRA"
    psu_col: str = "SDMVPSU"
    n_cycles: int = 1

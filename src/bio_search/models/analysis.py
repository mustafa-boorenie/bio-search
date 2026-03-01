"""Pydantic models for statistical analysis results.

Three result containers live here, ordered from fine to coarse:

1. ``AssociationResult`` -- a single exposure-outcome regression.
2. ``EWASResult`` -- an environment-wide association study that bundles
   many ``AssociationResult`` rows for one outcome, plus FDR metadata.
3. ``GuidedAnalysisResult`` -- a deeper dive into one exposure-outcome
   pair with subgroup analyses and trend tests.

All numeric fields use ``float`` rather than ``Decimal`` because the
upstream libraries (statsmodels, scipy) return plain floats and we do
not need arbitrary-precision arithmetic for epidemiological estimates.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Building blocks
# ---------------------------------------------------------------------------

class ConfidenceInterval(BaseModel):
    """A confidence interval around a point estimate.

    Attributes:
        lower: Lower bound of the interval.
        upper: Upper bound of the interval.
        level: Confidence level expressed as a proportion (default 0.95
            for a 95 % CI).
    """

    lower: float
    upper: float
    level: float = 0.95


# ---------------------------------------------------------------------------
# Core association result
# ---------------------------------------------------------------------------

class AssociationResult(BaseModel):
    """Result of a single regression between an exposure and an outcome.

    This is the atomic unit of every analysis the platform runs.
    Whether it is a simple linear model, a survey-weighted logistic
    regression, or one cell of an EWAS Manhattan plot, the result is
    always serialised into this shape.

    Attributes:
        exposure: Short name of the exposure variable.
        outcome: Short name of the outcome variable.
        beta: Regression coefficient (log-odds for logistic models).
        se: Standard error of ``beta``.
        p_value: Two-sided p-value for the null hypothesis beta = 0.
        ci: Confidence interval for ``beta``.
        n: Number of observations used in the model.
        model_type: Type of regression (``"linear"``, ``"logistic"``,
            etc.).
        covariates: List of covariate variable names included in the
            model.
        fdr_p: Benjamini-Hochberg adjusted p-value.  ``None`` before
            FDR correction is applied.
        effect_size: Standardised effect size (Cohen's d, odds ratio,
            etc.) if computed.
        effect_size_type: Label for the effect-size metric (e.g.
            ``"cohens_d"``, ``"odds_ratio"``).
        clinically_significant: Whether the effect exceeds a
            pre-defined clinical-significance threshold.  ``None`` when
            no threshold has been evaluated.
    """

    exposure: str
    outcome: str
    beta: float
    se: float
    p_value: float
    ci: ConfidenceInterval
    n: int
    model_type: str = "linear"
    covariates: list[str] = []
    fdr_p: float | None = None
    effect_size: float | None = None
    effect_size_type: str | None = None
    clinically_significant: bool | None = None


# ---------------------------------------------------------------------------
# Aggregate result containers
# ---------------------------------------------------------------------------

class EWASResult(BaseModel):
    """Environment-Wide Association Study results for one outcome.

    An EWAS tests every available exposure variable against a single
    outcome, producing hundreds or thousands of ``AssociationResult``
    rows.  This container holds them together with the FDR correction
    metadata.

    Attributes:
        outcome: The outcome variable name that was held constant.
        associations: Individual regression results, one per exposure.
        n_tests: Total number of tests performed (used for FDR).
        fdr_method: Multiple-testing correction method applied.
        timestamp: UTC time when the analysis completed.
    """

    outcome: str
    associations: list[AssociationResult]
    n_tests: int
    fdr_method: str = "benjamini-hochberg"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class GuidedAnalysisResult(BaseModel):
    """Deep-dive analysis of a single exposure-outcome relationship.

    After an EWAS flags a promising association, a guided analysis
    re-runs the model with subgroup stratification and dose-response
    trend tests.

    Attributes:
        exposure: The exposure variable under investigation.
        outcome: The outcome variable under investigation.
        primary: The main (unstratified) association result.
        subgroups: Stratified results keyed by the stratification
            variable name.  Each value is a list of results, one per
            stratum level (e.g. ``{"RIAGENDR": [male_result,
            female_result]}``).
        trend: Dose-response trend test results across ordered
            quantiles of the exposure.  ``None`` if no trend test was
            run.
    """

    exposure: str
    outcome: str
    primary: AssociationResult
    subgroups: dict[str, list[AssociationResult]] = {}
    trend: list[AssociationResult] | None = None

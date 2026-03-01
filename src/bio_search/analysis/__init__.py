"""Statistical analysis modules for NHANES association mining.

This package provides higher-level analysis interfaces built on top of
the survey-weighted estimators:

1. **Regression** -- auto-selecting linear vs. logistic models with
   default NHANES confounders.
2. **Correlation** -- survey-weighted Pearson and Spearman coefficients.
3. **Effect sizes** -- Cohen's d, odds ratios, and standardised betas
   with confidence intervals.
4. **EWAS** -- environment-wide association study scanner.
5. **Multiple testing** -- Benjamini-Hochberg, Bonferroni, and Holm
   corrections for p-value adjustment.
6. **Guided analysis** -- deep-dive on a single exposure-outcome pair
   with subgroup breakdowns.
7. **Clinical significance** -- MCID-based relevance assessment.
8. **Subgroup analysis** -- stratified analysis by demographics.
9. **Trend analysis** -- cross-cycle temporal trends.
10. **Engine** -- top-level coordinator.
"""

from bio_search.analysis.clinical import ClinicalSignificanceAssessor
from bio_search.analysis.correlation import CorrelationAnalyzer, CorrelationError
from bio_search.analysis.effect_size import EffectSizeCalculator, EffectSizeError
from bio_search.analysis.engine import AnalysisEngine
from bio_search.analysis.ewas import EWASScanner
from bio_search.analysis.guided import GuidedAnalyzer
from bio_search.analysis.multiple_testing import MultipleTestingCorrector
from bio_search.analysis.regression import RegressionAnalyzer
from bio_search.analysis.subgroup import SubgroupAnalyzer
from bio_search.analysis.trend import TrendAnalyzer

__all__ = [
    "AnalysisEngine",
    "ClinicalSignificanceAssessor",
    "CorrelationAnalyzer",
    "CorrelationError",
    "EffectSizeCalculator",
    "EffectSizeError",
    "EWASScanner",
    "GuidedAnalyzer",
    "MultipleTestingCorrector",
    "RegressionAnalyzer",
    "SubgroupAnalyzer",
    "TrendAnalyzer",
]

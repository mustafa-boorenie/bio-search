"""Clinical significance assessment using MCID thresholds.

Statistical significance (p < 0.05) answers the question "is this effect
real?", but clinical significance answers "does it *matter*?".  A large
NHANES sample can detect a 0.1 mg/dL change in cholesterol with
p < 0.001, but no clinician would act on such a tiny shift.

This module provides:

1. **MCID thresholds** -- Minimal Clinically Important Differences for
   common NHANES biomarkers, sourced from consensus guidelines and
   clinical trial literature.

2. **ClinicalSignificanceAssessor** -- a scorer that combines
   statistical strength (p-value) with practical magnitude (beta vs.
   MCID or Cohen's d) into a single 0-1 clinical significance score.

The score formula weights clinical magnitude more heavily than
statistical strength (60/40 split) because in NHANES -- where sample
sizes are large -- virtually everything is statistically significant,
so the bottleneck is always practical relevance.

Reference thresholds
--------------------
- Fasting glucose: ADA position statement, 5 mg/dL
- HbA1c: DCCT/EDIC, 0.5%
- Cholesterol: ATP-III, 10 mg/dL
- Blood lead: CDC reference value update, 1 ug/dL
- BMI: WHO, 1 kg/m2
- Blood pressure: AHA/ACC 2017 guidelines, 5/3 mmHg
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from bio_search.models.analysis import AssociationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Known MCIDs for common NHANES biomarker variables.
#
# Keys are the NHANES variable short names.  Values are the magnitude of
# change (in the variable's native unit) that is considered the smallest
# clinically meaningful shift.
# ---------------------------------------------------------------------------
MCID_THRESHOLDS: dict[str, float] = {
    # Laboratory - metabolic
    "LBXGLU": 5.0,       # mg/dL fasting glucose
    "LBXSGL": 5.0,       # mg/dL serum glucose (refrigerated)
    "LBXGH": 0.5,        # % glycohemoglobin (HbA1c)

    # Laboratory - lipids
    "LBXTC": 10.0,       # mg/dL total cholesterol
    "LBXTR": 15.0,       # mg/dL triglycerides
    "LBXSTR": 15.0,      # mg/dL triglycerides (refrigerated)
    "LBDLDL": 10.0,      # mg/dL LDL cholesterol
    "LBDHDD": 5.0,       # mg/dL HDL cholesterol

    # Laboratory - kidney
    "LBXSCR": 0.3,       # mg/dL serum creatinine
    "LBXSBU": 5.0,       # mg/dL blood urea nitrogen

    # Laboratory - liver
    "LBXSATSI": 10.0,    # U/L ALT
    "LBXSASSI": 10.0,    # U/L AST

    # Laboratory - metals / toxicology
    "LBXBPB": 1.0,       # ug/dL blood lead
    "LBXBCD": 0.3,       # ug/L blood cadmium
    "LBXTHG": 1.0,       # ug/L total blood mercury
    "LBXCOT": 3.0,       # ng/mL serum cotinine

    # Laboratory - inflammation
    "LBXHSCRP": 1.0,     # mg/L high-sensitivity CRP

    # Laboratory - hematology
    "LBXHGB": 1.0,       # g/dL hemoglobin
    "LBXFER": 15.0,      # ng/mL ferritin

    # Laboratory - thyroid
    "LBXTSH": 1.0,       # mIU/L TSH

    # Laboratory - nutrition
    "LBXVIDMS": 10.0,    # nmol/L 25-OH vitamin D
    "LBXSUA": 1.0,       # mg/dL uric acid

    # Examination - anthropometry
    "BMXBMI": 1.0,       # kg/m2 BMI
    "BMXWT": 2.0,        # kg body weight
    "BMXWAIST": 2.0,     # cm waist circumference

    # Examination - blood pressure (oscillometric averages)
    "BPXOSY": 5.0,       # mmHg systolic BP (average of readings)
    "BPXOSY1": 5.0,      # mmHg systolic BP 1st reading
    "BPXOSY2": 5.0,      # mmHg systolic BP 2nd reading
    "BPXOSY3": 5.0,      # mmHg systolic BP 3rd reading
    "BPXODI": 3.0,       # mmHg diastolic BP (average of readings)
    "BPXODI1": 3.0,      # mmHg diastolic BP 1st reading
    "BPXODI2": 3.0,      # mmHg diastolic BP 2nd reading
    "BPXODI3": 3.0,      # mmHg diastolic BP 3rd reading
}

# Cohen's d thresholds (conventional benchmarks).
_COHENS_D_SMALL = 0.2
_COHENS_D_MEDIUM = 0.5


class ClinicalSignificanceAssessor:
    """Evaluates whether an association has practical/clinical relevance.

    Parameters
    ----------
    custom_thresholds:
        Optional dict of ``{variable_name: mcid_value}`` pairs that
        override or extend the built-in ``MCID_THRESHOLDS``.
    """

    def __init__(
        self,
        custom_thresholds: dict[str, float] | None = None,
    ) -> None:
        self.thresholds: dict[str, float] = {**MCID_THRESHOLDS}
        if custom_thresholds:
            self.thresholds.update(custom_thresholds)

    # ------------------------------------------------------------------
    # Binary assessment
    # ------------------------------------------------------------------
    def is_clinically_significant(self, result: AssociationResult) -> bool:
        """Return ``True`` if the effect exceeds the relevant MCID.

        For outcomes with a known MCID, the beta coefficient is compared
        directly.  For unknown outcomes, a fallback to Cohen's d >= 0.2
        (small effect) is used.  If neither MCID nor effect size is
        available, returns ``False`` conservatively.

        Parameters
        ----------
        result:
            A single regression result.
        """
        # Known biomarker: compare |beta| to MCID.
        if result.outcome in self.thresholds:
            return abs(result.beta) >= self.thresholds[result.outcome]

        # Unknown biomarker: fall back to standardised effect size.
        if result.effect_size is not None:
            return abs(result.effect_size) >= _COHENS_D_SMALL

        return False

    # ------------------------------------------------------------------
    # Continuous score
    # ------------------------------------------------------------------
    def score(self, result: AssociationResult) -> float:
        """Compute a clinical significance score in [0, 1].

        The score blends two components:

        * **Statistical component** (40%) -- how far below 0.05 the
          p-value is, measured on a -log10 scale normalised to 10
          (i.e. p = 1e-10 saturates the component).
        * **Clinical component** (60%) -- how close the effect is to
          the MCID (or to Cohen's d = 0.5 for unknown outcomes).

        Parameters
        ----------
        result:
            A single regression result.

        Returns
        -------
        float
            Score in [0, 1].  Higher is more clinically meaningful.
        """
        # --- Statistical component ---
        # Clamp p to a small positive value to avoid log(0).
        safe_p = max(result.p_value, 1e-300)
        stat_score = min(1.0, -np.log10(safe_p) / 10.0)

        # --- Clinical component ---
        if result.outcome in self.thresholds:
            mcid = self.thresholds[result.outcome]
            clinical_score = min(1.0, abs(result.beta) / mcid)
        elif result.effect_size is not None:
            clinical_score = min(1.0, abs(result.effect_size) / _COHENS_D_MEDIUM)
        else:
            # No threshold and no effect size -- assign a neutral 0.5.
            clinical_score = 0.5

        combined = 0.4 * stat_score + 0.6 * clinical_score
        return round(combined, 4)

    # ------------------------------------------------------------------
    # Batch enrichment
    # ------------------------------------------------------------------
    def enrich(self, results: list[AssociationResult]) -> list[AssociationResult]:
        """Annotate each result with clinical significance metadata.

        Mutates each ``AssociationResult`` in place by setting
        ``clinically_significant`` and returns the same list for
        convenience.

        Parameters
        ----------
        results:
            List of regression results (typically from an EWAS).
        """
        for r in results:
            r.clinically_significant = self.is_clinically_significant(r)
        return results

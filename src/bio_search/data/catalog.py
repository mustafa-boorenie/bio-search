"""NHANES data catalog -- hardcoded index of cycles, tables, and XPT URLs.

This module provides NHANESCatalog, which maps every supported NHANES
release cycle to the XPT files available on the CDC website.  The catalog
is intentionally hardcoded (no network calls) so the TUI can render a
browsable table list instantly on startup.

The catalog covers five major cycles that span the most recent decade of
NHANES data collection, which is the range most useful for contemporary
epidemiological research:

    2021-2023   (suffix _L)   -- most recent release
    2017-2020   (suffix _P)   -- pre-pandemic
    2017-2018   (suffix _J)
    2015-2016   (suffix _I)
    2013-2014   (suffix _H)

Each entry stores the CDC table name, a human-readable label, the data
component category, and the XPT download URL.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bio_search.models.nhanes import (
    DataComponent,
    NHANESTable,
    NHANESVariable,
    VariableType,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CDC base URL (no trailing slash)
# ---------------------------------------------------------------------------
_CDC_BASE = "https://wwwn.cdc.gov/Nchs/Nhanes"


# ---------------------------------------------------------------------------
# Helper: build XPT url
# ---------------------------------------------------------------------------
def _xpt_url(cycle: str, table_name: str) -> str:
    """Return the full CDC download URL for a given table."""
    return f"{_CDC_BASE}/{cycle}/{table_name}.XPT"


# ---------------------------------------------------------------------------
# Per-table metadata (name, label, component)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _TableSpec:
    """Lightweight spec used only inside the catalog builder."""

    base: str
    label: str
    component: DataComponent


# fmt: off
_TABLE_SPECS: list[_TableSpec] = [
    # DEMOGRAPHICS
    _TableSpec("DEMO",    "Demographics",                    DataComponent.DEMOGRAPHICS),

    # LABORATORY
    _TableSpec("GLU",     "Plasma Fasting Glucose",          DataComponent.LABORATORY),
    _TableSpec("GHB",     "Glycohemoglobin (HbA1c)",         DataComponent.LABORATORY),
    _TableSpec("CBC",     "Complete Blood Count",            DataComponent.LABORATORY),
    _TableSpec("BIOPRO",  "Standard Biochemistry Profile",   DataComponent.LABORATORY),
    _TableSpec("PBCD",    "Lead, Cadmium, Mercury, Se, Mn",  DataComponent.LABORATORY),
    _TableSpec("COT",     "Cotinine and Hydroxycotinine",    DataComponent.LABORATORY),
    _TableSpec("HDL",     "HDL Cholesterol",                 DataComponent.LABORATORY),
    _TableSpec("TCHOL",   "Total Cholesterol",               DataComponent.LABORATORY),
    _TableSpec("TRIGLY",  "Triglycerides",                   DataComponent.LABORATORY),
    _TableSpec("ALB_CR",  "Albumin and Creatinine - Urine",  DataComponent.LABORATORY),
    _TableSpec("HSCRP",   "High-Sensitivity C-Reactive Protein", DataComponent.LABORATORY),
    _TableSpec("FERTIN",  "Ferritin",                        DataComponent.LABORATORY),
    _TableSpec("FETIB",   "Iron Status - Serum",             DataComponent.LABORATORY),
    _TableSpec("THYROD",  "Thyroid Profile",                 DataComponent.LABORATORY),
    _TableSpec("VID",     "Vitamin D",                       DataComponent.LABORATORY),

    # EXAMINATION
    _TableSpec("BPX",     "Blood Pressure",                  DataComponent.EXAMINATION),
    _TableSpec("BMX",     "Body Measures",                   DataComponent.EXAMINATION),

    # QUESTIONNAIRE
    _TableSpec("SMQ",     "Smoking - Cigarette Use",         DataComponent.QUESTIONNAIRE),
    _TableSpec("ALQ",     "Alcohol Use",                     DataComponent.QUESTIONNAIRE),
    _TableSpec("PAQ",     "Physical Activity",               DataComponent.QUESTIONNAIRE),
    _TableSpec("DIQ",     "Diabetes",                        DataComponent.QUESTIONNAIRE),
    _TableSpec("MCQ",     "Medical Conditions",              DataComponent.QUESTIONNAIRE),
    _TableSpec("INQ",     "Income",                          DataComponent.QUESTIONNAIRE),
]
# fmt: on

# ---------------------------------------------------------------------------
# Cycle suffix mapping
# ---------------------------------------------------------------------------
_CYCLE_SUFFIX: dict[str, str] = {
    "2021-2023": "_L",
    "2017-2020": "_P",
    "2017-2018": "_J",
    "2015-2016": "_I",
    "2013-2014": "_H",
}

# ---------------------------------------------------------------------------
# Overrides: some tables use a different base name in certain cycles.
# Map (cycle, base) -> actual_base_name, or None to skip the table for
# that cycle entirely (e.g. Ferritin was not released in some cycles).
# ---------------------------------------------------------------------------
_NAME_OVERRIDES: dict[tuple[str, str], str | None] = {
    # Iron-status table was called FETIB in some cycles, not available in all
    ("2021-2023", "FETIB"): None,
    ("2017-2020", "FETIB"): None,
    # Thyroid not available in all cycles
    ("2021-2023", "THYROD"): None,
    ("2017-2020", "THYROD"): None,
    # Lead/Cadmium table naming varies
    ("2021-2023", "PBCD"): "PBCD",
    ("2017-2020", "PBCD"): "PBCD",
    ("2017-2018", "PBCD"): "PBCD",
    ("2015-2016", "PBCD"): "PBCD",
    ("2013-2014", "PBCD"): "PBCD",
    # Ferritin not in all cycles
    ("2013-2014", "FERTIN"): "FERTIN",
    # Vitamin D naming
    ("2013-2014", "VID"): "VID",
}

# ---------------------------------------------------------------------------
# Variable stubs -- key variables per table for search
# ---------------------------------------------------------------------------
# Each tuple is (var_name, label, var_type).
_TABLE_VARIABLES: dict[str, list[tuple[str, str, VariableType]]] = {
    "DEMO": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("RIAGENDR", "Gender", VariableType.BINARY),
        ("RIDAGEYR", "Age in years at screening", VariableType.CONTINUOUS),
        ("RIDRETH3", "Race/Hispanic origin with NH Asian", VariableType.CATEGORICAL),
        ("DMDEDUC2", "Education level - adults 20+", VariableType.ORDINAL),
        ("INDFMPIR", "Ratio of family income to poverty", VariableType.CONTINUOUS),
        ("SDMVSTRA", "Masked variance pseudo-stratum", VariableType.SURVEY_DESIGN),
        ("SDMVPSU", "Masked variance pseudo-PSU", VariableType.SURVEY_DESIGN),
        ("WTMECPRP", "Full sample MEC exam weight", VariableType.WEIGHT),
        ("WTINTPRP", "Full sample interview weight", VariableType.WEIGHT),
    ],
    "GLU": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXGLU", "Fasting glucose (mg/dL)", VariableType.CONTINUOUS),
        ("LBDGLUSI", "Fasting glucose (mmol/L)", VariableType.CONTINUOUS),
        ("WTSAFPRP", "Fasting subsample MEC weight", VariableType.WEIGHT),
    ],
    "GHB": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXGH", "Glycohemoglobin (%)", VariableType.CONTINUOUS),
    ],
    "CBC": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXWBCSI", "White blood cell count (1000 cells/uL)", VariableType.CONTINUOUS),
        ("LBXRBCSI", "Red blood cell count (million cells/uL)", VariableType.CONTINUOUS),
        ("LBXHGB", "Hemoglobin (g/dL)", VariableType.CONTINUOUS),
        ("LBXHCT", "Hematocrit (%)", VariableType.CONTINUOUS),
        ("LBXMCVSI", "Mean cell volume (fL)", VariableType.CONTINUOUS),
        ("LBXPLTSI", "Platelet count (1000 cells/uL)", VariableType.CONTINUOUS),
    ],
    "BIOPRO": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXSATSI", "Alanine aminotransferase ALT (U/L)", VariableType.CONTINUOUS),
        ("LBXSASSI", "Aspartate aminotransferase AST (U/L)", VariableType.CONTINUOUS),
        ("LBXSBU", "Blood urea nitrogen (mg/dL)", VariableType.CONTINUOUS),
        ("LBXSCR", "Creatinine, refrigerated serum (mg/dL)", VariableType.CONTINUOUS),
        ("LBXSGL", "Glucose, refrigerated serum (mg/dL)", VariableType.CONTINUOUS),
        ("LBXSTR", "Triglycerides, refrigerated (mg/dL)", VariableType.CONTINUOUS),
        ("LBXSUA", "Uric acid (mg/dL)", VariableType.CONTINUOUS),
        ("LBDLDL", "LDL-cholesterol, Friedewald (mg/dL)", VariableType.CONTINUOUS),
    ],
    "PBCD": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXBPB", "Blood lead (ug/dL)", VariableType.CONTINUOUS),
        ("LBXBCD", "Blood cadmium (ug/L)", VariableType.CONTINUOUS),
        ("LBXTHG", "Blood mercury, total (ug/L)", VariableType.CONTINUOUS),
        ("LBXBSE", "Blood selenium (ug/L)", VariableType.CONTINUOUS),
        ("LBXBMN", "Blood manganese (ug/L)", VariableType.CONTINUOUS),
    ],
    "COT": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXCOT", "Serum cotinine (ng/mL)", VariableType.CONTINUOUS),
        ("LBXHCOT", "Serum hydroxycotinine (ng/mL)", VariableType.CONTINUOUS),
    ],
    "HDL": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBDHDD", "Direct HDL-cholesterol (mg/dL)", VariableType.CONTINUOUS),
    ],
    "TCHOL": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXTC", "Total cholesterol (mg/dL)", VariableType.CONTINUOUS),
    ],
    "TRIGLY": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXTR", "Triglycerides, refrig serum (mg/dL)", VariableType.CONTINUOUS),
        ("LBDTRSI", "Triglycerides (mmol/L)", VariableType.CONTINUOUS),
    ],
    "ALB_CR": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("URXUMA", "Albumin, urine (ug/mL)", VariableType.CONTINUOUS),
        ("URXUCR", "Creatinine, urine (mg/dL)", VariableType.CONTINUOUS),
        ("URDACT", "Albumin creatinine ratio (mg/g)", VariableType.CONTINUOUS),
    ],
    "HSCRP": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXHSCRP", "HS C-Reactive Protein (mg/L)", VariableType.CONTINUOUS),
    ],
    "FERTIN": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXFER", "Ferritin (ng/mL)", VariableType.CONTINUOUS),
    ],
    "FETIB": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXIRN", "Iron, frozen serum (ug/dL)", VariableType.CONTINUOUS),
        ("LBXTIB", "TIBC, frozen serum (ug/dL)", VariableType.CONTINUOUS),
        ("LBDPCT", "Transferrin saturation (%)", VariableType.CONTINUOUS),
    ],
    "THYROD": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXTSH", "Thyroid stimulating hormone (mIU/L)", VariableType.CONTINUOUS),
        ("LBXT4F", "Free thyroxine (pmol/L)", VariableType.CONTINUOUS),
        ("LBXT3F", "Free triiodothyronine (pmol/L)", VariableType.CONTINUOUS),
    ],
    "VID": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("LBXVIDMS", "25OHD2+25OHD3 (nmol/L)", VariableType.CONTINUOUS),
        ("LBDVD2MS", "25OHD2 (nmol/L)", VariableType.CONTINUOUS),
        ("LBDVD3MS", "25OHD3 (nmol/L)", VariableType.CONTINUOUS),
    ],
    "BPX": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("BPXOSY1", "Oscillometric systolic BP 1st reading (mmHg)", VariableType.CONTINUOUS),
        ("BPXOSY2", "Oscillometric systolic BP 2nd reading (mmHg)", VariableType.CONTINUOUS),
        ("BPXOSY3", "Oscillometric systolic BP 3rd reading (mmHg)", VariableType.CONTINUOUS),
        ("BPXODI1", "Oscillometric diastolic BP 1st reading (mmHg)", VariableType.CONTINUOUS),
        ("BPXODI2", "Oscillometric diastolic BP 2nd reading (mmHg)", VariableType.CONTINUOUS),
        ("BPXODI3", "Oscillometric diastolic BP 3rd reading (mmHg)", VariableType.CONTINUOUS),
    ],
    "BMX": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("BMXWT", "Weight (kg)", VariableType.CONTINUOUS),
        ("BMXHT", "Standing height (cm)", VariableType.CONTINUOUS),
        ("BMXBMI", "Body Mass Index (kg/m**2)", VariableType.CONTINUOUS),
        ("BMXWAIST", "Waist circumference (cm)", VariableType.CONTINUOUS),
        ("BMXARMC", "Arm circumference (cm)", VariableType.CONTINUOUS),
    ],
    "SMQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("SMQ020", "Smoked at least 100 cigarettes in life", VariableType.BINARY),
        ("SMQ040", "Do you now smoke cigarettes?", VariableType.CATEGORICAL),
        ("SMD650", "Avg # cigarettes/day during past 30 days", VariableType.CONTINUOUS),
    ],
    "ALQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("ALQ111", "Ever had a drink of any kind of alcohol", VariableType.BINARY),
        ("ALQ121", "Past 12 mo how often drink alcoholic bev", VariableType.ORDINAL),
        ("ALQ130", "Avg # alcoholic drinks/day past 12 mos", VariableType.CONTINUOUS),
    ],
    "PAQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("PAQ605", "Vigorous work activity", VariableType.BINARY),
        ("PAQ620", "Moderate work activity", VariableType.BINARY),
        ("PAQ650", "Vigorous recreational activities", VariableType.BINARY),
        ("PAQ665", "Moderate recreational activities", VariableType.BINARY),
        ("PAD680", "Minutes sedentary activity", VariableType.CONTINUOUS),
    ],
    "DIQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("DIQ010", "Doctor told you have diabetes", VariableType.CATEGORICAL),
        ("DIQ050", "Taking insulin now", VariableType.BINARY),
        ("DIQ070", "Taking diabetic pills to lower blood sugar", VariableType.BINARY),
    ],
    "MCQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("MCQ160B", "Ever told had congestive heart failure", VariableType.BINARY),
        ("MCQ160C", "Ever told you had coronary heart disease", VariableType.BINARY),
        ("MCQ160D", "Ever told you had angina/angina pectoris", VariableType.BINARY),
        ("MCQ160E", "Ever told you had heart attack", VariableType.BINARY),
        ("MCQ160F", "Ever told you had a stroke", VariableType.BINARY),
        ("MCQ220", "Ever told you had cancer or malignancy", VariableType.BINARY),
    ],
    "INQ": [
        ("SEQN", "Respondent sequence number", VariableType.IDENTIFIER),
        ("INDFMMPC", "Family monthly poverty level category", VariableType.CATEGORICAL),
        ("INDFMMPI", "Family monthly poverty level index", VariableType.CONTINUOUS),
    ],
}


def _build_catalog() -> dict[str, list[NHANESTable]]:
    """Build the full catalog dict, mapping cycle strings to table lists."""
    catalog: dict[str, list[NHANESTable]] = {}

    for cycle, suffix in _CYCLE_SUFFIX.items():
        tables: list[NHANESTable] = []
        for spec in _TABLE_SPECS:
            # Check for name overrides / skip
            override_key = (cycle, spec.base)
            if override_key in _NAME_OVERRIDES:
                actual_base = _NAME_OVERRIDES[override_key]
                if actual_base is None:
                    # Table not available in this cycle
                    continue
            else:
                actual_base = spec.base

            table_name = f"{actual_base}{suffix}"
            url = _xpt_url(cycle, table_name)

            # Build variable stubs for this table
            variables: list[NHANESVariable] = []
            var_stubs = _TABLE_VARIABLES.get(spec.base, [])
            for var_name, var_label, var_type in var_stubs:
                variables.append(
                    NHANESVariable(
                        name=var_name,
                        label=var_label,
                        table=table_name,
                        var_type=var_type,
                    )
                )

            tables.append(
                NHANESTable(
                    name=table_name,
                    label=spec.label,
                    component=spec.component,
                    cycle=cycle,
                    xpt_url=url,
                    variables=variables,
                )
            )

        catalog[cycle] = tables

    return catalog


class NHANESCatalog:
    """Provides the full index of NHANES datasets for the TUI.

    The catalog is built once from hardcoded metadata -- no network calls.
    Use this class to browse cycles, look up table download URLs, and do
    quick substring searches across variable names and labels.

    Example::

        catalog = NHANESCatalog()
        for tbl in catalog.get_tables("2017-2018"):
            print(tbl.name, tbl.label)

        hits = catalog.search_variables("cholesterol")
    """

    def __init__(self) -> None:
        self._catalog = _build_catalog()
        logger.debug(
            "NHANESCatalog initialized with %d cycles, %d total tables",
            len(self._catalog),
            sum(len(v) for v in self._catalog.values()),
        )

    # -- Cycle-level queries ------------------------------------------------

    def get_cycles(self) -> list[str]:
        """Return a sorted list of available cycle identifiers.

        Most recent cycle first.
        """
        return sorted(self._catalog.keys(), reverse=True)

    # -- Table-level queries ------------------------------------------------

    def get_tables(self, cycle: str) -> list[NHANESTable]:
        """Return all tables for a given cycle.

        Args:
            cycle: A cycle identifier such as ``"2017-2018"``.

        Returns:
            List of ``NHANESTable`` instances.  Empty list if the cycle
            is not recognised.
        """
        return list(self._catalog.get(cycle, []))

    def get_table(self, cycle: str, table_name: str) -> NHANESTable | None:
        """Look up a single table by cycle and name.

        Args:
            cycle: Cycle identifier.
            table_name: The full CDC table name (e.g. ``"DEMO_J"``).

        Returns:
            The matching ``NHANESTable``, or ``None`` if not found.
        """
        for tbl in self._catalog.get(cycle, []):
            if tbl.name == table_name:
                return tbl
        return None

    def get_xpt_url(self, cycle: str, table_name: str) -> str:
        """Return the CDC XPT download URL for a table.

        Args:
            cycle: Cycle identifier.
            table_name: Full table name.

        Returns:
            The HTTPS download URL.

        Raises:
            KeyError: If the cycle/table combination is not in the catalog.
        """
        tbl = self.get_table(cycle, table_name)
        if tbl is None:
            raise KeyError(f"Table {table_name!r} not found in cycle {cycle!r}")
        return tbl.xpt_url

    def get_all_tables(self) -> list[NHANESTable]:
        """Return every table across all cycles.

        Useful for global searches or building a flat list in the TUI.
        """
        result: list[NHANESTable] = []
        for cycle in self.get_cycles():
            result.extend(self._catalog[cycle])
        return result

    # -- Variable-level search ----------------------------------------------

    def search_variables(self, query: str) -> list[NHANESVariable]:
        """Search variable names and labels across all tables/cycles.

        A case-insensitive substring match is used.  Results are returned
        in cycle-descending order (most recent first).

        Args:
            query: Substring to search for (e.g. ``"glucose"`` or
                ``"LBXGH"``).

        Returns:
            List of matching ``NHANESVariable`` instances.
        """
        query_lower = query.lower()
        hits: list[NHANESVariable] = []
        for cycle in self.get_cycles():
            for tbl in self._catalog[cycle]:
                for var in tbl.variables:
                    if (
                        query_lower in var.name.lower()
                        or query_lower in var.label.lower()
                    ):
                        hits.append(var)
        return hits

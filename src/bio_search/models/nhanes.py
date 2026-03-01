"""Pydantic models for NHANES metadata.

These models mirror the structure of the CDC NHANES data catalogue:

    Cycle  -->  Table  -->  Variable

A *cycle* is a multi-year survey wave (e.g. "2017-2018").  Each cycle
contains many *tables* grouped by component (Demographics, Laboratory,
etc.).  Each table contains *variables* with a short name, human label,
and type classification.

The type system (``VariableType``) lets downstream code decide how to
treat each column -- e.g. continuous variables get linear regression,
binary variables get logistic regression, survey-design columns are
never used as exposures/outcomes, and so on.
"""

from enum import Enum

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DataComponent(str, Enum):
    """Top-level grouping of NHANES tables on the CDC website."""

    DEMOGRAPHICS = "demographics"
    DIETARY = "dietary"
    EXAMINATION = "examination"
    LABORATORY = "laboratory"
    QUESTIONNAIRE = "questionnaire"


class VariableType(str, Enum):
    """Semantic type for an NHANES variable.

    The classifier in ``data/`` assigns one of these types to every
    column so the analysis engine can pick the right statistical model.
    """

    CONTINUOUS = "continuous"
    BINARY = "binary"
    CATEGORICAL = "categorical"
    ORDINAL = "ordinal"
    IDENTIFIER = "identifier"
    WEIGHT = "weight"
    SURVEY_DESIGN = "survey_design"


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

class NHANESVariable(BaseModel):
    """A single column inside an NHANES SAS-transport (XPT) file.

    Attributes:
        name: Short SAS variable name (e.g. ``LBXGLU``).
        label: Human-readable description from the codebook.
        table: Name of the parent table (e.g. ``GLU_L``).
        var_type: Semantic type used to choose the regression model.
        n_values: Number of distinct non-missing values observed.
            Populated after the data is loaded; ``None`` before that.
        value_labels: Mapping from coded numeric values to their text
            labels (e.g. ``{1: "Male", 2: "Female"}``).  ``None`` when
            the variable has no coded values.
    """

    name: str
    label: str
    table: str
    var_type: VariableType
    n_values: int | None = None
    value_labels: dict[int | float, str] | None = None


class NHANESTable(BaseModel):
    """One data table (XPT file) in a specific NHANES cycle.

    Attributes:
        name: Table short name (e.g. ``DEMO_L``).
        label: Human-readable table title.
        component: Which section of the NHANES website the table
            belongs to.
        cycle: Cycle identifier string (e.g. ``"2021-2023"``).
        xpt_url: Full URL to the SAS-transport file on the CDC server.
        variables: Column metadata.  Empty until the table is loaded or
            the codebook is parsed.
    """

    name: str
    label: str
    component: DataComponent
    cycle: str
    xpt_url: str
    variables: list[NHANESVariable] = []


class NHANESCycle(BaseModel):
    """A multi-year NHANES survey wave.

    Attributes:
        cycle_id: Canonical identifier (e.g. ``"2017-2018"``).
        years: Start and end calendar years as a two-element tuple.
        tables: All data tables published for this cycle.  Populated
            lazily by the catalogue scraper.
    """

    cycle_id: str
    years: tuple[int, int]
    tables: list[NHANESTable] = []

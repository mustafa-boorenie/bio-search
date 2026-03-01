"""XPT file loader and variable-type classifier.

This module reads SAS transport (XPT) files into pandas DataFrames and
automatically classifies each column into a ``VariableType`` category
(CONTINUOUS, CATEGORICAL, BINARY, WEIGHT, IDENTIFIER, SURVEY_DESIGN).

The classifier uses simple heuristics that work well for NHANES data:

- Known survey-design columns (SDMVSTRA, SDMVPSU, SEQN) are tagged
  explicitly.
- Columns whose name starts with ``WT`` are sample weights.
- Columns with only two unique non-null values are binary.
- Columns with 10 or fewer unique non-null values are categorical.
- Everything else is continuous.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from bio_search.models.nhanes import VariableType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known special variables
# ---------------------------------------------------------------------------
_IDENTIFIER_VARS: set[str] = {"SEQN"}
_SURVEY_DESIGN_VARS: set[str] = {"SDMVSTRA", "SDMVPSU"}

# All NHANES survey variables that should be tagged automatically.
SURVEY_VARS: set[str] = _IDENTIFIER_VARS | _SURVEY_DESIGN_VARS

# Maximum number of unique non-null values for a column to be
# classified as CATEGORICAL (rather than CONTINUOUS).
_CATEGORICAL_THRESHOLD = 10


class LoadError(Exception):
    """Raised when an XPT file cannot be read."""


class DataLoader:
    """Loads NHANES XPT files and classifies variable types.

    Example::

        loader = DataLoader()
        df = loader.load_xpt(Path("data/raw/2017-2018/DEMO_J.XPT"))
        df, types = loader.load_and_classify(
            Path("data/raw/2017-2018/DEMO_J.XPT")
        )
        print(types)
        # {'SEQN': VariableType.IDENTIFIER,
        #  'SDMVSTRA': VariableType.SURVEY_DESIGN, ...}
    """

    # -- Public API ---------------------------------------------------------

    @staticmethod
    def load_xpt(path: Path) -> pd.DataFrame:
        """Read a SAS XPT file into a pandas DataFrame.

        Args:
            path: Path to the ``.XPT`` file.

        Returns:
            A ``pd.DataFrame`` with all columns from the file.

        Raises:
            LoadError: If the file does not exist or cannot be parsed.
        """
        if not path.exists():
            raise LoadError(f"File not found: {path}")

        try:
            df = pd.read_sas(path, format="xport", encoding="utf-8")
        except Exception as exc:
            raise LoadError(f"Failed to read XPT file {path}: {exc}") from exc

        logger.info(
            "Loaded %s: %d rows x %d columns",
            path.name,
            len(df),
            len(df.columns),
        )
        return df

    @staticmethod
    def classify_variable(series: pd.Series) -> VariableType:
        """Classify a single pandas Series into a VariableType.

        The logic is intentionally simple and tuned for NHANES:

        1. If the column name is ``SEQN`` -> IDENTIFIER.
        2. If the column name is ``SDMVSTRA`` or ``SDMVPSU`` ->
           SURVEY_DESIGN.
        3. If the column name starts with ``WT`` -> WEIGHT.
        4. If there are exactly 2 unique non-null values (like
           ``{0, 1}`` or ``{1, 2}``) -> BINARY.
        5. If there are 10 or fewer unique non-null values ->
           CATEGORICAL.
        6. Otherwise -> CONTINUOUS.

        Args:
            series: A DataFrame column.

        Returns:
            The inferred ``VariableType``.
        """
        name = series.name if isinstance(series.name, str) else str(series.name)

        # 1. Identifier
        if name in _IDENTIFIER_VARS:
            return VariableType.IDENTIFIER

        # 2. Survey design
        if name in _SURVEY_DESIGN_VARS:
            return VariableType.SURVEY_DESIGN

        # 3. Weights
        if name.startswith("WT"):
            return VariableType.WEIGHT

        # 4 + 5. Count unique non-null values
        nunique = series.dropna().nunique()

        if nunique <= 2:
            return VariableType.BINARY

        if nunique <= _CATEGORICAL_THRESHOLD:
            return VariableType.CATEGORICAL

        # 6. Default
        return VariableType.CONTINUOUS

    def load_and_classify(
        self, path: Path
    ) -> tuple[pd.DataFrame, dict[str, VariableType]]:
        """Load an XPT file and classify every column.

        This is a convenience wrapper that calls ``load_xpt`` followed
        by ``classify_variable`` for each column.

        Args:
            path: Path to the ``.XPT`` file.

        Returns:
            A tuple of ``(dataframe, type_map)`` where ``type_map``
            maps column names to their ``VariableType``.
        """
        df = self.load_xpt(path)
        type_map: dict[str, VariableType] = {}
        for col in df.columns:
            type_map[col] = self.classify_variable(df[col])

        logger.debug(
            "Classified %d variables in %s: %s",
            len(type_map),
            path.name,
            {vt.value: sum(1 for v in type_map.values() if v == vt) for vt in VariableType},
        )
        return df, type_map

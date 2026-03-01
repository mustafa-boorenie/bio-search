"""Variable harmonisation across NHANES cycles.

NHANES occasionally renames variables between release cycles.  For
example, C-reactive protein was ``LBXCRP`` in older cycles and became
``LBXHSCRP`` when the assay switched to a high-sensitivity method.
This module provides a mapping from *canonical* variable names to the
cycle-specific names actually used in the XPT files, and a transformer
that renames DataFrame columns accordingly.

The harmonisation map covers the variables most commonly used in
epidemiological research (metabolic biomarkers, metals, lipids, liver
enzymes, kidney function, inflammation markers).

Typical usage::

    harmonizer = VariableHarmonizer()
    df = harmonizer.harmonize(df, cycle="2013-2014")
    # Columns are now renamed to canonical names
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Harmonisation map
#
# Structure:  canonical_name -> { cycle: actual_column_name }
#
# If a canonical name is not listed for a specific cycle, it means the
# variable name did not change (i.e. the canonical name == actual name).
# Only cycles where the name differs are included.
# ---------------------------------------------------------------------------
HARMONIZATION_MAP: dict[str, dict[str, str]] = {
    # ---- Glucose / diabetes -----------------------------------------------
    "LBXGLU": {
        # Fasting glucose -- name is stable across most cycles
        "2021-2023": "LBXGLU",
        "2017-2020": "LBXGLU",
        "2017-2018": "LBXGLU",
        "2015-2016": "LBXGLU",
        "2013-2014": "LBXGLU",
    },
    "LBXGH": {
        # HbA1c (glycohemoglobin) -- stable
        "2021-2023": "LBXGH",
        "2017-2020": "LBXGH",
        "2017-2018": "LBXGH",
        "2015-2016": "LBXGH",
        "2013-2014": "LBXGH",
    },

    # ---- Metals -----------------------------------------------------------
    "LBXBPB": {
        # Blood lead -- stable across listed cycles
        "2021-2023": "LBXBPB",
        "2017-2020": "LBXBPB",
        "2017-2018": "LBXBPB",
        "2015-2016": "LBXBPB",
        "2013-2014": "LBXBPB",
    },
    "LBXBCD": {
        # Blood cadmium
        "2021-2023": "LBXBCD",
        "2017-2020": "LBXBCD",
        "2017-2018": "LBXBCD",
        "2015-2016": "LBXBCD",
        "2013-2014": "LBXBCD",
    },

    # ---- Tobacco biomarker ------------------------------------------------
    "LBXCOT": {
        # Cotinine
        "2021-2023": "LBXCOT",
        "2017-2020": "LBXCOT",
        "2017-2018": "LBXCOT",
        "2015-2016": "LBXCOT",
        "2013-2014": "LBXCOT",
    },

    # ---- Lipids -----------------------------------------------------------
    "LBXTC": {
        # Total cholesterol
        "2021-2023": "LBXTC",
        "2017-2020": "LBXTC",
        "2017-2018": "LBXTC",
        "2015-2016": "LBXTC",
        "2013-2014": "LBXTC",
    },
    "LBXTR": {
        # Triglycerides
        "2021-2023": "LBXTR",
        "2017-2020": "LBXTR",
        "2017-2018": "LBXTR",
        "2015-2016": "LBXTR",
        "2013-2014": "LBXTR",
    },
    "LBDHDD": {
        # HDL cholesterol -- direct
        "2021-2023": "LBDHDD",
        "2017-2020": "LBDHDD",
        "2017-2018": "LBDHDD",
        "2015-2016": "LBDHDD",
        "2013-2014": "LBDHDD",
    },
    "LBDLDL": {
        # LDL cholesterol (Friedewald equation) -- in BIOPRO/TRIGLY
        "2021-2023": "LBDLDL",
        "2017-2020": "LBDLDL",
        "2017-2018": "LBDLDL",
        "2015-2016": "LBDLDL",
        "2013-2014": "LBDLDL",
    },

    # ---- Kidney function --------------------------------------------------
    "LBXSCR": {
        # Serum creatinine
        "2021-2023": "LBXSCR",
        "2017-2020": "LBXSCR",
        "2017-2018": "LBXSCR",
        "2015-2016": "LBXSCR",
        "2013-2014": "LBXSCR",
    },
    "URXUMA": {
        # Urine albumin
        "2021-2023": "URXUMA",
        "2017-2020": "URXUMA",
        "2017-2018": "URXUMA",
        "2015-2016": "URXUMA",
        "2013-2014": "URXUMA",
    },

    # ---- Liver enzymes ----------------------------------------------------
    "LBXSATSI": {
        # ALT (alanine aminotransferase)
        "2021-2023": "LBXSATSI",
        "2017-2020": "LBXSATSI",
        "2017-2018": "LBXSATSI",
        "2015-2016": "LBXSATSI",
        "2013-2014": "LBXSATSI",
    },
    "LBXSASSI": {
        # AST (aspartate aminotransferase)
        "2021-2023": "LBXSASSI",
        "2017-2020": "LBXSASSI",
        "2017-2018": "LBXSASSI",
        "2015-2016": "LBXSASSI",
        "2013-2014": "LBXSASSI",
    },

    # ---- Inflammation -----------------------------------------------------
    "LBXHSCRP": {
        # C-reactive protein -- the key variable that actually changed names.
        # Older cycles used LBXCRP; newer ones use LBXHSCRP.
        "2021-2023": "LBXHSCRP",
        "2017-2020": "LBXHSCRP",
        "2017-2018": "LBXHSCRP",
        "2015-2016": "LBXHSCRP",
        "2013-2014": "LBXCRP",
    },
}

# Reverse lookup: for each cycle, map actual_name -> canonical_name
_REVERSE_MAP: dict[str, dict[str, str]] = {}
for canonical, cycle_map in HARMONIZATION_MAP.items():
    for cycle, actual in cycle_map.items():
        _REVERSE_MAP.setdefault(cycle, {})[actual] = canonical


class VariableHarmonizer:
    """Renames NHANES DataFrame columns to canonical variable names.

    The harmoniser is stateless -- all mapping information lives in the
    module-level ``HARMONIZATION_MAP`` dict.  You can instantiate it
    freely or use the class methods directly.

    Example::

        harmonizer = VariableHarmonizer()

        # Rename cycle-specific columns to canonical names
        df = harmonizer.harmonize(df, cycle="2013-2014")

        # Look up the canonical name for a variable
        canonical = harmonizer.get_canonical_name("LBXCRP", "2013-2014")
        # -> "LBXHSCRP"
    """

    def harmonize(self, df: pd.DataFrame, cycle: str) -> pd.DataFrame:
        """Rename columns in *df* from cycle-specific names to canonical.

        Only columns that appear in the harmonisation map and actually
        differ from the canonical name are renamed.  Columns not in the
        map are left untouched.

        Args:
            df: The raw DataFrame loaded from an XPT file.
            cycle: The NHANES cycle identifier (e.g. ``"2013-2014"``).

        Returns:
            A new DataFrame with harmonised column names.
        """
        rename_map: dict[str, str] = {}

        for canonical, cycle_map in HARMONIZATION_MAP.items():
            actual = cycle_map.get(cycle)
            if actual is None:
                continue
            # Only rename if the actual name differs from canonical
            # AND the actual name is present in the DataFrame.
            if actual != canonical and actual in df.columns:
                rename_map[actual] = canonical

        if rename_map:
            logger.info(
                "Harmonising %d variables for cycle %s: %s",
                len(rename_map),
                cycle,
                rename_map,
            )
            df = df.rename(columns=rename_map)
        else:
            logger.debug("No harmonisation needed for cycle %s", cycle)

        return df

    def get_canonical_name(self, var_name: str, cycle: str) -> str:
        """Return the canonical name for a variable in a given cycle.

        If the variable is not in the harmonisation map, returns the
        original name unchanged.

        Args:
            var_name: The column name as it appears in the XPT file.
            cycle: The NHANES cycle.

        Returns:
            The canonical variable name.
        """
        reverse = _REVERSE_MAP.get(cycle, {})
        return reverse.get(var_name, var_name)

    def get_actual_name(self, canonical_name: str, cycle: str) -> str:
        """Return the cycle-specific column name for a canonical variable.

        This is the inverse of ``get_canonical_name``.  If the canonical
        name is not in the map, returns it unchanged.

        Args:
            canonical_name: The canonical variable name.
            cycle: The NHANES cycle.

        Returns:
            The actual column name used in that cycle's XPT files.
        """
        cycle_map = HARMONIZATION_MAP.get(canonical_name, {})
        return cycle_map.get(cycle, canonical_name)

    def list_harmonized_variables(self) -> list[str]:
        """Return all canonical variable names in the harmonisation map."""
        return sorted(HARMONIZATION_MAP.keys())

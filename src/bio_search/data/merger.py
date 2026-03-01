"""NHANES table merging and cross-cycle stacking.

NHANES distributes data across dozens of separate XPT files per cycle.
To build a single analytic dataset a researcher must:

1. **Merge** tables within the same cycle on the respondent ID (``SEQN``).
2. **Stack** merged datasets from multiple cycles and adjust sample
   weights so that the combined dataset represents the correct
   population.

This module provides ``DataMerger`` which handles both operations with
proper weight adjustment.

Weight adjustment rule (per CDC guidance):
    When combining *N* cycles, divide every weight column (those whose
    name starts with ``WT``) by *N*.  This ensures the combined dataset
    represents the average annual population rather than inflating the
    total.

Typical usage::

    merger = DataMerger()

    # Merge tables within one cycle
    combined = merger.merge_tables([demo_df, lab_df, bp_df])

    # Stack two cycles with weight adjustment
    pooled = merger.stack_cycles([cycle1_df, cycle2_df], n_cycles=2)
"""

from __future__ import annotations

import logging

import pandas as pd

logger = logging.getLogger(__name__)


class MergeError(Exception):
    """Raised when a merge or stack operation fails."""


class DataMerger:
    """Merges and stacks NHANES DataFrames.

    All operations return new DataFrames; inputs are never modified.
    """

    @staticmethod
    def merge_tables(
        dfs: list[pd.DataFrame],
        on: str = "SEQN",
    ) -> pd.DataFrame:
        """Inner-join multiple DataFrames on a shared key column.

        This is the standard way to combine NHANES tables from the same
        cycle (e.g. demographics + laboratory + examination).  An inner
        join is used so that only respondents present in *all* tables
        are kept; this avoids surprises from partial data.

        Args:
            dfs: List of DataFrames to merge.  Each must contain the
                ``on`` column.
            on: The column to join on.  Defaults to ``"SEQN"`` (the
                NHANES respondent sequence number).

        Returns:
            A single merged DataFrame.

        Raises:
            MergeError: If the input list is empty or a DataFrame is
                missing the join column.
        """
        if not dfs:
            raise MergeError("Cannot merge an empty list of DataFrames")

        # Validate that every DataFrame has the join column
        for i, df in enumerate(dfs):
            if on not in df.columns:
                raise MergeError(
                    f"DataFrame at index {i} is missing the join column {on!r}. "
                    f"Available columns: {list(df.columns[:10])}..."
                )

        result = dfs[0].copy()
        for i, df in enumerate(dfs[1:], start=1):
            pre_rows = len(result)
            result = result.merge(df, on=on, how="inner", suffixes=("", f"_dup{i}"))
            logger.debug(
                "Merged table %d: %d rows -> %d rows (%d dropped)",
                i,
                pre_rows,
                len(result),
                pre_rows - len(result),
            )

        # Warn about duplicate columns created by overlapping names
        dup_cols = [c for c in result.columns if "_dup" in c]
        if dup_cols:
            logger.warning(
                "Duplicate columns created during merge (will be dropped): %s",
                dup_cols,
            )
            result = result.drop(columns=dup_cols)

        logger.info(
            "Merged %d tables on %s: %d rows x %d columns",
            len(dfs),
            on,
            len(result),
            len(result.columns),
        )
        return result

    @staticmethod
    def stack_cycles(
        cycle_dfs: list[pd.DataFrame],
        n_cycles: int,
    ) -> pd.DataFrame:
        """Concatenate DataFrames from multiple NHANES cycles.

        After concatenation, all sample-weight columns (those whose
        name starts with ``WT``) are divided by ``n_cycles`` per CDC
        guidance for combining survey cycles.

        Args:
            cycle_dfs: List of DataFrames, one per cycle.  They should
                already be harmonised (see ``VariableHarmonizer``) so
                that column names match across cycles.
            n_cycles: Number of cycles being combined.  This is the
                divisor for weight adjustment.  Must be >= 1.

        Returns:
            A single stacked DataFrame with adjusted weights.

        Raises:
            MergeError: If the input list is empty or ``n_cycles < 1``.
        """
        if not cycle_dfs:
            raise MergeError("Cannot stack an empty list of DataFrames")
        if n_cycles < 1:
            raise MergeError(f"n_cycles must be >= 1, got {n_cycles}")

        result = pd.concat(cycle_dfs, ignore_index=True)

        # Identify weight columns
        weight_cols = [c for c in result.columns if c.startswith("WT")]

        if weight_cols and n_cycles > 1:
            logger.info(
                "Adjusting %d weight columns by 1/%d: %s",
                len(weight_cols),
                n_cycles,
                weight_cols,
            )
            for col in weight_cols:
                result[col] = result[col] / n_cycles

        logger.info(
            "Stacked %d cycle DataFrames: %d total rows, %d columns, "
            "%d weight columns adjusted",
            len(cycle_dfs),
            len(result),
            len(result.columns),
            len(weight_cols) if n_cycles > 1 else 0,
        )
        return result

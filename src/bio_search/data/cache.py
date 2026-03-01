"""DuckDB-backed persistent DataFrame cache.

Caches downloaded and processed NHANES tables in a local DuckDB
database so that subsequent runs can skip the download-and-parse step.
DuckDB is columnar and compressed, so the on-disk footprint is much
smaller than the original XPT files while offering fast analytical
reads.

Usage::

    cache = DataCache(Path("data/cache.duckdb"))
    cache.store("DEMO_J", df)

    if cache.has("DEMO_J"):
        df = cache.load("DEMO_J")
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class CacheError(Exception):
    """Raised when a cache operation fails."""


class DataCache:
    """DuckDB-based persistent cache for NHANES DataFrames.

    Each table is stored as a DuckDB table whose name is the sanitised
    version of the NHANES table name (upper-case, alphanumeric + underscores).

    Args:
        db_path: Path to the DuckDB database file.  Created automatically
            if it does not exist.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Verify the connection works on init.
        try:
            con = duckdb.connect(str(db_path))
            con.close()
        except Exception as exc:
            raise CacheError(f"Cannot open DuckDB at {db_path}: {exc}") from exc
        logger.debug("DataCache initialised at %s", db_path)

    # -- helpers ------------------------------------------------------------

    def _connect(self) -> duckdb.DuckDBPyConnection:
        """Return a fresh connection to the cache database."""
        return duckdb.connect(str(self._db_path))

    @staticmethod
    def _sanitise(table_name: str) -> str:
        """Make a table name safe for use as a DuckDB identifier.

        Replaces hyphens and spaces with underscores, uppercases, and
        prefixes with ``t_`` to avoid collisions with SQL keywords.
        """
        safe = table_name.upper().replace("-", "_").replace(" ", "_")
        # DuckDB identifiers must start with a letter or underscore
        if safe and not (safe[0].isalpha() or safe[0] == "_"):
            safe = f"t_{safe}"
        return safe

    # -- public API ---------------------------------------------------------

    def store(self, table_name: str, df: pd.DataFrame) -> None:
        """Store a DataFrame in the cache, replacing any previous version.

        Args:
            table_name: Logical name (e.g. ``"DEMO_J"``).
            df: The DataFrame to persist.
        """
        safe_name = self._sanitise(table_name)
        con = self._connect()
        try:
            # Register the DataFrame so DuckDB can reference it as a table
            con.register("__incoming", df)
            con.execute(f"DROP TABLE IF EXISTS {safe_name}")
            con.execute(f"CREATE TABLE {safe_name} AS SELECT * FROM __incoming")
            con.unregister("__incoming")
            logger.info(
                "Cached %s (%d rows, %d cols) as %s",
                table_name,
                len(df),
                len(df.columns),
                safe_name,
            )
        except Exception as exc:
            raise CacheError(f"Failed to store {table_name}: {exc}") from exc
        finally:
            con.close()

    def load(self, table_name: str) -> pd.DataFrame | None:
        """Load a previously cached DataFrame.

        Args:
            table_name: Logical name.

        Returns:
            The DataFrame, or ``None`` if the table is not cached.
        """
        safe_name = self._sanitise(table_name)
        con = self._connect()
        try:
            if not self._table_exists(con, safe_name):
                return None
            df = con.execute(f"SELECT * FROM {safe_name}").fetchdf()
            logger.debug("Cache hit: %s (%d rows)", table_name, len(df))
            return df
        except Exception as exc:
            logger.warning("Cache load failed for %s: %s", table_name, exc)
            return None
        finally:
            con.close()

    def has(self, table_name: str) -> bool:
        """Check whether a table is present in the cache."""
        safe_name = self._sanitise(table_name)
        con = self._connect()
        try:
            return self._table_exists(con, safe_name)
        finally:
            con.close()

    def clear(self, table_name: str | None = None) -> None:
        """Remove cached data.

        Args:
            table_name: If given, clear only this table.  If ``None``,
                drop every cached table.
        """
        con = self._connect()
        try:
            if table_name is not None:
                safe_name = self._sanitise(table_name)
                con.execute(f"DROP TABLE IF EXISTS {safe_name}")
                logger.info("Cleared cache for %s", table_name)
            else:
                for name in self._all_table_names(con):
                    con.execute(f"DROP TABLE IF EXISTS {name}")
                logger.info("Cleared entire cache")
        finally:
            con.close()

    def list_tables(self) -> list[str]:
        """Return the names of all cached tables.

        Returns the *sanitised* DuckDB table names.  These correspond
        1-to-1 with the logical names passed to ``store()``.
        """
        con = self._connect()
        try:
            return self._all_table_names(con)
        finally:
            con.close()

    # -- internal -----------------------------------------------------------

    @staticmethod
    def _table_exists(con: duckdb.DuckDBPyConnection, safe_name: str) -> bool:
        """Check whether a table exists in the connected database."""
        result = con.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name = ?",
            [safe_name],
        ).fetchone()
        return result is not None and result[0] > 0

    @staticmethod
    def _all_table_names(con: duckdb.DuckDBPyConnection) -> list[str]:
        """Return all user table names in the connected database."""
        rows = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main'"
        ).fetchall()
        return [row[0] for row in rows]

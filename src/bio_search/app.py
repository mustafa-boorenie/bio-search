"""Bio-Search Textual application.

This is the top-level ``App`` subclass that wires together the NHANES
catalog, downloader, data loader, cache, merger, harmoniser, and
analysis engine.  It exposes high-level async methods that the
``MainScreen`` calls in response to user commands.

Usage::

    from bio_search.app import BioSearchApp

    app = BioSearchApp()
    app.run()
"""

from __future__ import annotations

import asyncio
import logging

import pandas as pd
from textual.app import App

from bio_search.config import Settings
from bio_search.data.cache import DataCache
from bio_search.data.catalog import NHANESCatalog
from bio_search.data.downloader import NHANESDownloader
from bio_search.data.harmonizer import VariableHarmonizer
from bio_search.data.loader import DataLoader
from bio_search.models.analysis import EWASResult, GuidedAnalysisResult
from bio_search.models.nhanes import DataComponent
from bio_search.survey.design import SurveyDesign
from bio_search.survey.weights import WeightSelector
from bio_search.tui.screens.main import MainScreen

logger = logging.getLogger(__name__)


class BioSearchApp(App):
    """NHANES Biomedical Association Mining TUI.

    The app owns all the shared infrastructure (catalog, downloader,
    cache, analysis engine) and exposes async helpers that the screen
    layer invokes.

    Attributes
    ----------
    settings:
        Global configuration loaded from environment / ``.env``.
    catalog:
        Hardcoded NHANES data index (no network calls).
    downloader:
        Async CDC XPT file fetcher with retry and caching.
    loader:
        XPT-to-DataFrame loader with variable-type classification.
    cache:
        DuckDB-backed persistent DataFrame cache.
    harmonizer:
        Renames cycle-specific variable names to canonical forms.
    """

    TITLE = "Bio-Search: NHANES Association Mining"
    CSS_PATH = "tui/styles/app.tcss"

    def __init__(self) -> None:
        super().__init__()

        # -- Configuration -------------------------------------------------
        self.settings = Settings()

        # -- Data layer ----------------------------------------------------
        self.catalog = NHANESCatalog()
        self.downloader = NHANESDownloader(
            max_concurrent=self.settings.max_download_workers,
        )
        self.loader = DataLoader()
        self.harmonizer = VariableHarmonizer()

        # -- Cache ---------------------------------------------------------
        cache_path = self.settings.data_dir / "processed" / "cache.duckdb"
        self.cache = DataCache(cache_path)

        # -- Analysis engine (lazy import to avoid hard dep) ---------------
        self._engine = None

        # -- Working data --------------------------------------------------
        self._loaded_data: pd.DataFrame | None = None

        # -- Latest analysis results (for export) -------------------------
        self._latest_ewas_result: EWASResult | None = None
        self._latest_guided_result: GuidedAnalysisResult | None = None

    # -- Lifecycle ---------------------------------------------------------

    def on_mount(self) -> None:
        """Push the main screen when the app starts."""
        self.push_screen(MainScreen())

    # -- Engine accessor (lazy init) ---------------------------------------

    def _get_engine(self):
        """Lazily import and construct the analysis engine.

        This avoids an import-time crash if the analysis module has
        unresolved dependencies during early development.
        """
        if self._engine is None:
            try:
                from bio_search.analysis.engine import AnalysisEngine

                self._engine = AnalysisEngine(self.settings)
            except ImportError:
                logger.warning(
                    "AnalysisEngine is not available yet -- "
                    "analysis commands will fail."
                )
                raise
        return self._engine

    # -- Data operations ---------------------------------------------------

    async def download_table(
        self, cycle: str, table_name: str
    ) -> pd.DataFrame | None:
        """Download, load, harmonise, and cache a single NHANES table.

        Parameters
        ----------
        cycle:
            NHANES cycle identifier (e.g. ``"2017-2018"``).
        table_name:
            Full CDC table name (e.g. ``"DEMO_J"``).

        Returns
        -------
        pd.DataFrame or None
            The loaded DataFrame, or ``None`` if the table is not in
            the catalog.
        """
        table = self.catalog.get_table(cycle, table_name)
        if table is None:
            return None

        path = await self.downloader.download_table(table, self.settings.data_dir)

        df = self.loader.load_xpt(path)
        df = self.harmonizer.harmonize(df, cycle)

        cache_key = f"{cycle}_{table_name}"
        self.cache.store(cache_key, df)

        logger.info(
            "Downloaded and cached %s/%s: %d rows x %d cols",
            cycle,
            table_name,
            len(df),
            len(df.columns),
        )
        return df

    # -- Analysis operations -----------------------------------------------

    async def run_ewas(
        self,
        outcome: str,
        progress_callback=None,
    ) -> EWASResult | None:
        """Run an environment-wide association study.

        This method executes the EWAS in a background thread so the
        TUI remains responsive.

        Parameters
        ----------
        outcome:
            The outcome variable name (e.g. ``"LBXGLU"``).
        progress_callback:
            Optional ``(current, total, var_name) -> None`` callable
            invoked after each variable is tested.

        Returns
        -------
        EWASResult or None
            The full EWAS results, or ``None`` if no data is loaded.
        """
        if self._loaded_data is None:
            return None

        engine = self._get_engine()

        design = SurveyDesign(
            weight_col=WeightSelector.select_weight(
                {DataComponent.LABORATORY}
            ),
        )
        prepared = design.prepare(self._loaded_data)

        def _run() -> EWASResult:
            return engine.run_ewas(
                prepared,
                outcome,
                design,
                progress_callback=progress_callback,
            )

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run)
        self._latest_ewas_result = result
        return result

    async def run_guided(
        self,
        exposure: str,
        outcome: str,
    ) -> GuidedAnalysisResult | None:
        """Run a guided deep-dive analysis for one exposure-outcome pair.

        Parameters
        ----------
        exposure:
            The exposure variable name.
        outcome:
            The outcome variable name.

        Returns
        -------
        GuidedAnalysisResult or None
            The guided analysis results, or ``None`` if no data is
            loaded.
        """
        if self._loaded_data is None:
            return None

        engine = self._get_engine()
        design = SurveyDesign()
        prepared = design.prepare(self._loaded_data)

        def _run() -> GuidedAnalysisResult:
            return engine.run_guided(prepared, outcome, exposure, design)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _run)
        self._latest_guided_result = result
        return result

    # -- Data management ---------------------------------------------------

    def load_cached_data(self, table_keys: list[str]) -> None:
        """Load and merge previously cached tables into the working dataset.

        Parameters
        ----------
        table_keys:
            Cache keys in the format ``"<cycle>_<table_name>"``
            (e.g. ``["2017-2018_DEMO_J", "2017-2018_GLU_J"]``).
        """
        dfs: list[pd.DataFrame] = []
        for key in table_keys:
            df = self.cache.load(key)
            if df is not None:
                dfs.append(df)
                logger.debug("Loaded cached table: %s (%d rows)", key, len(df))
            else:
                logger.warning("Cache miss for key: %s", key)

        if not dfs:
            self._loaded_data = None
            return

        if len(dfs) == 1:
            self._loaded_data = dfs[0]
        else:
            # Merge on SEQN (the respondent identifier present in every
            # NHANES table).
            try:
                from bio_search.data.merger import DataMerger

                merger = DataMerger()
                self._loaded_data = merger.merge_tables(dfs)
            except ImportError:
                # Fallback: simple SEQN outer merge
                merged = dfs[0]
                for other in dfs[1:]:
                    merged = pd.merge(
                        merged, other, on="SEQN", how="outer"
                    )
                self._loaded_data = merged

        logger.info(
            "Working dataset: %d rows x %d columns from %d table(s)",
            len(self._loaded_data),
            len(self._loaded_data.columns),
            len(dfs),
        )

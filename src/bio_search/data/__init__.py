"""NHANES data pipeline -- download, cache, load, harmonise, merge.

This package provides the complete data ingestion layer for bio-search.
The typical flow is:

    1. **Catalog** -- browse available NHANES cycles and tables.
    2. **Download** -- fetch XPT files from the CDC.
    3. **Load** -- read XPT into pandas and classify variable types.
    4. **Cache** -- persist DataFrames in DuckDB for fast reuse.
    5. **Harmonize** -- rename variables to canonical names across cycles.
    6. **Merge** -- join tables within a cycle and stack across cycles.
    7. **Codebook** -- parse CDC codebook HTML for variable metadata.
"""

from bio_search.data.cache import CacheError, DataCache
from bio_search.data.catalog import NHANESCatalog
from bio_search.data.codebook import CodebookError, CodebookParser
from bio_search.data.downloader import DownloadError, NHANESDownloader
from bio_search.data.harmonizer import HARMONIZATION_MAP, VariableHarmonizer
from bio_search.data.loader import DataLoader, LoadError
from bio_search.data.merger import DataMerger, MergeError

__all__ = [
    # Catalog
    "NHANESCatalog",
    # Downloader
    "NHANESDownloader",
    "DownloadError",
    # Loader
    "DataLoader",
    "LoadError",
    # Cache
    "DataCache",
    "CacheError",
    # Harmonizer
    "VariableHarmonizer",
    "HARMONIZATION_MAP",
    # Merger
    "DataMerger",
    "MergeError",
    # Codebook
    "CodebookParser",
    "CodebookError",
]

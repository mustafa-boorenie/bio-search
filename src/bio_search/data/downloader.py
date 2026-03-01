"""Async XPT file downloader for NHANES data.

This module provides NHANESDownloader, which downloads SAS transport
(XPT) files from the CDC website.  Downloads are async (httpx), retried
on transient failures (tenacity), and cached on disk so subsequent runs
skip already-fetched files.

Typical usage::

    downloader = NHANESDownloader()
    path = await downloader.download_table(table, data_dir)
    paths = await downloader.download_tables(tables, data_dir)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Callable

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bio_search.models.nhanes import NHANESTable

logger = logging.getLogger(__name__)

# Type alias for the optional progress callback.
# Signature: (completed: int, total: int, table_name: str) -> None
ProgressCallback = Callable[[int, int, str], None] | None

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
_RETRY_DECORATOR = retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TransportError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)


class DownloadError(Exception):
    """Raised when a table download fails after all retries."""


class NHANESDownloader:
    """Async downloader for CDC NHANES XPT files.

    Files are saved under ``data_dir/raw/{cycle}/{table_name}.XPT``.
    If the file already exists on disk the download is skipped entirely,
    making repeated runs cheap.

    Args:
        timeout: Per-request timeout in seconds.  CDC files can be
            several hundred MB for large tables, so the default is
            generous.
        max_concurrent: Maximum number of parallel downloads.  Keeps
            the CDC server happy and avoids saturating the local
            network.
    """

    def __init__(
        self,
        timeout: float = 120.0,
        max_concurrent: int = 4,
    ) -> None:
        self._timeout = timeout
        self._max_concurrent = max_concurrent

    # -- Public API ---------------------------------------------------------

    async def download_table(
        self,
        table: NHANESTable,
        data_dir: Path,
    ) -> Path:
        """Download a single XPT file from the CDC.

        Args:
            table: The ``NHANESTable`` to download.
            data_dir: Root data directory.  The file will be written to
                ``data_dir/raw/{cycle}/{table.name}.XPT``.

        Returns:
            Path to the downloaded (or already-cached) XPT file.

        Raises:
            DownloadError: If the download fails after all retries.
        """
        dest = self._dest_path(data_dir, table)

        if dest.exists() and dest.stat().st_size > 0:
            logger.debug("Cached: %s (%s)", table.name, dest)
            return dest

        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            await self._fetch(table.xpt_url, dest)
        except Exception as exc:
            # Clean up partial file
            if dest.exists():
                dest.unlink(missing_ok=True)
            raise DownloadError(
                f"Failed to download {table.name} from {table.xpt_url}: {exc}"
            ) from exc

        logger.info("Downloaded: %s -> %s (%d bytes)", table.name, dest, dest.stat().st_size)
        return dest

    async def download_tables(
        self,
        tables: list[NHANESTable],
        data_dir: Path,
        progress_callback: ProgressCallback = None,
    ) -> list[Path]:
        """Download multiple XPT files concurrently.

        Args:
            tables: List of tables to download.
            data_dir: Root data directory.
            progress_callback: Optional callable invoked after each
                table completes.  Signature:
                ``(completed, total, table_name) -> None``.

        Returns:
            List of paths to downloaded files, in the same order as
            ``tables``.
        """
        semaphore = asyncio.Semaphore(self._max_concurrent)
        completed = 0
        total = len(tables)
        results: list[Path | Exception] = [None] * total  # type: ignore[list-item]

        async def _download_one(idx: int, table: NHANESTable) -> None:
            nonlocal completed
            async with semaphore:
                try:
                    path = await self.download_table(table, data_dir)
                    results[idx] = path
                except Exception as exc:
                    logger.error("Download failed for %s: %s", table.name, exc)
                    results[idx] = exc

                completed += 1
                if progress_callback is not None:
                    try:
                        progress_callback(completed, total, table.name)
                    except Exception:
                        logger.warning(
                            "Progress callback raised an exception", exc_info=True
                        )

        tasks = [
            asyncio.create_task(_download_one(i, tbl))
            for i, tbl in enumerate(tables)
        ]
        await asyncio.gather(*tasks)

        # Separate successes from failures
        paths: list[Path] = []
        errors: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Path):
                paths.append(result)
            else:
                errors.append(f"{tables[i].name}: {result}")

        if errors:
            logger.warning(
                "%d of %d downloads failed:\n  %s",
                len(errors),
                total,
                "\n  ".join(errors),
            )

        return paths

    # -- Internal helpers ---------------------------------------------------

    @staticmethod
    def _dest_path(data_dir: Path, table: NHANESTable) -> Path:
        """Compute the local file path for a table download."""
        return data_dir / "raw" / table.cycle / f"{table.name}.XPT"

    @_RETRY_DECORATOR
    async def _fetch(self, url: str, dest: Path) -> None:
        """Stream-download a URL to disk with retry.

        Uses httpx async streaming to avoid loading the entire file
        into memory.
        """
        logger.debug("Fetching %s", url)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
        ) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()

                tmp_dest = dest.with_suffix(".XPT.tmp")
                try:
                    with open(tmp_dest, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65_536):
                            f.write(chunk)

                    # Atomic rename so a partial file is never mistaken
                    # for a complete download.
                    tmp_dest.rename(dest)
                except Exception:
                    tmp_dest.unlink(missing_ok=True)
                    raise

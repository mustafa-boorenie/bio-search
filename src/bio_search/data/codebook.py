"""NHANES codebook parser.

Each NHANES table has a corresponding HTML codebook on the CDC website
that documents every variable: its name, label, type, value ranges,
and coded categories.  This module downloads and parses those codebooks
into structured ``NHANESVariable`` objects.

The CDC codebook pages have a predictable structure:

    https://wwwn.cdc.gov/Nchs/Nhanes/{cycle}/{table_name}.htm

Each variable section contains a header with the variable name and
SAS label, followed by a table of value codes and frequencies.

Typical usage::

    parser = CodebookParser()

    # Download + parse in one call
    variables = await parser.fetch_codebook("DEMO_J", "2017-2018")
    for var in variables.values():
        print(var.name, var.label)

    # Or parse HTML you already have
    variables = parser.parse_codebook(html_string)
"""

from __future__ import annotations

import logging
import re

import httpx
from bs4 import BeautifulSoup, Tag

from bio_search.models.nhanes import NHANESVariable, VariableType

logger = logging.getLogger(__name__)

_CDC_BASE = "https://wwwn.cdc.gov/Nchs/Nhanes"


class CodebookError(Exception):
    """Raised when codebook fetching or parsing fails."""


class CodebookParser:
    """Downloads and parses NHANES codebook HTML pages.

    The parser is stateless; each call is independent.  For bulk
    operations, reuse a single instance to benefit from any future
    caching.
    """

    @staticmethod
    def _codebook_url(table_name: str, cycle: str) -> str:
        """Build the CDC codebook URL for a table."""
        return f"{_CDC_BASE}/{cycle}/{table_name}.htm"

    # -- HTML parsing -------------------------------------------------------

    @staticmethod
    def parse_codebook(
        html: str,
        table_name: str = "",
        cycle: str = "",
    ) -> dict[str, NHANESVariable]:
        """Parse a CDC codebook HTML page into NHANESVariable objects.

        The CDC codebook pages organise each variable in a ``<div>``
        with an ``id`` that contains the variable name.  Inside each
        div there is typically:

        - A header (``<h3>``) with the variable name and SAS label.
        - A description paragraph.
        - A frequency table with value codes.

        This parser is intentionally lenient -- if a section cannot be
        parsed, it is logged and skipped rather than raising.

        Args:
            html: The raw HTML content of the codebook page.
            table_name: Optional table name to attach to each variable.
            cycle: Optional cycle to attach to each variable.

        Returns:
            Dict mapping variable name to ``NHANESVariable``.
        """
        soup = BeautifulSoup(html, "lxml")
        variables: dict[str, NHANESVariable] = {}

        # Strategy 1: Look for divs with id matching variable patterns
        # CDC pages use <div id="VARNAME"> or similar
        var_divs = soup.find_all("div", id=True)

        for div in var_divs:
            try:
                var = _parse_variable_div(div, table_name, cycle)
                if var is not None:
                    variables[var.name] = var
            except Exception:
                logger.debug(
                    "Could not parse div id=%s", div.get("id"), exc_info=True
                )

        # Strategy 2: If we got nothing from divs, try parsing tables directly
        if not variables:
            variables = _parse_from_tables(soup, table_name, cycle)

        # Strategy 3: Fallback -- look for <h3> headers with var info
        if not variables:
            variables = _parse_from_headers(soup, table_name, cycle)

        logger.info(
            "Parsed codebook for %s (%s): %d variables",
            table_name or "unknown",
            cycle or "unknown",
            len(variables),
        )
        return variables

    # -- Async fetcher ------------------------------------------------------

    async def fetch_codebook(
        self,
        table_name: str,
        cycle: str,
        timeout: float = 30.0,
    ) -> dict[str, NHANESVariable]:
        """Download a codebook from the CDC and parse it.

        Args:
            table_name: The NHANES table name (e.g. ``"DEMO_J"``).
            cycle: The NHANES cycle (e.g. ``"2017-2018"``).
            timeout: HTTP request timeout in seconds.

        Returns:
            Dict mapping variable name to ``NHANESVariable``.

        Raises:
            CodebookError: If the download or parse fails.
        """
        url = self._codebook_url(table_name, cycle)
        logger.debug("Fetching codebook: %s", url)

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout),
                follow_redirects=True,
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPStatusError as exc:
            raise CodebookError(
                f"HTTP {exc.response.status_code} fetching codebook for "
                f"{table_name} ({cycle}): {url}"
            ) from exc
        except httpx.TransportError as exc:
            raise CodebookError(
                f"Network error fetching codebook for {table_name} ({cycle}): {exc}"
            ) from exc

        return self.parse_codebook(html, table_name=table_name, cycle=cycle)


# ---------------------------------------------------------------------------
# Internal parsing helpers
# ---------------------------------------------------------------------------

# Pattern to match NHANES variable names (2-8 uppercase chars + optional digits)
_VAR_NAME_PATTERN = re.compile(r"^[A-Z]{2,8}[A-Z0-9_]{0,10}$")


def _looks_like_var_name(text: str) -> bool:
    """Return True if text looks like a valid NHANES variable name."""
    return bool(_VAR_NAME_PATTERN.match(text.strip()))


def _parse_variable_div(
    div: Tag,
    table_name: str,
    cycle: str,
) -> NHANESVariable | None:
    """Try to extract a variable from a codebook <div>."""
    div_id = div.get("id", "")
    if not isinstance(div_id, str):
        return None

    # The div id is often the variable name itself
    var_name = div_id.strip().upper()

    # Look for a header inside the div
    header = div.find(["h3", "h2", "h4"])
    label = ""
    if header:
        header_text = header.get_text(strip=True)
        # Header often looks like "VARNAME - Description" or just description
        if " - " in header_text:
            parts = header_text.split(" - ", 1)
            if _looks_like_var_name(parts[0].strip()):
                var_name = parts[0].strip().upper()
                label = parts[1].strip()
            else:
                label = header_text
        else:
            label = header_text

    if not _looks_like_var_name(var_name):
        return None

    # Try to find a description paragraph
    description = ""
    desc_tag = div.find("p")
    if desc_tag:
        description = desc_tag.get_text(strip=True)

    # Use description as label if we did not find one
    if not label and description:
        label = description[:200]  # Truncate very long descriptions

    if not label:
        label = var_name  # Last resort

    return NHANESVariable(
        name=var_name,
        label=label,
        table=table_name,
        var_type=VariableType.CONTINUOUS,  # default; refined after data load
    )


def _parse_from_tables(
    soup: BeautifulSoup,
    table_name: str,
    cycle: str,
) -> dict[str, NHANESVariable]:
    """Fallback: scan HTML tables for variable definitions."""
    variables: dict[str, NHANESVariable] = {}

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all(["td", "th"])
            if len(cells) >= 2:
                name_text = cells[0].get_text(strip=True).upper()
                label_text = cells[1].get_text(strip=True)
                if _looks_like_var_name(name_text) and label_text:
                    variables[name_text] = NHANESVariable(
                        name=name_text,
                        label=label_text,
                        table=table_name,
                        var_type=VariableType.CONTINUOUS,
                    )

    return variables


def _parse_from_headers(
    soup: BeautifulSoup,
    table_name: str,
    cycle: str,
) -> dict[str, NHANESVariable]:
    """Fallback: scan headers for 'VARNAME - Label' patterns."""
    variables: dict[str, NHANESVariable] = {}

    for header in soup.find_all(["h2", "h3", "h4"]):
        text = header.get_text(strip=True)
        if " - " in text:
            parts = text.split(" - ", 1)
            name = parts[0].strip().upper()
            label = parts[1].strip()
            if _looks_like_var_name(name) and label:
                variables[name] = NHANESVariable(
                    name=name,
                    label=label,
                    table=table_name,
                    var_type=VariableType.CONTINUOUS,
                )

    return variables

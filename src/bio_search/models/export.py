"""Pydantic models for result export and manuscript generation.

These models define *what* gets exported and *how*.  The actual
rendering logic lives in ``output/`` and ``llm/``; these are pure data
containers that get passed around.
"""

from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class ExportFormat(str, Enum):
    """Supported output file formats for analysis results."""

    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    PNG = "png"
    SVG = "svg"
    PDF = "pdf"


class ExportConfig(BaseModel):
    """User-selected export options.

    Attributes:
        format: File format for the primary data export.
        output_dir: Directory where exported files are written.
            Created automatically if it does not exist.
        include_charts: Whether to render and include visualisations
            (forest plots, volcano plots, etc.) alongside the data
            export.
    """

    format: ExportFormat = ExportFormat.CSV
    output_dir: Path = Path("./output")
    include_charts: bool = True


class ManuscriptSection(str, Enum):
    """Standard sections of a scientific manuscript.

    Used to request LLM-generated text for individual sections or
    to assemble a full draft from cached section outputs.
    """

    INTRODUCTION = "introduction"
    METHODS = "methods"
    RESULTS = "results"
    DISCUSSION = "discussion"
    ABSTRACT = "abstract"

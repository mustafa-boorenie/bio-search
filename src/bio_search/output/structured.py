"""Structured data export (CSV, JSON) for analysis results.

The ``StructuredExporter`` writes flat files that are easy to load in
R, Excel, or downstream Python scripts.  Every method returns the
``Path`` to the file it created.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from bio_search.models.analysis import AssociationResult, EWASResult


class StructuredExporter:
    """Export analysis results to structured formats."""

    def __init__(self, output_dir: Path = Path("./output")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------
    def to_csv(
        self,
        results: list[AssociationResult],
        filename: str = "results.csv",
    ) -> Path:
        """Write association results to a CSV file."""
        path = self.output_dir / filename
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "exposure",
                    "outcome",
                    "beta",
                    "se",
                    "p_value",
                    "fdr_p",
                    "ci_lower",
                    "ci_upper",
                    "n",
                    "model_type",
                    "effect_size",
                    "effect_size_type",
                    "clinically_significant",
                    "covariates",
                ]
            )
            for r in results:
                writer.writerow(
                    [
                        r.exposure,
                        r.outcome,
                        r.beta,
                        r.se,
                        r.p_value,
                        r.fdr_p,
                        r.ci.lower,
                        r.ci.upper,
                        r.n,
                        r.model_type,
                        r.effect_size,
                        r.effect_size_type,
                        r.clinically_significant,
                        ";".join(r.covariates),
                    ]
                )
        return path

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------
    def to_json(
        self,
        results: list[AssociationResult],
        filename: str = "results.json",
    ) -> Path:
        """Write association results to a JSON file."""
        path = self.output_dir / filename
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "n_results": len(results),
            "results": [r.model_dump(mode="json") for r in results],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    # ------------------------------------------------------------------
    # EWAS convenience wrappers
    # ------------------------------------------------------------------
    def ewas_to_csv(
        self,
        ewas: EWASResult,
        filename: str | None = None,
    ) -> Path:
        """Write an entire EWAS result set to CSV."""
        if filename is None:
            filename = (
                f"ewas_{ewas.outcome}_{ewas.timestamp.strftime('%Y%m%d_%H%M%S')}.csv"
            )
        return self.to_csv(ewas.associations, filename)

    def ewas_to_json(
        self,
        ewas: EWASResult,
        filename: str | None = None,
    ) -> Path:
        """Write an entire EWAS result set to JSON."""
        if filename is None:
            filename = (
                f"ewas_{ewas.outcome}_{ewas.timestamp.strftime('%Y%m%d_%H%M%S')}.json"
            )
        path = self.output_dir / filename
        data = ewas.model_dump(mode="json")
        data["timestamp"] = str(data["timestamp"])
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return path

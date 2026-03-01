"""Human-readable summary report generation.

``ReportGenerator`` produces both plain-text reports (suitable for
piping to a file or pager) and rich terminal output using the ``rich``
library.  The text report doubles as a lightweight audit log that
records the analysis parameters alongside the findings.
"""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from bio_search.models.analysis import EWASResult


class ReportGenerator:
    """Generate summary reports of EWAS findings."""

    def __init__(self, output_dir: Path = Path("./output")) -> None:
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Plain-text report
    # ------------------------------------------------------------------
    def generate_text_report(
        self,
        ewas: EWASResult,
        fdr_threshold: float = 0.05,
    ) -> str:
        """Return a multi-line plain-text summary of EWAS findings."""
        sig = [
            r
            for r in ewas.associations
            if r.fdr_p is not None and r.fdr_p < fdr_threshold
        ]

        lines = [
            f"EWAS Report: {ewas.outcome}",
            "=" * 50,
            f"Date: {ewas.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"Total exposures tested: {ewas.n_tests}",
            f"Associations computed: {len(ewas.associations)}",
            f"FDR method: {ewas.fdr_method}",
            f"Significant (FDR < {fdr_threshold}): {len(sig)}",
            "",
        ]

        if sig:
            lines.append("Top Significant Associations:")
            lines.append("-" * 50)
            lines.append(
                f"{'Exposure':<20} {'Beta':>10} {'P-value':>12} {'FDR P':>12} {'N':>8}"
            )
            lines.append("-" * 50)
            for r in sig[:30]:
                lines.append(
                    f"{r.exposure:<20} {r.beta:>10.4f} "
                    f"{r.p_value:>12.2e} {r.fdr_p:>12.2e} {r.n:>8}"
                )
        else:
            lines.append(
                "No significant associations found after FDR correction."
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Save to file
    # ------------------------------------------------------------------
    def save_report(
        self,
        ewas: EWASResult,
        filename: str | None = None,
    ) -> Path:
        """Write the plain-text report to disk and return the path."""
        if filename is None:
            filename = (
                f"report_{ewas.outcome}_"
                f"{ewas.timestamp.strftime('%Y%m%d_%H%M%S')}.txt"
            )
        path = self.output_dir / filename
        path.write_text(self.generate_text_report(ewas))
        return path

    # ------------------------------------------------------------------
    # Rich terminal output
    # ------------------------------------------------------------------
    def print_report(
        self,
        ewas: EWASResult,
        fdr_threshold: float = 0.05,
    ) -> None:
        """Print a formatted report to the terminal using rich."""
        console = Console()
        sig = [
            r
            for r in ewas.associations
            if r.fdr_p is not None and r.fdr_p < fdr_threshold
        ]

        console.print(
            Panel(
                f"Outcome: [bold]{ewas.outcome}[/]\n"
                f"Tests: {ewas.n_tests} | "
                f"Computed: {len(ewas.associations)} | "
                f"Significant: [bold green]{len(sig)}[/] "
                f"(FDR < {fdr_threshold})",
                title="EWAS Report",
            )
        )

        if sig:
            table = Table(
                title=f"Top Significant Associations (n={len(sig)})",
                show_lines=True,
            )
            table.add_column("#", style="dim")
            table.add_column("Exposure", style="cyan")
            table.add_column("Beta", justify="right")
            table.add_column("P-value", justify="right")
            table.add_column("FDR P", justify="right", style="bold")
            table.add_column("N", justify="right")

            for i, r in enumerate(sig[:30], 1):
                table.add_row(
                    str(i),
                    r.exposure,
                    f"{r.beta:.4f}",
                    f"{r.p_value:.2e}",
                    f"{r.fdr_p:.2e}",
                    str(r.n),
                )
            console.print(table)

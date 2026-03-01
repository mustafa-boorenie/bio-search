"""Terminal-based chart rendering using plotext.

These helpers are designed for quick visual feedback in the TUI *and*
in plain terminal sessions (e.g. ``bio-search`` CLI).  They call
``plt.show()`` directly, so output goes to stdout.

For publication-quality raster/vector figures, see
``visualization.export.FigureExporter``.
"""

from __future__ import annotations

import numpy as np
import plotext as plt
from rich.console import Console
from rich.table import Table

from bio_search.models.analysis import AssociationResult


class TerminalVisualizer:
    """Generate terminal-based charts using plotext."""

    # ------------------------------------------------------------------
    # Manhattan plot
    # ------------------------------------------------------------------
    @staticmethod
    def manhattan(
        results: list[AssociationResult],
        title: str = "Manhattan Plot",
    ) -> None:
        """Manhattan plot: -log10(p) by exposure index."""
        plt.clear_figure()
        plt.title(title)
        plt.xlabel("Exposure Index")
        plt.ylabel("-log10(p-value)")

        p_values = [r.p_value for r in results]
        log_p = [-np.log10(p) if p > 0 else 20 for p in p_values]
        x = list(range(len(log_p)))

        # Colour by significance
        sig = [
            i for i, r in enumerate(results) if r.fdr_p is not None and r.fdr_p < 0.05
        ]
        nonsig = [i for i in range(len(results)) if i not in sig]

        if nonsig:
            plt.scatter(
                [x[i] for i in nonsig],
                [log_p[i] for i in nonsig],
                color="gray",
            )
        if sig:
            plt.scatter(
                [x[i] for i in sig],
                [log_p[i] for i in sig],
                color="red",
            )

        # Bonferroni line
        if len(results) > 0:
            bon_line = -np.log10(0.05 / len(results))
            plt.hline(bon_line, color="blue")

        plt.show()

    # ------------------------------------------------------------------
    # Volcano plot
    # ------------------------------------------------------------------
    @staticmethod
    def volcano(
        results: list[AssociationResult],
        title: str = "Volcano Plot",
    ) -> None:
        """Volcano plot: effect size vs -log10(p)."""
        plt.clear_figure()
        plt.title(title)
        plt.xlabel("Effect Size (Beta)")
        plt.ylabel("-log10(p-value)")

        betas = [r.beta for r in results]
        log_p = [-np.log10(r.p_value) if r.p_value > 0 else 20 for r in results]

        plt.scatter(betas, log_p)
        plt.show()

    # ------------------------------------------------------------------
    # Forest plot
    # ------------------------------------------------------------------
    @staticmethod
    def forest(
        results: list[AssociationResult],
        title: str = "Forest Plot",
        max_display: int = 20,
    ) -> None:
        """Forest plot for top results."""
        plt.clear_figure()
        plt.title(title)

        display = results[:max_display]
        names = [r.exposure[:20] for r in display]
        betas = [r.beta for r in display]

        y_pos = list(range(len(names)))
        plt.scatter(betas, y_pos)
        plt.vline(0, color="red")
        plt.yticks(y_pos, names)
        plt.show()

    # ------------------------------------------------------------------
    # Generic scatter
    # ------------------------------------------------------------------
    @staticmethod
    def scatter(
        x_data: list[float],
        y_data: list[float],
        x_label: str,
        y_label: str,
        title: str | None = None,
    ) -> None:
        """Simple scatter plot."""
        plt.clear_figure()
        plt.title(title or f"{x_label} vs {y_label}")
        plt.xlabel(x_label)
        plt.ylabel(y_label)
        plt.scatter(x_data, y_data)
        plt.show()

    # ------------------------------------------------------------------
    # Rich summary table
    # ------------------------------------------------------------------
    @staticmethod
    def summary_table(
        results: list[AssociationResult],
        max_display: int = 20,
    ) -> None:
        """Print a rich-formatted summary table to the terminal."""
        console = Console()
        table = Table(title="Top Associations", show_lines=True)
        table.add_column("Rank", style="dim")
        table.add_column("Exposure", style="cyan")
        table.add_column("Beta", justify="right")
        table.add_column("SE", justify="right")
        table.add_column("P-value", justify="right")
        table.add_column("FDR P", justify="right")
        table.add_column("N", justify="right")
        table.add_column("Sig", style="bold")

        for i, r in enumerate(results[:max_display], 1):
            fdr = r.fdr_p if r.fdr_p is not None else 1.0
            if fdr < 0.001:
                sig = "***"
            elif fdr < 0.01:
                sig = "**"
            elif fdr < 0.05:
                sig = "*"
            else:
                sig = ""

            table.add_row(
                str(i),
                r.exposure,
                f"{r.beta:.4f}",
                f"{r.se:.4f}",
                f"{r.p_value:.2e}",
                f"{r.fdr_p:.2e}" if r.fdr_p is not None else "\u2014",
                str(r.n),
                sig,
            )
        console.print(table)

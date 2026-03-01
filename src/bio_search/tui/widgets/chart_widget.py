"""Terminal chart widget using textual-plotext.

Provides convenience methods for the plot types most commonly used in
environment-wide association studies:

- **Manhattan plot** -- ``-log10(p)`` by exposure index, with a
  Bonferroni significance threshold line.
- **Volcano plot** -- effect size (beta) vs ``-log10(p)``.
- **Forest plot** -- effect sizes with confidence intervals for the
  top-N results.
- **Scatter plot** -- generic x-vs-y scatter.

All methods clear the previous figure before drawing.
"""

from __future__ import annotations

import math

from textual_plotext import PlotextPlot

from bio_search.models.analysis import AssociationResult


class ChartWidget(PlotextPlot):
    """Plotext-backed chart widget with EWAS-specific plot helpers."""

    # -- Manhattan ---------------------------------------------------------

    def manhattan_plot(self, results: list[AssociationResult]) -> None:
        """Draw a Manhattan plot: -log10(p) by exposure index.

        A horizontal red line marks the Bonferroni-corrected significance
        threshold (0.05 / number_of_tests).

        Parameters
        ----------
        results:
            The association results to plot.
        """
        if not results:
            return

        self.plt.clear_figure()
        self.plt.title("Manhattan Plot")
        self.plt.xlabel("Exposure Index")
        self.plt.ylabel("-log10(p-value)")

        p_values = [r.p_value for r in results]
        log_p = [
            -math.log10(p) if p > 0 else 20.0
            for p in p_values
        ]
        x = list(range(len(log_p)))

        self.plt.scatter(x, log_p)

        # Bonferroni significance line
        if len(results) > 0:
            bonferroni = 0.05 / len(results)
            sig_line = -math.log10(bonferroni) if bonferroni > 0 else 20.0
            self.plt.hline(sig_line, color="red")

        self.refresh()

    # -- Volcano -----------------------------------------------------------

    def volcano_plot(self, results: list[AssociationResult]) -> None:
        """Draw a Volcano plot: effect size vs -log10(p).

        Parameters
        ----------
        results:
            The association results to plot.
        """
        if not results:
            return

        self.plt.clear_figure()
        self.plt.title("Volcano Plot")
        self.plt.xlabel("Effect Size (Beta)")
        self.plt.ylabel("-log10(p-value)")

        betas = [r.beta for r in results]
        log_p = [
            -math.log10(r.p_value) if r.p_value > 0 else 20.0
            for r in results
        ]

        self.plt.scatter(betas, log_p)
        self.plt.vline(0, color="dim")
        self.refresh()

    # -- Forest ------------------------------------------------------------

    def forest_plot(
        self, results: list[AssociationResult], max_rows: int = 20
    ) -> None:
        """Draw a Forest plot: effect sizes with confidence intervals.

        Only the first *max_rows* results are shown to keep the plot
        readable in a terminal.

        Parameters
        ----------
        results:
            The association results to plot.
        max_rows:
            Maximum number of rows to display.
        """
        if not results:
            return

        subset = results[:max_rows]

        self.plt.clear_figure()
        self.plt.title("Forest Plot")
        self.plt.xlabel("Effect Size (Beta)")

        names = [r.exposure[:20] for r in subset]
        betas = [r.beta for r in subset]
        y_pos = list(range(len(names)))

        self.plt.scatter(betas, y_pos)

        # Draw CI whiskers as individual horizontal segments
        for i, r in enumerate(subset):
            lo = r.ci.lower
            hi = r.ci.upper
            self.plt.plot([lo, hi], [i, i], color="blue")

        self.plt.yticks(y_pos, names)
        self.plt.vline(0, color="red")
        self.refresh()

    # -- Generic scatter ---------------------------------------------------

    def scatter_plot(
        self,
        x_data: list[float],
        y_data: list[float],
        x_label: str,
        y_label: str,
    ) -> None:
        """Draw a simple scatter plot.

        Parameters
        ----------
        x_data:
            Horizontal axis values.
        y_data:
            Vertical axis values.
        x_label:
            Label for the X axis.
        y_label:
            Label for the Y axis.
        """
        if not x_data or not y_data:
            return

        self.plt.clear_figure()
        self.plt.title(f"{x_label} vs {y_label}")
        self.plt.xlabel(x_label)
        self.plt.ylabel(y_label)
        self.plt.scatter(x_data, y_data)
        self.refresh()

    # -- Clear -------------------------------------------------------------

    def clear_chart(self) -> None:
        """Erase the current figure."""
        self.plt.clear_figure()
        self.refresh()

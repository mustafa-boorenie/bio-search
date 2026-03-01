"""Publication-quality figure export using matplotlib and seaborn.

All figures are saved to disk (PNG by default) using the non-interactive
``Agg`` backend so the module works in headless environments and inside
Textual apps without popping up windows.

Every public method returns the ``Path`` to the saved image so callers
can display it, attach it to an email, or embed it in a manuscript.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # Must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import seaborn as sns  # noqa: E402

from bio_search.models.analysis import AssociationResult  # noqa: E402


class FigureExporter:
    """Generate publication-quality figures."""

    def __init__(self, output_dir: Path = Path("./output"), dpi: int = 300) -> None:
        self.output_dir = output_dir
        self.dpi = dpi
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sns.set_theme(style="whitegrid", font_scale=1.2)

    # ------------------------------------------------------------------
    # Manhattan plot
    # ------------------------------------------------------------------
    def manhattan(
        self,
        results: list[AssociationResult],
        filename: str = "manhattan.png",
    ) -> Path:
        """Manhattan plot coloured by FDR significance."""
        fig, ax = plt.subplots(figsize=(14, 6))

        p_values = [r.p_value for r in results]
        log_p = [-np.log10(p) if p > 0 else 20 for p in p_values]
        x = range(len(log_p))

        colors = [
            "red" if (r.fdr_p or 1) < 0.05 else "steelblue" for r in results
        ]
        ax.scatter(x, log_p, c=colors, alpha=0.7, s=20)

        # Bonferroni line
        if len(results) > 0:
            bon = -np.log10(0.05 / len(results))
            ax.axhline(
                y=bon,
                color="red",
                linestyle="--",
                alpha=0.5,
                label=f"Bonferroni (p={0.05 / len(results):.1e})",
            )

        ax.set_xlabel("Exposure Index")
        ax.set_ylabel("-log\u2081\u2080(p-value)")
        ax.set_title("Manhattan Plot \u2014 EWAS Results")
        ax.legend()

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    # ------------------------------------------------------------------
    # Volcano plot
    # ------------------------------------------------------------------
    def volcano(
        self,
        results: list[AssociationResult],
        filename: str = "volcano.png",
    ) -> Path:
        """Volcano plot with top-hit labels."""
        fig, ax = plt.subplots(figsize=(10, 8))

        betas = [r.beta for r in results]
        log_p = [-np.log10(r.p_value) if r.p_value > 0 else 20 for r in results]
        colors = ["red" if (r.fdr_p or 1) < 0.05 else "gray" for r in results]

        ax.scatter(betas, log_p, c=colors, alpha=0.6, s=20)
        ax.set_xlabel("Effect Size (\u03b2)")
        ax.set_ylabel("-log\u2081\u2080(p-value)")
        ax.set_title("Volcano Plot \u2014 EWAS Results")
        ax.axvline(x=0, color="black", linestyle="-", alpha=0.3)

        # Label top hits
        sig = [
            (r, b, lp)
            for r, b, lp in zip(results, betas, log_p)
            if (r.fdr_p or 1) < 0.05
        ]
        sig.sort(key=lambda t: t[2], reverse=True)
        for r, b, lp in sig[:10]:
            ax.annotate(
                r.exposure,
                (b, lp),
                fontsize=7,
                alpha=0.8,
                xytext=(5, 5),
                textcoords="offset points",
            )

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    # ------------------------------------------------------------------
    # Forest plot
    # ------------------------------------------------------------------
    def forest(
        self,
        results: list[AssociationResult],
        filename: str = "forest.png",
        max_display: int = 20,
    ) -> Path:
        """Horizontal forest plot with 95 % confidence intervals."""
        display = results[:max_display]
        fig, ax = plt.subplots(figsize=(10, max(6, len(display) * 0.4)))

        y_pos = range(len(display))
        betas = [r.beta for r in display]
        ci_lower = [r.ci.lower for r in display]
        ci_upper = [r.ci.upper for r in display]
        names = [r.exposure for r in display]
        xerr_lower = [b - lo for b, lo in zip(betas, ci_lower)]
        xerr_upper = [hi - b for b, hi in zip(betas, ci_upper)]

        ax.errorbar(
            betas,
            y_pos,
            xerr=[xerr_lower, xerr_upper],
            fmt="o",
            color="steelblue",
            capsize=3,
            markersize=5,
        )
        ax.axvline(x=0, color="red", linestyle="--", alpha=0.5)
        ax.set_yticks(list(y_pos))
        ax.set_yticklabels(names)
        ax.set_xlabel("Effect Size (\u03b2) with 95% CI")
        ax.set_title("Forest Plot \u2014 Top Associations")
        ax.invert_yaxis()

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

    # ------------------------------------------------------------------
    # Generic scatter
    # ------------------------------------------------------------------
    def scatter(
        self,
        x_data: list[float],
        y_data: list[float],
        x_label: str,
        y_label: str,
        filename: str = "scatter.png",
        title: str | None = None,
    ) -> Path:
        """Scatter plot with optional linear regression overlay."""
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.scatter(x_data, y_data, alpha=0.3, s=10)
        ax.set_xlabel(x_label)
        ax.set_ylabel(y_label)
        ax.set_title(title or f"{x_label} vs {y_label}")

        # Add regression line when there are enough points
        if len(x_data) > 2:
            z = np.polyfit(x_data, y_data, 1)
            p = np.poly1d(z)
            x_sorted = sorted(x_data)
            ax.plot(x_sorted, [p(xi) for xi in x_sorted], "r--", alpha=0.5)

        path = self.output_dir / filename
        fig.savefig(path, dpi=self.dpi, bbox_inches="tight")
        plt.close(fig)
        return path

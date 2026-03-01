"""Manuscript section generation from EWAS results.

``ManuscriptGenerator`` can operate in two modes:

1. **LLM mode** -- when an ``llm_client`` is provided, sections are
   drafted by GPT-4o with a domain-specific prompt.
2. **Template mode** -- when no LLM is available, a structured
   template is returned with placeholders for manual editing.

Either way, the output is a Markdown string ready to save to disk or
display in the TUI editor.
"""

from __future__ import annotations

from pathlib import Path

from bio_search.models.analysis import EWASResult
from bio_search.models.export import ManuscriptSection


class ManuscriptGenerator:
    """Generate manuscript sections from analysis results."""

    def __init__(
        self,
        llm_client=None,
        output_dir: Path = Path("./output"),
    ) -> None:
        self.llm_client = llm_client
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_results_summary(
        self,
        ewas: EWASResult,
        fdr_threshold: float = 0.05,
    ) -> str:
        """Build a concise text summary of significant findings."""
        sig = [
            r
            for r in ewas.associations
            if r.fdr_p is not None and r.fdr_p < fdr_threshold
        ]
        lines = [
            f"Outcome: {ewas.outcome}",
            f"Total exposures tested: {ewas.n_tests}",
            f"Significant associations (FDR<{fdr_threshold}): {len(sig)}",
            "",
        ]
        for r in sig[:20]:
            lines.append(
                f"- {r.exposure}: beta={r.beta:.4f}, p={r.p_value:.2e}, "
                f"FDR p={r.fdr_p:.2e}, N={r.n}"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def generate_section(
        self,
        section: ManuscriptSection,
        ewas: EWASResult,
        context: str = "",
    ) -> str:
        """Generate a manuscript section, using LLM if available."""
        if self.llm_client is None:
            return self._generate_template(section, ewas)

        summary = self._build_results_summary(ewas)

        prompts = {
            ManuscriptSection.METHODS: (
                f"Write a Methods section for a cross-sectional study using NHANES data.\n"
                f"Analysis details:\n{summary}\n{context}\n"
                f"Include: study design, data source, variable definitions, statistical methods "
                f"(survey-weighted regression, FDR correction), software used."
            ),
            ManuscriptSection.RESULTS: (
                f"Write a Results section based on these EWAS findings:\n{summary}\n{context}\n"
                f"Include: sample characteristics, main findings with effect sizes and CIs, "
                f"sensitivity analyses."
            ),
            ManuscriptSection.INTRODUCTION: (
                f"Write an Introduction for a study examining associations with {ewas.outcome} "
                f"using NHANES data.\n{context}\n"
                f"Include: background, knowledge gap, study rationale."
            ),
            ManuscriptSection.DISCUSSION: (
                f"Write a Discussion section for these findings:\n{summary}\n{context}\n"
                f"Include: main findings interpretation, comparison with literature, "
                f"strengths/limitations, public health implications."
            ),
            ManuscriptSection.ABSTRACT: (
                f"Write a structured Abstract (Background, Methods, Results, Conclusions) "
                f"for these findings:\n{summary}\n{context}"
            ),
        }

        prompt = prompts.get(
            section, f"Write the {section.value} section.\n{summary}"
        )
        response = await self.llm_client.generate(prompt)
        return response

    def _generate_template(
        self,
        section: ManuscriptSection,
        ewas: EWASResult,
    ) -> str:
        """Return a structured template when no LLM is available."""
        sig = [
            r
            for r in ewas.associations
            if r.fdr_p is not None and r.fdr_p < 0.05
        ]

        templates = {
            ManuscriptSection.METHODS: (
                f"## Methods\n\n"
                f"### Study Design and Data Source\n"
                f"This cross-sectional study used data from the National Health and Nutrition "
                f"Examination Survey (NHANES).\n\n"
                f"### Statistical Analysis\n"
                f"An environment-wide association study (EWAS) was conducted to systematically "
                f"evaluate associations between {ewas.n_tests} exposures and {ewas.outcome}. "
                f"Survey-weighted linear/logistic regression was used, adjusting for age, sex, "
                f"race/ethnicity, and income-to-poverty ratio. Multiple testing was corrected "
                f"using the Benjamini-Hochberg false discovery rate (FDR) method.\n"
            ),
            ManuscriptSection.RESULTS: (
                f"## Results\n\n"
                f"Of {ewas.n_tests} exposures tested, {len(sig)} showed statistically significant "
                f"associations with {ewas.outcome} after FDR correction (q < 0.05).\n\n"
                + (
                    "\n".join(
                        f"- **{r.exposure}**: beta = {r.beta:.3f} "
                        f"(95% CI: {r.ci.lower:.3f}, {r.ci.upper:.3f}), "
                        f"p = {r.p_value:.2e}, FDR q = {r.fdr_p:.2e}"
                        for r in sig[:10]
                    )
                    if sig
                    else "No significant associations were found."
                )
            ),
            ManuscriptSection.INTRODUCTION: (
                f"## Introduction\n\n"
                f"[Background on {ewas.outcome} and its public health relevance.]\n\n"
                f"[Known risk factors and knowledge gaps.]\n\n"
                f"[Rationale for using the EWAS approach with NHANES data.]\n"
            ),
            ManuscriptSection.DISCUSSION: (
                f"## Discussion\n\n"
                f"[Summary of main findings: {len(sig)} significant associations identified.]\n\n"
                f"[Comparison with existing literature.]\n\n"
                f"[Strengths: nationally representative sample, comprehensive exposure "
                f"assessment.]\n\n"
                f"[Limitations: cross-sectional design, residual confounding.]\n\n"
                f"[Public health implications and future directions.]\n"
            ),
            ManuscriptSection.ABSTRACT: (
                f"## Abstract\n\n"
                f"**Background:** [Context for studying {ewas.outcome}.]\n\n"
                f"**Methods:** An EWAS was performed using NHANES data, testing "
                f"{ewas.n_tests} exposures.\n\n"
                f"**Results:** {len(sig)} significant associations were identified "
                f"after FDR correction.\n\n"
                f"**Conclusions:** [Key takeaways.]\n"
            ),
        }
        return templates.get(
            section,
            f"## {section.value.title()}\n\n[Section content to be generated]",
        )

    def save_section(
        self,
        section: ManuscriptSection,
        content: str,
        filename: str | None = None,
    ) -> Path:
        """Write a manuscript section to disk."""
        if filename is None:
            filename = f"{section.value.lower()}.md"
        path = self.output_dir / filename
        path.write_text(content)
        return path

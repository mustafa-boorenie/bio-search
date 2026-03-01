"""LLM-powered manuscript section writer.

``ManuscriptWriter`` wraps the ``LLMClient`` with epidemiology-specific
system prompts and structured finding summaries so that each section
reads like a draft from a domain expert.

For the template-only fallback path (no API key), see
``output.manuscript.ManuscriptGenerator._generate_template``.
"""

from __future__ import annotations

from bio_search.llm.client import LLMClient
from bio_search.models.analysis import EWASResult
from bio_search.models.export import ManuscriptSection


class ManuscriptWriter:
    """LLM-powered manuscript section writer."""

    SECTION_PROMPTS: dict[ManuscriptSection, str] = {
        ManuscriptSection.METHODS: (
            "Write a detailed Methods section for a cross-sectional epidemiological study. "
            "Data source: NHANES (National Health and Nutrition Examination Survey). "
            "Statistical approach: Environment-Wide Association Study (EWAS) with "
            "survey-weighted regression, adjusting for demographic confounders, "
            "with Benjamini-Hochberg FDR correction for multiple comparisons. "
            "Include: study population, inclusion/exclusion criteria, variable definitions, "
            "statistical model specification, software and packages used."
        ),
        ManuscriptSection.RESULTS: (
            "Write a Results section describing the findings. "
            "Include: sample demographics, number of associations tested, "
            "significant findings with effect estimates and confidence intervals, "
            "direction and magnitude of effects."
        ),
        ManuscriptSection.INTRODUCTION: (
            "Write an Introduction that establishes the scientific context. "
            "Include: background on the outcome variable, known risk factors, "
            "knowledge gaps, rationale for the EWAS approach, study objectives."
        ),
        ManuscriptSection.DISCUSSION: (
            "Write a Discussion section. Include: summary of main findings, "
            "comparison with existing literature, biological plausibility, "
            "strengths (nationally representative sample, comprehensive exposure assessment), "
            "limitations (cross-sectional design, residual confounding), "
            "public health implications, future directions."
        ),
        ManuscriptSection.ABSTRACT: (
            "Write a structured abstract with sections: "
            "Background, Methods, Results, Conclusions. "
            "Keep each section to 2-3 sentences. Total word count: 250-300."
        ),
    }

    SYSTEM_MESSAGE = (
        "You are a scientific writing assistant specializing in epidemiology and "
        "public health research. Write in formal academic style suitable for a "
        "peer-reviewed journal. Use precise statistical language."
    )

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def write_section(
        self,
        section: ManuscriptSection,
        ewas: EWASResult,
        additional_context: str = "",
    ) -> str:
        """Generate a single manuscript section."""
        sig = [
            r
            for r in ewas.associations
            if r.fdr_p is not None and r.fdr_p < 0.05
        ]

        findings = "\n".join(
            f"- {r.exposure}: beta={r.beta:.4f} "
            f"(95% CI: {r.ci.lower:.4f}, {r.ci.upper:.4f}), "
            f"p={r.p_value:.2e}, FDR q={r.fdr_p:.2e}, N={r.n}"
            for r in sig[:20]
        )

        prompt = (
            f"{self.SECTION_PROMPTS[section]}\n\n"
            f"Outcome variable: {ewas.outcome}\n"
            f"Total exposures tested: {ewas.n_tests}\n"
            f"Significant associations (FDR<0.05): {len(sig)}\n\n"
            f"Key findings:\n{findings}\n\n"
            f"{additional_context}"
        )

        return await self.llm.generate(
            prompt, system=self.SYSTEM_MESSAGE, max_tokens=3000
        )

    async def write_full_manuscript(self, ewas: EWASResult) -> dict[str, str]:
        """Generate all standard manuscript sections sequentially."""
        sections: dict[str, str] = {}
        for section in [
            ManuscriptSection.ABSTRACT,
            ManuscriptSection.INTRODUCTION,
            ManuscriptSection.METHODS,
            ManuscriptSection.RESULTS,
            ManuscriptSection.DISCUSSION,
        ]:
            sections[section.value] = await self.write_section(section, ewas)
        return sections

"""Natural-language query parsing for the NHANES TUI.

``QueryParser`` translates free-text questions like "What affects blood
glucose?" into structured analysis specifications that the pipeline
can execute.

Two parsing strategies are used:

1. **LLM parse** -- sends the query to GPT-4o with a curated system
   prompt that enumerates common NHANES variables.  Returns structured
   JSON.
2. **Fallback parse** -- keyword/regex matching when no LLM is
   available or when the LLM call fails.
"""

from __future__ import annotations

import json
import logging

from bio_search.llm.client import LLMClient

logger = logging.getLogger(__name__)


class QueryParser:
    """Parse natural language queries into analysis specifications."""

    SYSTEM_PROMPT = (
        "You are an NHANES data analysis assistant. Parse the user's natural language query "
        "into a structured analysis specification. Respond with JSON only.\n\n"
        "Available analysis types: ewas, guided, info\n"
        "Common NHANES variables:\n"
        "- LBXGLU: Fasting glucose (mg/dL)\n"
        "- LBXGH: Glycohemoglobin HbA1c (%)\n"
        "- LBXTC: Total cholesterol (mg/dL)\n"
        "- LBXTR: Triglycerides (mg/dL)\n"
        "- LBDLDL: LDL cholesterol (mg/dL)\n"
        "- LBXSCR: Serum creatinine (mg/dL)\n"
        "- LBXBPB: Blood lead (ug/dL)\n"
        "- LBXBCD: Blood cadmium (ug/L)\n"
        "- LBXCOT: Serum cotinine (ng/mL)\n"
        "- BMXBMI: Body mass index (kg/m2)\n"
        "- BPXOSY: Systolic blood pressure (mmHg)\n"
        "- LBXHSCRP: High-sensitivity CRP (mg/L)\n"
        "- RIDAGEYR: Age (years)\n"
        "- RIAGENDR: Sex (1=Male, 2=Female)\n\n"
        "Output format:\n"
        '{"type": "ewas"|"guided"|"info", "outcome": "VAR", "exposure": "VAR"|null, '
        '"covariates": ["VAR", ...]|null}'
    )

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def parse(self, query: str) -> dict:
        """Parse a natural-language query into an analysis spec dict."""
        if not self.llm.available:
            return self._fallback_parse(query)

        try:
            response = await self.llm.generate(
                query, system=self.SYSTEM_PROMPT, temperature=0.1
            )
            # Extract JSON from response (strip markdown fences if present)
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            return json.loads(text)
        except Exception as e:
            logger.warning("LLM parse failed: %s, using fallback", e)
            return self._fallback_parse(query)

    def _fallback_parse(self, query: str) -> dict:
        """Simple keyword-based fallback parser."""
        query_upper = query.upper()

        # Look for known variable names in the raw query
        known_vars = [
            "LBXGLU",
            "LBXGH",
            "LBXTC",
            "LBXTR",
            "LBDLDL",
            "LBXSCR",
            "LBXBPB",
            "LBXBCD",
            "LBXCOT",
            "BMXBMI",
            "BPXOSY",
            "LBXHSCRP",
        ]
        found = [v for v in known_vars if v in query_upper]

        if len(found) >= 2:
            return {"type": "guided", "outcome": found[1], "exposure": found[0]}
        if len(found) == 1:
            return {"type": "ewas", "outcome": found[0]}

        # Keyword matching for plain-English queries
        keyword_map = {
            "glucose": "LBXGLU",
            "diabetes": "LBXGH",
            "hba1c": "LBXGH",
            "cholesterol": "LBXTC",
            "triglyceride": "LBXTR",
            "ldl": "LBDLDL",
            "creatinine": "LBXSCR",
            "kidney": "LBXSCR",
            "lead": "LBXBPB",
            "cadmium": "LBXBCD",
            "smoking": "LBXCOT",
            "cotinine": "LBXCOT",
            "bmi": "BMXBMI",
            "obesity": "BMXBMI",
            "blood pressure": "BPXOSY",
            "crp": "LBXHSCRP",
            "inflammation": "LBXHSCRP",
        }

        found_kw: list[str] = []
        for kw, var in keyword_map.items():
            if kw in query.lower():
                found_kw.append(var)

        # Deduplicate while preserving order
        found_kw = list(dict.fromkeys(found_kw))

        if len(found_kw) >= 2:
            return {
                "type": "guided",
                "outcome": found_kw[1],
                "exposure": found_kw[0],
            }
        if len(found_kw) == 1:
            return {"type": "ewas", "outcome": found_kw[0]}

        return {"type": "info", "query": query}

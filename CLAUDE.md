# Bio-Search Development Guide

## Project Overview

Bio-Search is an NHANES Biomedical Association Mining TUI — a terminal-based research tool for epidemiologists that downloads CDC NHANES datasets, runs Environment-Wide Association Studies (EWAS), performs guided deep-dive analyses, tracks associations across survey cycles, and uses LLMs to interpret results and generate manuscript-quality scientific writing.

## Tech Stack

- **Python 3.11+** with **Hatchling** build system
- **Textual** (TUI framework) + **Rich** (formatting) + **plotext** (inline charts)
- **pandas** + **numpy** + **scipy** + **statsmodels** + **samplics** (survey statistics)
- **DuckDB** (persistent DataFrame cache)
- **httpx** + **tenacity** (async CDC data downloads with retry)
- **OpenAI** / **Anthropic** SDKs (multi-provider LLM support)
- **Pydantic v2** + **pydantic-settings** (models and configuration)
- **matplotlib** + **seaborn** (export-quality charts)

## Project Structure

```
src/bio_search/
  app.py              # Top-level Textual App, wires all subsystems
  config.py           # Pydantic-settings config (env vars / .env)
  __main__.py          # Entry point
  models/             # Pydantic data models (nhanes, analysis, survey, export)
  data/               # Data layer: catalog, downloader, loader, cache, harmonizer, merger
  analysis/           # Statistical engine: EWAS, guided, regression, subgroup, trend, clinical
  survey/             # Survey design, estimation, weight selection
  llm/                # Multi-provider LLM: client, query parser, manuscript writer
  output/             # Report and manuscript generation
  visualization/      # Terminal (plotext) and export (matplotlib) charts
  tui/                # UI layer: screens, widgets, styles
tests/
  unit/               # Unit tests for catalog, EWAS, effect size, etc.
  integration/        # (empty — planned)
```

## Commands

```bash
# Install
pip install -e .                    # Standard
pip install -e '.[anthropic]'       # With Anthropic support
pip install -e '.[dev]'             # With dev tools (pytest, ruff)

# Run
bio-search                          # Installed script
python -m bio_search                # Module invocation

# Dev
pytest                              # Run tests
ruff check src/                     # Lint
ruff format src/                    # Format
```

## Configuration

All settings via environment variables or `.env` file, prefixed `BIO_SEARCH_`:

| Variable | Default | Purpose |
|---|---|---|
| `DATA_DIR` | `./data` | XPT files and DuckDB cache |
| `LLM_PROVIDER` | `openai` | `openai`, `anthropic`, `minimax`, `kimi`, `qwen`, `ollama` |
| `LLM_API_KEY` | None | Universal LLM API key |
| `LLM_MODEL` | Provider default | Override model name |
| `LLM_BASE_URL` | None | Override API endpoint |
| `EWAS_MIN_N` | `200` | Minimum sample size per association |
| `FDR_ALPHA` | `0.05` | Benjamini-Hochberg threshold |

## Architecture Patterns

- **Layered**: `App` owns subsystems -> `MainScreen` calls async methods -> analysis runs in executor threads
- **Data pipeline**: CDC XPT -> Downloader -> Loader -> Harmonizer -> DuckDB Cache -> Merger -> SurveyDesign
- **Analysis pipeline**: SurveyEstimator -> RegressionAnalyzer -> EWASScanner/GuidedAnalyzer -> FDR correction -> ClinicalSignificance
- **Survey correctness**: Stratified multi-stage design (SDMVSTRA/SDMVPSU), MEC vs interview weights, CDC weight division for combined cycles, cluster-robust SEs
- **LLM routing**: Single `LLMClient.generate()` routes to OpenAI-compatible API or Anthropic SDK based on provider setting
- **All models are Pydantic v2**: `AssociationResult` is the atomic unit for every statistical test

## TUI Slash Commands

`/browse`, `/download`, `/load`, `/ewas`, `/guided`, `/info`, `/search`, `/export`, `/clear`, `/help`, `/quit`

Keyboard shortcuts: `d`=Browse, `e`=EWAS, `g`=Guided, `x`=Export, `?`=Help, `q`=Quit

## Code Style

- Line length: 100 (ruff)
- Lint rules: E, F, I (pycodestyle errors, pyflakes, isort)
- Target: Python 3.11
- Use Pydantic models for all data structures
- Use `async`/`await` for I/O, `run_in_executor` for CPU-bound analysis
- Type hints throughout (use `X | None` not `Optional[X]`)

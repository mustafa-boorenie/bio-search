# Bio-Search — Product Requirements Document

## Vision

Bio-Search is a terminal-native research workstation for epidemiologists and public health researchers. It enables rapid exploration of CDC NHANES (National Health and Nutrition Examination Survey) data through Environment-Wide Association Studies (EWAS), guided deep-dive analyses, and AI-assisted scientific interpretation — all without leaving the terminal.

## Target Users

- Epidemiologists running association studies on NHANES data
- Public health researchers exploring exposure-outcome relationships
- Biostatisticians needing survey-weighted analysis with proper complex survey methodology
- Graduate students learning NHANES data analysis workflows

## Core Workflows

### 1. Data Discovery & Acquisition
- **Browse** the hardcoded NHANES catalog (5 cycles: 2013-2014 through 2021-2023, ~110 tables)
- **Search** variables by name or label across all tables
- **Download** SAS XPT files directly from the CDC with async retry
- **Cache** downloaded DataFrames in DuckDB for instant reload
- **Harmonize** variable names across cycles to canonical forms

### 2. Environment-Wide Association Study (EWAS)
- Select an outcome variable (e.g., LBXGLU for fasting glucose)
- Automatically scan every eligible exposure variable in the loaded dataset
- Apply survey-weighted regression (linear for continuous, logistic for binary outcomes)
- Correct for multiple testing (Benjamini-Hochberg FDR, Bonferroni, Holm)
- Render results as inline Rich table + Manhattan plot in terminal
- Filter by minimum sample size and max missing data fraction

### 3. Guided Deep-Dive Analysis
- Select a specific exposure-outcome pair for detailed analysis
- Run primary survey-weighted regression with automatic covariate selection
- Stratify by subgroups: sex, race/ethnicity, age groups, income quartiles
- Track the same association across multiple NHANES cycles (temporal trend)
- Render results as inline table + forest plot

### 4. AI-Assisted Interpretation
- Natural language queries processed by configurable LLM (OpenAI, Anthropic, MiniMax, Kimi, Qwen)
- Query parser converts natural language to structured analysis specifications
- Manuscript writer generates journal-quality sections (abstract, introduction, methods, results, discussion)
- Falls back to keyword matching when no LLM is configured
- Full functionality available via slash commands without any LLM

### 5. Export & Reporting
- Plain text + Rich terminal reports
- Export-quality charts via matplotlib/seaborn
- Manuscript section generation
- Planned: CSV, JSON, XLSX export

## Technical Requirements

### Survey Statistics Correctness (Non-Negotiable)
- Stratified multi-stage cluster design: strata=SDMVSTRA, PSU=SDMVPSU
- MEC exam weights for laboratory/examination data, interview weights for questionnaire-only
- Weight division by number of combined cycles (CDC mandate)
- Cluster-robust (Huber-White sandwich) standard errors
- Taylor series linearization for variance estimation (via samplics)

### Performance
- Async downloads with configurable concurrency (default: 4 workers)
- DuckDB columnar cache for sub-second table reloads
- Analysis runs in background thread (run_in_executor) to keep TUI responsive
- Lazy engine initialization to avoid import-time overhead

### Extensibility
- Multi-provider LLM architecture (single interface, multiple backends)
- Pydantic models for all data structures (serializable, validated)
- Modular analysis pipeline (each analyzer is independently testable)
- Plugin-ready catalog design (currently hardcoded, designed for future dynamic loading)

---

## Current State (v0.1.0)

### Implemented
- Full NHANES data pipeline: catalog, download, load, harmonize, cache, merge
- Complete EWAS engine with survey-weighted regression and FDR correction
- Guided analysis with subgroup stratification and temporal trends
- Multi-provider LLM integration (OpenAI, Anthropic, MiniMax, Kimi, Qwen)
- Chat-style TUI with slash commands, tab completion, and keyboard shortcuts
- Inline Manhattan plots and forest plots via plotext
- Clinical significance assessment with MCID thresholds for ~30 biomarkers
- Effect size calculations (Cohen's d, odds ratio, standardized beta)
- Variable harmonization across survey cycles
- DuckDB persistent DataFrame cache
- Unit tests for catalog, EWAS, effect size, multiple testing, survey weights, variable classification

### Not Yet Implemented
- **Export functionality**: `/export` command is a placeholder — CSV, JSON, XLSX output not wired up
- **Integration tests**: `tests/integration/` directory exists but is empty
- **Codebook module**: `data/codebook.py` exists but functionality is incomplete
- **Structured output**: `output/structured.py` exists but needs completion
- **Correlation analysis**: `analysis/correlation.py` exists but not fully integrated
- **Dynamic catalog updates**: Catalog is hardcoded; no live scraping of CDC website for new cycles/tables
- **README**: Empty placeholder — no user-facing documentation
- **CI/CD**: No GitHub Actions or automated pipeline
- **Batch mode**: No headless/CLI-only mode for scripting — TUI only
- **Data validation**: No integrity checks on downloaded XPT files
- **Session persistence**: Analysis results are lost when the TUI exits
- **Multi-cycle EWAS**: EWAS currently works on single merged dataset; no automated cross-cycle comparison workflow
- **Codebook parsing**: Online CDC codebook scraping for richer variable metadata
- **Error recovery**: Limited graceful handling of network failures mid-download

## Milestones

### v0.2.0 — Export & Documentation
- Wire up `/export` for CSV, JSON, XLSX
- Write README with installation, quickstart, and usage examples
- Add session result persistence (save/load analysis results)
- Set up CI with GitHub Actions (lint + test)

### v0.3.0 — Robustness & Testing
- Integration tests covering full download-analyze-export workflows
- Data validation on downloaded XPT files
- Graceful error recovery for network failures
- Batch/headless CLI mode for scripting

### v0.4.0 — Extended Analysis
- Multi-cycle EWAS comparison workflow
- Dynamic catalog updates (scrape CDC for new cycles)
- CDC codebook parsing for enriched variable metadata
- Correlation matrix analysis
- Session persistence for analysis history

### v1.0.0 — Production Ready
- Comprehensive documentation and tutorials
- Plugin system for custom analysis modules
- Performance benchmarks and optimization
- Community contribution guidelines

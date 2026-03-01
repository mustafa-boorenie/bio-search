# Bio-Search

**NHANES Biomedical Association Mining TUI** — a terminal-based research workstation for epidemiologists exploring CDC NHANES survey data.

Bio-Search downloads NHANES datasets directly from the CDC, runs Environment-Wide Association Studies (EWAS) with proper survey-weighted statistics, performs guided deep-dive analyses with subgroup stratification, and uses LLMs to interpret results and generate manuscript-quality scientific writing — all from your terminal.

```
 ___ ___ ___      ___ ___   _   ___  ___ _  _
| _ )_ _/ _ \ ___/ __| __| /_\ | _ \/ __| || |
| _ \| | (_) |___\__ \ _| / _ \|   / (__| __ |
|___/___\___/    |___/___/_/ \_\_|_\\___|_||_|
```

## Features

- **NHANES Data Pipeline** — Browse, download, and cache CDC NHANES datasets (5 cycles, 2013–2023, ~110 tables) with async retry and DuckDB persistence
- **Environment-Wide Association Study (EWAS)** — Scan every exposure against an outcome with survey-weighted regression, FDR correction, and inline Manhattan plots
- **Guided Deep-Dive** — Analyze specific exposure-outcome pairs with subgroup stratification (sex, race, age, income) and temporal trend tracking across cycles
- **Survey Statistics Done Right** — Stratified multi-stage cluster design, MEC/interview weight selection, CDC weight adjustment for combined cycles, cluster-robust standard errors
- **Multi-Provider LLM** — Natural language queries and manuscript generation via OpenAI, Anthropic, MiniMax, Kimi, or Qwen (fully usable without any LLM)
- **Terminal-Native** — Chat-style TUI with Rich tables, inline plotext charts, slash commands, and keyboard shortcuts

## Installation

Requires **Python 3.11+**.

```bash
# Clone and install
git clone https://github.com/mustafa-boorenie/bio-search.git
cd bio-search
pip install -e .

# With Anthropic LLM support
pip install -e '.[anthropic]'

# With dev tools (pytest, ruff)
pip install -e '.[dev]'
```

## Quick Start

```bash
# Launch the TUI
bio-search
```

### Typical Workflow

```
# 1. Browse available data
/browse
/browse 2017-2018

# 2. Download tables
/download 2017-2018 DEMO_J
/download 2017-2018 GLU_J

# 3. Load into working dataset
/load 2017-2018_DEMO_J 2017-2018_GLU_J

# 4. Run EWAS — scan all exposures against fasting glucose
/ewas LBXGLU

# 5. Deep-dive into a specific association
/guided LBXBPB LBXGLU

# 6. Search and inspect variables
/search glucose
/info LBXGLU
```

### Commands

| Command | Description |
|---|---|
| `/browse [cycle] [table]` | Browse the NHANES catalog |
| `/download <cycle> <table>` | Download and cache a table |
| `/load <key> ...` | Load cached tables into working dataset |
| `/ewas <outcome>` | Run environment-wide association scan |
| `/guided <exposure> <outcome>` | Guided deep-dive analysis |
| `/info <variable>` | Show variable metadata |
| `/search <query>` | Search variables by name or label |
| `/export <format>` | Export results (CSV, JSON, XLSX) |
| `/clear` | Clear the chat log |
| `/help` | Show all commands |
| `/quit` | Exit |

**Keyboard shortcuts:** `d` Browse, `e` EWAS, `g` Guided, `x` Export, `?` Help, `q` Quit

### Natural Language Queries

Type plain text (without `/`) to ask questions via your configured LLM:

```
What biomarkers are associated with diabetes in NHANES?
Summarize the relationship between lead exposure and kidney function.
```

## Configuration

Copy `.env.example` to `.env` and configure:

```bash
# Data storage directory
BIO_SEARCH_DATA_DIR=./data

# LLM provider: openai, anthropic, minimax, kimi, qwen
BIO_SEARCH_LLM_PROVIDER=openai
BIO_SEARCH_LLM_API_KEY=sk-...

# Optional: override model or endpoint
BIO_SEARCH_LLM_MODEL=gpt-4o
BIO_SEARCH_LLM_BASE_URL=https://...

# EWAS parameters
BIO_SEARCH_EWAS_MIN_N=200         # Min sample size per association
BIO_SEARCH_EWAS_MAX_MISSING_PCT=0.5
BIO_SEARCH_FDR_ALPHA=0.05         # Benjamini-Hochberg threshold
```

The TUI is fully functional without an LLM — all analysis features work via slash commands.

## Development

```bash
# Run tests
pytest

# Lint and format
ruff check src/
ruff format src/
```

## License

MIT

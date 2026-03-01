"""Bio-Search application configuration.

Uses pydantic-settings to load configuration from environment variables
(prefixed BIO_SEARCH_) and/or a .env file.  Every knob the application
needs -- data directories, API keys, EWAS thresholds, download
parallelism -- lives here so there is a single source of truth.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration for the Bio-Search NHANES TUI.

    Attributes:
        data_dir: Local directory for cached XPT files and the DuckDB
            database.  Created automatically on first run.
        openai_api_key: Optional OpenAI API key used by the LLM agent
            for natural-language query interpretation and manuscript
            generation.  The TUI is fully usable without it.
        cdc_base_url: Root URL for the CDC NHANES data file server.
            Override only if you are mirroring the data locally.
        max_download_workers: Maximum concurrent HTTP connections when
            downloading XPT files from the CDC.
        ewas_min_n: Minimum sample size required for an association to
            be included in EWAS results.  Associations with fewer
            observations are silently dropped.
        ewas_max_missing_pct: Maximum fraction of missing values (0-1)
            allowed in an exposure or outcome column before the pair is
            excluded from analysis.
        ewas_workers: Number of parallel workers for running EWAS
            regression models.
        fdr_alpha: Family-wise significance level for Benjamini-Hochberg
            FDR correction.
    """

    model_config = SettingsConfigDict(
        env_prefix="BIO_SEARCH_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # -- Storage --
    data_dir: Path = Path("./data")

    # -- LLM --
    openai_api_key: str | None = None  # backward compat (used when provider=openai)
    llm_provider: str = "openai"  # openai | anthropic | minimax | kimi | qwen | ollama
    llm_api_key: str | None = None  # universal key (takes precedence over openai_api_key)
    llm_model: str | None = None  # override default model per provider
    llm_base_url: str | None = None  # override base URL (advanced)

    # -- CDC data source --
    cdc_base_url: str = "https://wwwn.cdc.gov/Nchs/Nhanes"

    # -- Download --
    max_download_workers: int = 4

    # -- EWAS parameters --
    ewas_min_n: int = 200
    ewas_max_missing_pct: float = 0.5
    ewas_workers: int = 4

    # -- Multiple-testing correction --
    fdr_alpha: float = 0.05

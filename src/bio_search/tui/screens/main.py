r"""Main screen -- chat-style single-column interface for Bio-Search.

Layout::

    +---------------------------------------------+
    |  Bio-Search: NHANES Association Mining      |  Header
    |---------------------------------------------|
    |  BIO-SEARCH (ASCII banner)                  |
    |  by Dr. Boorenie, powered by NHANES         |
    |  > /help                                    |  Chat log
    |  > /download 2017-2018 DEMO_J              |
    |  + Downloaded DEMO_J: 9,254 rows           |
    |---------------------------------------------|
    |  /browse    Browse catalog: ...             |  Completions
    |  /download  Download table: ...             |
    |---------------------------------------------|
    | > _                                        |  Input
    +---------------------------------------------+
    |  d browse  e ewas  g guided  q quit  ? help |  Footer

Keyboard bindings:
    d  -- pre-fill /browse in the command bar
    e  -- pre-fill /ewas in the command bar
    g  -- pre-fill /guided in the command bar
    x  -- pre-fill /export in the command bar
    ?  -- print keyboard shortcuts to the log
    q  -- quit the application
"""

from __future__ import annotations

import math
from pathlib import Path

import plotext as plt
from rich.table import Table as RichTable
from rich.text import Text
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

from bio_search.llm.client import PROVIDER_DEFAULTS
from bio_search.tui.widgets.command_input import CommandInput

# -- ASCII art banner (figlet "small" font, 46 chars wide) ----------------

_BANNER_LINES = [
    r" ___ ___ ___      ___ ___   _   ___  ___ _  _ ",
    r"| _ )_ _/ _ \ ___/ __| __| /_\ | _ \/ __| || |",
    r"| _ \| | (_) |___\__ \ _| / _ \|   / (__| __ |",
    r"|___/___\___/    |___/___/_/ \_\_|_\\___|_||_|",
]


class MainScreen(Screen):
    """Chat-style main screen with scrolling log and command input."""

    BINDINGS = [
        ("d", "browse", "Browse"),
        ("e", "start_ewas", "EWAS"),
        ("g", "start_guided", "Guided"),
        ("x", "export", "Export"),
        ("q", "quit", "Quit"),
        ("question_mark", "show_help", "Help"),
    ]

    # -- Layout ------------------------------------------------------------

    def compose(self):
        yield Header()
        yield RichLog(id="chat-log", wrap=True, markup=True)
        yield Static("", id="completions", markup=True)
        yield CommandInput(id="command-bar")
        yield Footer()

    # -- Startup -----------------------------------------------------------

    def on_mount(self) -> None:
        """Show the welcome banner and focus the command input."""
        self._setup_step: int = 0  # 0=not in setup, 1=provider, 2=api key
        self._setup_provider: str = ""

        log = self.query_one("#chat-log", RichLog)

        # ASCII art banner
        log.write("")
        for line in _BANNER_LINES:
            log.write(Text(line, style="bold cyan"))
        log.write("")
        log.write(Text("  by Dr. Boorenie, powered by NHANES", style="dim"))
        log.write("")
        log.write(
            "Type [bold]/help[/bold] for commands or "
            "press [bold]/[/bold] to see all commands.\n"
        )

        # First-launch onboarding hint
        if not Path(".env").exists():
            log.write(
                "[yellow]No .env file found.[/yellow] "
                "Run [bold]/setup[/bold] to configure your LLM provider "
                "and API key, or create a .env file manually.\n"
            )

        # Focus the command input so the user can type immediately
        self.query_one("#command-bar").focus()

    # -- Helpers -----------------------------------------------------------

    def _echo(self, text: str) -> None:
        """Echo a user command to the chat log."""
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[dim]> {text}[/dim]")

    def _log(self) -> RichLog:
        """Shorthand to get the chat log widget."""
        return self.query_one("#chat-log", RichLog)

    def _hide_completions(self) -> None:
        """Hide the completions dropdown."""
        c = self.query_one("#completions", Static)
        c.display = False

    # -- Slash-command completions -----------------------------------------

    def on_input_changed(self, event: Input.Changed) -> None:
        """Show matching slash commands as the user types."""
        if event.input.id != "command-bar":
            return

        completions = self.query_one("#completions", Static)
        value = event.value.strip()

        if value.startswith("/"):
            cmd_part = value.split()[0].lower()
            matches = [
                (cmd, desc)
                for cmd, desc in CommandInput.COMMANDS.items()
                if cmd.startswith(cmd_part)
            ]
            # Hide if exact match + args already typed, or no matches
            exact = len(matches) == 1 and matches[0][0] == cmd_part
            if matches and not (exact and " " in value):
                lines = "\n".join(
                    f"  [bold cyan]{cmd:<14}[/bold cyan] [dim]{desc}[/dim]"
                    for cmd, desc in matches
                )
                completions.update(lines)
                completions.display = True
            else:
                completions.display = False
        else:
            completions.display = False

    # -- Command dispatch --------------------------------------------------

    async def on_command_input_command_submitted(
        self, event: CommandInput.CommandSubmitted
    ) -> None:
        """Route slash commands to the appropriate handler."""
        self._hide_completions()
        log = self._log()
        cmd = event.command
        args = event.args

        # If in setup flow, route raw input there (unless it's /quit)
        if self._setup_step > 0 and cmd != "/quit":
            raw = f"{cmd} {' '.join(args)}".strip()
            self._echo(raw)
            self._handle_setup_input(raw)
            return

        # Echo the user input
        self._echo(f"{cmd} {' '.join(args)}".strip())

        if cmd == "/help":
            self._print_help(log)
        elif cmd == "/ewas" and args:
            await self._run_ewas(args[0])
        elif cmd == "/guided" and len(args) >= 2:
            await self._run_guided(args[0], args[1])
        elif cmd == "/download" and len(args) >= 2:
            await self._download_table(args[0], args[1])
        elif cmd == "/info" and args:
            self._show_variable_info(args[0])
        elif cmd == "/search" and args:
            self._search_variables(" ".join(args))
        elif cmd == "/load" and args:
            self._load_cached(args)
        elif cmd == "/browse":
            self._browse(args)
        elif cmd == "/clear":
            self._clear_workspace()
        elif cmd == "/export" and args:
            await self._export_results(args[0])
        elif cmd == "/setup":
            self._setup_command()
        elif cmd == "/quit":
            self.app.exit()
        else:
            log.write(
                f"[yellow]Unknown or incomplete command:[/yellow] "
                f"{cmd} {' '.join(args)}"
            )
            log.write("Type [bold]/help[/bold] for available commands.")

    async def on_command_input_nlquery_submitted(
        self, event: CommandInput.NLQuerySubmitted
    ) -> None:
        """Handle natural-language queries via configured LLM provider."""
        self._hide_completions()
        log = self._log()

        # If in setup flow, route raw input there
        if self._setup_step > 0:
            self._echo(event.query)
            self._handle_setup_input(event.query)
            return

        self._echo(event.query)

        if not self._get_llm_client().available:
            log.write(
                "[yellow]No LLM API key configured.[/yellow] "
                "Set [bold]BIO_SEARCH_LLM_API_KEY[/bold] and optionally "
                "[bold]BIO_SEARCH_LLM_PROVIDER[/bold] (openai, anthropic, "
                "minimax, kimi, qwen, ollama) in your environment or .env file.\n"
                "[dim]Legacy BIO_SEARCH_OPENAI_API_KEY also works for OpenAI.\n"
                "You can still use slash commands — type /help.[/dim]"
            )
            return

        await self._ask_llm(event.query)

    # -- Command implementations -------------------------------------------

    def _print_help(self, log: RichLog) -> None:
        """Print all available commands to the chat log."""
        table = RichTable(
            title="Available Commands",
            show_header=False,
            expand=False,
            border_style="dim",
            padding=(0, 1),
        )
        table.add_column("Command", style="bold cyan", no_wrap=True)
        table.add_column("Description")

        for cmd, desc in CommandInput.COMMANDS.items():
            table.add_row(cmd, desc)

        log.write(table)
        log.write(
            "[dim]Shortcuts: d=Browse  e=EWAS  g=Guided  "
            "x=Export  ?=Help  q=Quit[/dim]\n"
        )

    async def _run_ewas(self, outcome: str) -> None:
        """Execute an EWAS scan for the given outcome variable."""
        log = self._log()
        log.write(
            f"[bold green]Starting EWAS scan for outcome: {outcome}[/bold green]"
        )

        def progress_cb(current: int, total: int, var: str) -> None:
            pct = (current / total * 100) if total > 0 else 0
            self.call_from_thread(
                log.write,
                f"[dim]  Testing {current}/{total} ({pct:.0f}%): {var}[/dim]",
            )

        try:
            result = await self.app.run_ewas(outcome, progress_cb)

            if result and result.associations:
                sorted_assoc = sorted(
                    result.associations, key=lambda a: a.p_value
                )

                n_sig = sum(
                    1
                    for r in result.associations
                    if r.fdr_p is not None and r.fdr_p < 0.05
                )
                log.write(
                    f"\n[bold green]EWAS complete:[/bold green] "
                    f"{len(result.associations)} tested, "
                    f"[bold]{n_sig} significant[/bold] (FDR<0.05, "
                    f"method: {result.fdr_method})"
                )

                # Inline results table
                self._render_results_table(sorted_assoc)

                # Inline Manhattan plot
                self._render_manhattan(sorted_assoc)
            else:
                log.write(
                    "[yellow]No results returned. "
                    "Make sure data is loaded (/load).[/yellow]"
                )
        except Exception as exc:
            log.write(f"[bold red]EWAS error: {exc}[/bold red]")

    async def _run_guided(self, exposure: str, outcome: str) -> None:
        """Run a guided deep-dive analysis for one exposure-outcome pair."""
        log = self._log()
        log.write(
            f"[bold green]Guided analysis: "
            f"{exposure} -> {outcome}[/bold green]"
        )

        try:
            result = await self.app.run_guided(exposure, outcome)

            if result:
                all_results = [result.primary]
                for sg_list in result.subgroups.values():
                    all_results.extend(sg_list)

                p = result.primary
                log.write(
                    f"  Primary: Beta={p.beta:.4f}, "
                    f"p={p.p_value:.2e}, N={p.n}"
                )
                if result.subgroups:
                    log.write(
                        f"  Subgroups: "
                        f"{', '.join(result.subgroups.keys())}"
                    )

                # Inline results table
                self._render_results_table(all_results)

                # Inline forest plot
                if result.trend:
                    self._render_forest(result.trend)
            else:
                log.write(
                    "[yellow]No result. Make sure data is loaded.[/yellow]"
                )
        except Exception as exc:
            log.write(f"[bold red]Guided analysis error: {exc}[/bold red]")

    async def _download_table(self, cycle: str, table_name: str) -> None:
        """Download and cache a single NHANES table."""
        log = self._log()
        log.write(f"Downloading [bold]{table_name}[/bold] from {cycle}...")

        try:
            df = await self.app.download_table(cycle, table_name)
            if df is not None:
                log.write(
                    f"[green]+ Downloaded {table_name}: "
                    f"{len(df):,} rows, {len(df.columns)} columns[/green]"
                )
            else:
                log.write(
                    f"[yellow]Table {table_name} not found in "
                    f"cycle {cycle}.[/yellow]"
                )
        except Exception as exc:
            log.write(f"[bold red]Download error: {exc}[/bold red]")

    def _show_variable_info(self, var_name: str) -> None:
        """Look up a variable by name and display its metadata inline."""
        log = self._log()
        results = self.app.catalog.search_variables(var_name)

        if results:
            var = results[0]
            table = RichTable(
                title=var.name,
                show_header=False,
                expand=False,
                border_style="dim",
            )
            table.add_column("Field", style="bold cyan", no_wrap=True)
            table.add_column("Value")

            table.add_row("Label", var.label)
            table.add_row("Type", var.var_type.value)
            table.add_row("Table", var.table)

            if var.n_values is not None:
                table.add_row("Distinct values", str(var.n_values))

            if var.value_labels:
                items = list(var.value_labels.items())[:8]
                labels_str = ", ".join(f"{k}={v}" for k, v in items)
                if len(var.value_labels) > 8:
                    labels_str += f" ... ({len(var.value_labels)} total)"
                table.add_row("Value labels", labels_str)

            log.write(table)

            if len(results) > 1:
                log.write(
                    f"[dim]{len(results) - 1} more match(es) — "
                    f"use /search {var_name} for all[/dim]"
                )
        else:
            log.write(f"[yellow]Variable not found: {var_name}[/yellow]")

    def _search_variables(self, query: str) -> None:
        """Search variables by name or label substring."""
        log = self._log()
        results = self.app.catalog.search_variables(query)

        if results:
            table = RichTable(
                title=f"Search: '{query}' -- {len(results)} hit(s)",
                border_style="dim",
                expand=False,
            )
            table.add_column("#", style="dim", no_wrap=True)
            table.add_column("Variable", style="bold cyan", no_wrap=True)
            table.add_column("Label")
            table.add_column("Table", style="dim")

            for i, var in enumerate(results[:15], 1):
                table.add_row(str(i), var.name, var.label, var.table)

            log.write(table)

            if len(results) > 15:
                log.write(f"[dim]... and {len(results) - 15} more[/dim]")
        else:
            log.write(f"[yellow]No variables match '{query}'[/yellow]")

    def _load_cached(self, table_keys: list[str]) -> None:
        """Load previously cached tables into the working dataset."""
        log = self._log()
        log.write(f"Loading cached tables: {', '.join(table_keys)}")

        try:
            self.app.load_cached_data(table_keys)
            if self.app._loaded_data is not None:
                df = self.app._loaded_data
                log.write(
                    f"[green]+ Loaded {len(df):,} rows, "
                    f"{len(df.columns)} columns[/green]"
                )
            else:
                log.write("[yellow]No cached data found for those keys.[/yellow]")
        except Exception as exc:
            log.write(f"[bold red]Load error: {exc}[/bold red]")

    def _browse(self, args: list[str]) -> None:
        """Browse the NHANES catalog inline.

        /browse             -- list all cycles
        /browse <cycle>     -- list tables in that cycle
        /browse <cycle> <table> -- list variables in that table
        """
        log = self._log()
        catalog = self.app.catalog

        if not args:
            # List all cycles
            cycles = catalog.get_cycles()
            log.write("[bold]Available cycles:[/bold]")
            for cycle in cycles:
                tables = catalog.get_tables(cycle)
                log.write(f"  [cyan]{cycle}[/cyan]  ({len(tables)} tables)")
            log.write(
                "\n[dim]Use /browse <cycle> to see tables.[/dim]"
            )

        elif len(args) == 1:
            # List tables in a cycle
            cycle = args[0]
            tables = catalog.get_tables(cycle)
            if not tables:
                log.write(f"[yellow]Cycle not found: {cycle}[/yellow]")
                return

            table_widget = RichTable(
                title=f"Tables in {cycle}",
                border_style="dim",
                expand=False,
            )
            table_widget.add_column("Table", style="bold cyan", no_wrap=True)
            table_widget.add_column("Component", style="dim")
            table_widget.add_column("Description")

            for t in tables:
                table_widget.add_row(
                    t.name,
                    t.component.value.title(),
                    t.label,
                )

            log.write(table_widget)
            log.write(
                "[dim]Use /browse <cycle> <table> to see variables, "
                "or /download <cycle> <table> to fetch data.[/dim]"
            )

        else:
            # List variables in a table
            cycle, table_name = args[0], args[1]
            table = catalog.get_table(cycle, table_name)
            if table is None:
                log.write(
                    f"[yellow]Table {table_name} not found "
                    f"in {cycle}.[/yellow]"
                )
                return

            if not table.variables:
                log.write(
                    f"[dim]{table_name}: no variable metadata "
                    f"available in catalog.[/dim]"
                )
                return

            var_table = RichTable(
                title=f"{table_name} -- {table.label} ({cycle})",
                border_style="dim",
                expand=False,
            )
            var_table.add_column("Variable", style="bold cyan", no_wrap=True)
            var_table.add_column("Label")
            var_table.add_column("Type", style="dim")

            for var in table.variables:
                var_table.add_row(var.name, var.label, var.var_type.value)

            log.write(var_table)
            log.write(
                f"[dim]Use /info <VAR> for details or "
                f"/download {cycle} {table_name} to fetch data.[/dim]"
            )

    def _clear_workspace(self) -> None:
        """Clear the chat log."""
        log = self._log()
        log.clear()
        log.write("[dim]Cleared.[/dim]\n")

    async def _export_results(self, fmt: str) -> None:
        """Export the latest analysis results in the requested format.

        Supported formats: csv, json, report, figures.
        """
        log = self._log()
        fmt = fmt.lower()

        supported = ("csv", "json", "report", "figures")
        if fmt not in supported:
            log.write(
                f"[yellow]Unknown format '{fmt}'. "
                f"Supported: {', '.join(supported)}[/yellow]"
            )
            return

        # Gather association results from latest EWAS or guided analysis
        ewas_result = self.app._latest_ewas_result
        guided_result = self.app._latest_guided_result

        if ewas_result is None and guided_result is None:
            log.write(
                "[yellow]No results to export. "
                "Run /ewas or /guided first.[/yellow]"
            )
            return

        # Collect association results for CSV/JSON/figures
        associations = []
        if ewas_result:
            associations.extend(ewas_result.associations)
        if guided_result:
            associations.append(guided_result.primary)
            for sg_list in guided_result.subgroups.values():
                associations.extend(sg_list)

        output_dir = self.app.settings.data_dir / "output"

        try:
            if fmt == "csv":
                from bio_search.output.structured import StructuredExporter

                exporter = StructuredExporter(output_dir)
                if ewas_result:
                    path = exporter.ewas_to_csv(ewas_result)
                else:
                    path = exporter.to_csv(associations)
                log.write(f"[green]Exported CSV: {path}[/green]")

            elif fmt == "json":
                from bio_search.output.structured import StructuredExporter

                exporter = StructuredExporter(output_dir)
                if ewas_result:
                    path = exporter.ewas_to_json(ewas_result)
                else:
                    path = exporter.to_json(associations)
                log.write(f"[green]Exported JSON: {path}[/green]")

            elif fmt == "report":
                if ewas_result is None:
                    log.write(
                        "[yellow]Text reports require EWAS results. "
                        "Run /ewas first.[/yellow]"
                    )
                    return
                from bio_search.output.report import ReportGenerator

                gen = ReportGenerator(output_dir)
                path = gen.save_report(ewas_result)
                log.write(f"[green]Exported report: {path}[/green]")

            elif fmt == "figures":
                if not associations:
                    log.write("[yellow]No associations to plot.[/yellow]")
                    return
                from bio_search.visualization.export import FigureExporter

                fig_exp = FigureExporter(output_dir)
                paths = []
                paths.append(fig_exp.manhattan(associations))
                paths.append(fig_exp.volcano(associations))
                paths.append(fig_exp.forest(associations))
                for p in paths:
                    log.write(f"[green]Saved figure: {p}[/green]")

        except Exception as exc:
            log.write(f"[bold red]Export error: {exc}[/bold red]")

    # -- /setup flow --------------------------------------------------------

    def _setup_command(self) -> None:
        """Entry point for /setup — begin the interactive provider wizard."""
        log = self._log()
        self._setup_step = 1
        log.write("[bold]LLM Provider Setup[/bold]\n")
        self._show_provider_list(log)
        log.write("Enter a number to select a provider (or [bold]cancel[/bold] to abort):")

    def _show_provider_list(self, log: RichLog) -> None:
        """Display a numbered list of available LLM providers."""
        table = RichTable(
            title="Available Providers",
            show_header=True,
            expand=False,
            border_style="dim",
            padding=(0, 1),
        )
        table.add_column("#", style="bold", no_wrap=True)
        table.add_column("Provider", style="bold cyan", no_wrap=True)
        table.add_column("Default Model", style="dim")
        table.add_column("Note")

        for i, (name, defaults) in enumerate(PROVIDER_DEFAULTS.items(), 1):
            if name == "ollama":
                note = "local — no API key needed"
            elif name == "anthropic":
                note = "requires anthropic extra"
            else:
                note = "requires API key"
            table.add_row(str(i), name, defaults["model"] or "", note)

        log.write(table)

    def _handle_setup_input(self, raw: str) -> None:
        """State machine for the /setup wizard."""
        log = self._log()
        text = raw.strip().lower()

        if text == "cancel":
            self._setup_step = 0
            self._setup_provider = ""
            log.write("[dim]Setup cancelled.[/dim]\n")
            return

        if self._setup_step == 1:
            # Expect a number selecting the provider
            providers = list(PROVIDER_DEFAULTS.keys())
            try:
                idx = int(text) - 1
                if not (0 <= idx < len(providers)):
                    raise ValueError
            except ValueError:
                log.write(
                    f"[yellow]Enter a number 1-{len(providers)} "
                    f"or 'cancel'.[/yellow]"
                )
                return

            self._setup_provider = providers[idx]

            if self._setup_provider == "ollama":
                # Ollama needs no API key
                self._write_env(self._setup_provider, None)
                self._reset_llm_client()
                log.write(
                    f"[green]Provider set to [bold]{self._setup_provider}[/bold]. "
                    f"No API key needed — make sure Ollama is running "
                    f"on localhost:11434.[/green]\n"
                )
                self._setup_step = 0
                self._setup_provider = ""
            else:
                self._setup_step = 2
                log.write(
                    f"Selected [bold]{self._setup_provider}[/bold]. "
                    f"Enter your API key (or [bold]cancel[/bold] to abort):"
                )

        elif self._setup_step == 2:
            # Expect the API key string
            api_key = raw.strip()  # preserve original case
            if not api_key:
                log.write("[yellow]API key cannot be empty.[/yellow]")
                return

            self._write_env(self._setup_provider, api_key)
            self._reset_llm_client()
            log.write(
                f"[green]Saved! Provider=[bold]{self._setup_provider}[/bold], "
                f"API key written to .env.[/green]\n"
            )
            self._setup_step = 0
            self._setup_provider = ""

    def _write_env(self, provider: str, api_key: str | None) -> None:
        """Write or update BIO_SEARCH_LLM_PROVIDER and _API_KEY in .env."""
        env_path = Path(".env")
        lines: list[str] = []
        if env_path.exists():
            lines = env_path.read_text().splitlines()

        # Remove existing LLM provider/key lines, preserve everything else
        lines = [
            ln
            for ln in lines
            if not ln.strip().startswith("BIO_SEARCH_LLM_PROVIDER=")
            and not ln.strip().startswith("BIO_SEARCH_LLM_API_KEY=")
        ]

        lines.append(f"BIO_SEARCH_LLM_PROVIDER={provider}")
        if api_key:
            lines.append(f"BIO_SEARCH_LLM_API_KEY={api_key}")

        env_path.write_text("\n".join(lines) + "\n")

    def _reset_llm_client(self) -> None:
        """Reload settings from .env and recreate the LLM client."""
        from bio_search.config import Settings

        self.app.settings = Settings()
        if hasattr(self, "_llm_client"):
            del self._llm_client
        # Pre-warm the new client
        self._get_llm_client()

    # -- LLM ---------------------------------------------------------------

    def _get_llm_client(self):
        """Return a cached LLMClient instance."""
        if not hasattr(self, "_llm_client"):
            from bio_search.llm.client import LLMClient

            self._llm_client = LLMClient(self.app.settings)
        return self._llm_client

    async def _ask_llm(self, query: str) -> None:
        """Send a natural-language query to the configured LLM provider."""
        log = self._log()
        log.write("[dim]Thinking...[/dim]")

        try:
            llm = self._get_llm_client()

            # Build system prompt with context about loaded data
            data_ctx = ""
            if self.app._loaded_data is not None:
                df = self.app._loaded_data
                cols = ", ".join(df.columns[:30].tolist())
                data_ctx = (
                    f"\nCurrently loaded dataset: {len(df):,} rows, "
                    f"{len(df.columns)} columns.\n"
                    f"Columns (first 30): {cols}\n"
                )

            system = (
                "You are Bio-Search, an NHANES biomedical data analysis assistant. "
                "You help researchers explore CDC NHANES survey data, run "
                "environment-wide association studies (EWAS), and interpret results.\n"
                "Available slash commands the user can run:\n"
                "  /browse [cycle] [table] - browse the data catalog\n"
                "  /download <cycle> <table> - download a table\n"
                "  /load <key> - load cached tables\n"
                "  /ewas <outcome> - run EWAS scan\n"
                "  /guided <exposure> <outcome> - guided analysis\n"
                "  /info <var> - variable details\n"
                "  /search <query> - search variables\n"
                "When appropriate, suggest specific commands the user can run."
                + data_ctx
            )

            answer = await llm.generate(
                query, system=system, max_tokens=1024,
            )

            # Remove the "Thinking..." line and write the answer
            log.lines.pop()
            log.write(f"[bold]Bio-Search:[/bold] {answer}\n")

        except Exception as exc:
            log.write(f"[bold red]LLM error: {exc}[/bold red]")

    # -- Inline rendering helpers ------------------------------------------

    def _render_results_table(self, results) -> None:
        """Render association results as an inline Rich table."""
        log = self._log()

        table = RichTable(
            title="Results",
            border_style="dim",
            expand=False,
        )
        table.add_column("#", style="dim", no_wrap=True)
        table.add_column("Exposure", style="bold", no_wrap=True)
        table.add_column("Beta", justify="right")
        table.add_column("SE", justify="right")
        table.add_column("P-value", justify="right")
        table.add_column("FDR P", justify="right")
        table.add_column("N", justify="right")
        table.add_column("Sig", justify="center")

        for i, r in enumerate(results[:20], 1):
            fdr = f"{r.fdr_p:.2e}" if r.fdr_p is not None else "--"
            if r.fdr_p is not None:
                if r.fdr_p < 0.001:
                    sig = "***"
                elif r.fdr_p < 0.01:
                    sig = "**"
                elif r.fdr_p < 0.05:
                    sig = "*"
                else:
                    sig = ""
            else:
                sig = ""
            table.add_row(
                str(i),
                r.exposure,
                f"{r.beta:.4f}",
                f"{r.se:.4f}",
                f"{r.p_value:.2e}",
                fdr,
                str(r.n),
                sig,
            )

        log.write(table)

        if len(results) > 20:
            log.write(
                f"[dim]Showing top 20 of {len(results)} results.[/dim]"
            )

    def _render_manhattan(self, results) -> None:
        """Render a Manhattan plot inline using plotext."""
        log = self._log()
        if not results:
            return

        try:
            plt.clear_figure()
            plt.title("Manhattan Plot")
            plt.xlabel("Exposure Index")
            plt.ylabel("-log10(p)")
            plt.plot_size(60, 15)

            p_values = [r.p_value for r in results]
            log_p = [
                -math.log10(p) if p > 0 else 20.0 for p in p_values
            ]
            x = list(range(len(log_p)))

            plt.scatter(x, log_p)

            if len(results) > 0:
                bonferroni = 0.05 / len(results)
                sig_line = (
                    -math.log10(bonferroni) if bonferroni > 0 else 20.0
                )
                plt.hline(sig_line, color="red")

            chart_str = plt.build()
            log.write(chart_str)
        except Exception:
            log.write("[dim]Could not render Manhattan plot.[/dim]")

    def _render_forest(self, results) -> None:
        """Render a forest plot inline using plotext."""
        log = self._log()
        if not results:
            return

        try:
            subset = results[:20]

            plt.clear_figure()
            plt.title("Forest Plot")
            plt.xlabel("Effect Size (Beta)")
            plt.plot_size(60, max(10, len(subset) + 5))

            names = [r.exposure[:20] for r in subset]
            betas = [r.beta for r in subset]
            y_pos = list(range(len(names)))

            plt.scatter(betas, y_pos)

            for i, r in enumerate(subset):
                if r.ci:
                    plt.plot([r.ci.lower, r.ci.upper], [i, i], color="blue")

            plt.yticks(y_pos, names)
            plt.vline(0, color="red")

            chart_str = plt.build()
            log.write(chart_str)
        except Exception:
            log.write("[dim]Could not render forest plot.[/dim]")

    # -- Keyboard action handlers ------------------------------------------

    def action_browse(self) -> None:
        """Pre-fill the command bar with /browse."""
        cmd_bar = self.query_one("#command-bar", CommandInput)
        cmd_bar.value = "/browse "
        cmd_bar.focus()

    def action_start_ewas(self) -> None:
        """Pre-fill the command bar with /ewas."""
        cmd_bar = self.query_one("#command-bar", CommandInput)
        cmd_bar.value = "/ewas "
        cmd_bar.focus()

    def action_start_guided(self) -> None:
        """Pre-fill the command bar with /guided."""
        cmd_bar = self.query_one("#command-bar", CommandInput)
        cmd_bar.value = "/guided "
        cmd_bar.focus()

    def action_export(self) -> None:
        """Pre-fill the command bar with /export."""
        cmd_bar = self.query_one("#command-bar", CommandInput)
        cmd_bar.value = "/export "
        cmd_bar.focus()

    def action_show_help(self) -> None:
        """Print help to the chat log."""
        log = self._log()
        self._print_help(log)

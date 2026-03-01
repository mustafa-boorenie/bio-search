"""Dual-mode command input widget.

Supports two modes:

1. **Slash commands** -- structured actions like ``/ewas LBXGLU``,
   ``/download 2017-2018 DEMO_J``, ``/help``, etc.
2. **Natural language** -- free-form text that gets forwarded to the
   LLM agent (requires an OpenAI API key).

The widget posts either a ``CommandSubmitted`` or ``NLQuerySubmitted``
message depending on whether the input starts with ``/``.
"""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Input


class CommandInput(Input):
    """Text input that distinguishes /commands from natural-language queries.

    Messages
    --------
    CommandSubmitted
        Posted when the user presses Enter on a ``/command`` string.
    NLQuerySubmitted
        Posted when the user presses Enter on plain text (no ``/`` prefix).
    """

    COMMANDS: dict[str, str] = {
        "/browse": "Browse catalog: /browse [CYCLE] [TABLE]",
        "/download": "Download table: /download <CYCLE> <TABLE>",
        "/load": "Load cached tables: /load <TABLE_KEY> [TABLE_KEY ...]",
        "/ewas": "Run EWAS scan: /ewas <OUTCOME_VAR>",
        "/guided": "Guided analysis: /guided <EXPOSURE> <OUTCOME>",
        "/info": "Variable info: /info <VAR_NAME>",
        "/search": "Search variables: /search <query>",
        "/export": "Export results: /export <csv|json|report|figures>",
        "/clear": "Clear chat",
        "/help": "Show available commands",
        "/quit": "Exit application",
    }

    # -- Messages ----------------------------------------------------------

    class CommandSubmitted(Message):
        """A slash command was submitted."""

        def __init__(self, command: str, args: list[str]) -> None:
            super().__init__()
            self.command = command
            self.args = args

    class NLQuerySubmitted(Message):
        """A natural-language query was submitted."""

        def __init__(self, query: str) -> None:
            super().__init__()
            self.query = query

    # -- Construction ------------------------------------------------------

    def __init__(self, **kwargs) -> None:
        super().__init__(
            placeholder="> Type /command or ask a question...",
            **kwargs,
        )

    # -- Action overrides --------------------------------------------------

    async def action_submit(self) -> None:
        """Parse and dispatch the current input value."""
        value = self.value.strip()
        if not value:
            return

        if value.startswith("/"):
            parts = value.split()
            cmd = parts[0].lower()
            args = parts[1:]
            self.post_message(self.CommandSubmitted(cmd, args))
        else:
            self.post_message(self.NLQuerySubmitted(value))

        self.value = ""

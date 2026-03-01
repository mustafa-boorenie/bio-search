"""Entry point for the Bio-Search TUI.

Run with any of::

    python -m bio_search
    bio-search           # if installed via pip/pipx
"""

from __future__ import annotations


def main() -> None:
    """Launch the Bio-Search Textual application."""
    from bio_search.app import BioSearchApp

    app = BioSearchApp()
    app.run()


if __name__ == "__main__":
    main()

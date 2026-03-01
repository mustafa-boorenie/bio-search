"""EWAS progress indicator widget.

Shows a labelled progress bar and a status line that updates with the
name of the variable currently being tested.  Designed to sit inside
the workspace panel and give visual feedback during long-running
environment-wide association scans.
"""

from __future__ import annotations

from textual.containers import Vertical
from textual.widgets import ProgressBar, Static


class EWASProgress(Vertical):
    """Progress bar with status text for EWAS scans.

    Call ``update_progress(current, total, current_var)`` from the
    analysis callback, and ``reset()`` when the scan finishes or is
    cancelled.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._total = 0
        self._current = 0
        self._current_var = ""

    def compose(self):
        """Build the internal widget tree."""
        yield Static("EWAS Progress", classes="panel-title")
        yield ProgressBar(total=100, show_eta=True, id="ewas-progress-bar")
        yield Static("", id="ewas-status")

    def update_progress(
        self, current: int, total: int, current_var: str = ""
    ) -> None:
        """Update the bar position and status label.

        Parameters
        ----------
        current:
            Number of tests completed so far.
        total:
            Total number of tests to run.
        current_var:
            Name of the variable currently being tested.
        """
        self._current = current
        self._total = total
        self._current_var = current_var

        bar = self.query_one("#ewas-progress-bar", ProgressBar)
        bar.update(total=total, progress=current)

        status = self.query_one("#ewas-status", Static)
        pct = (current / total * 100) if total > 0 else 0
        status.update(
            f"Testing {current}/{total} ({pct:.0f}%): {current_var}"
        )

    def reset(self) -> None:
        """Reset the progress bar to its initial state."""
        self._current = 0
        self._total = 0
        self._current_var = ""

        bar = self.query_one("#ewas-progress-bar", ProgressBar)
        bar.update(total=100, progress=0)

        status = self.query_one("#ewas-status", Static)
        status.update("")

"""Sortable results table for association findings.

Displays EWAS or guided-analysis results in a Textual DataTable with
columns for exposure name, beta coefficient, standard error, p-value,
FDR-corrected p-value, sample size, model type, and a significance
flag.

Selecting a row posts a ``ResultSelected`` message so the main screen
can update the context panel or chart.
"""

from __future__ import annotations

from textual.message import Message
from textual.widgets import DataTable

from bio_search.models.analysis import AssociationResult


class ResultsTable(DataTable):
    """DataTable specialised for ``AssociationResult`` rows.

    Messages
    --------
    ResultSelected
        Posted when the user highlights a result row.
    """

    class ResultSelected(Message):
        """A result row was selected in the table."""

        def __init__(self, row_index: int, result: AssociationResult) -> None:
            super().__init__()
            self.row_index = row_index
            self.result = result

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._results: list[AssociationResult] = []

    # -- Column setup ------------------------------------------------------

    def setup_columns(self) -> None:
        """Add the standard association-result column headers."""
        self.add_columns(
            "Exposure",
            "Beta",
            "SE",
            "P-value",
            "FDR P",
            "N",
            "Model",
            "Sig",
        )

    # -- Data loading ------------------------------------------------------

    def load_results(self, results: list[AssociationResult]) -> None:
        """Clear the table and populate it with *results*.

        Results are displayed in the order they are provided.  The
        caller is responsible for sorting (e.g. by p-value) before
        passing the list.

        Parameters
        ----------
        results:
            Association results to display.
        """
        self._results = list(results)
        self.clear(columns=True)
        self.setup_columns()

        for r in self._results:
            fdr = r.fdr_p if r.fdr_p is not None else 1.0
            if fdr < 0.001:
                sig = "***"
            elif fdr < 0.01:
                sig = "**"
            elif fdr < 0.05:
                sig = "*"
            else:
                sig = ""

            self.add_row(
                r.exposure,
                f"{r.beta:.4f}",
                f"{r.se:.4f}",
                f"{r.p_value:.2e}",
                f"{r.fdr_p:.2e}" if r.fdr_p is not None else "--",
                str(r.n),
                r.model_type,
                sig,
            )

    # -- Selection handling ------------------------------------------------

    def on_data_table_row_selected(
        self, event: DataTable.RowSelected
    ) -> None:
        """Forward the selected row as a typed message."""
        if not self._results:
            return

        row_keys = list(self.rows.keys())
        if event.row_key in row_keys:
            idx = row_keys.index(event.row_key)
            if idx < len(self._results):
                self.post_message(
                    self.ResultSelected(idx, self._results[idx])
                )

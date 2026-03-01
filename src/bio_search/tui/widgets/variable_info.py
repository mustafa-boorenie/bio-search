"""Variable detail panel widget.

Displays a Rich table with metadata for the currently selected NHANES
variable: name, label, type classification, parent table, and (when
available) the number of distinct non-null values observed.
"""

from __future__ import annotations

from rich.table import Table as RichTable
from textual.widgets import Static

from bio_search.models.nhanes import NHANESVariable


class VariableInfo(Static):
    """Read-only panel that shows metadata for one NHANES variable.

    Call ``show_variable(var)`` to populate the panel, or
    ``clear_info()`` to reset it to the placeholder text.
    """

    _PLACEHOLDER = "Select a variable to see details"

    def __init__(self, **kwargs) -> None:
        super().__init__(self._PLACEHOLDER, **kwargs)

    def show_variable(self, var: NHANESVariable) -> None:
        """Render a Rich table with the variable's metadata.

        Parameters
        ----------
        var:
            The ``NHANESVariable`` whose details should be displayed.
        """
        table = RichTable(
            title=var.name,
            show_header=False,
            expand=True,
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
            # Show up to 8 coded values to keep the panel compact
            items = list(var.value_labels.items())[:8]
            labels_str = ", ".join(f"{k}={v}" for k, v in items)
            if len(var.value_labels) > 8:
                labels_str += f" ... ({len(var.value_labels)} total)"
            table.add_row("Value labels", labels_str)

        self.update(table)

    def clear_info(self) -> None:
        """Reset the panel to the placeholder message."""
        self.update(self._PLACEHOLDER)

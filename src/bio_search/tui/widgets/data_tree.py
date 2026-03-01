"""NHANES data hierarchy browser widget.

Renders the NHANES catalog as a navigable tree:

    Cycle
      Component (demographics, laboratory, ...)
        Table (DEMO_J, GLU_J, ...)
          Variable (LBXGLU, RIAGENDR, ...)

Selecting a table or variable node posts a message that the main screen
can handle to load data, display metadata, or pre-fill commands.
"""

from __future__ import annotations

from textual.message import Message
from textual.widgets import Tree

from bio_search.data.catalog import NHANESCatalog


class DataTree(Tree[dict]):
    """Hierarchical NHANES data browser built from the catalog.

    Messages
    --------
    TableSelected
        Posted when a user selects a table leaf node.
    VariableSelected
        Posted when a user selects a variable leaf node.
    """

    # -- Messages ----------------------------------------------------------

    class TableSelected(Message):
        """A table node was selected in the data tree."""

        def __init__(self, cycle: str, table_name: str) -> None:
            super().__init__()
            self.cycle = cycle
            self.table_name = table_name

    class VariableSelected(Message):
        """A variable node was selected in the data tree."""

        def __init__(
            self, variable_name: str, table_name: str, cycle: str
        ) -> None:
            super().__init__()
            self.variable_name = variable_name
            self.table_name = table_name
            self.cycle = cycle

    # -- Construction ------------------------------------------------------

    def __init__(self, catalog: NHANESCatalog, **kwargs) -> None:
        super().__init__("NHANES Data", **kwargs)
        self.catalog = catalog

    def on_mount(self) -> None:
        """Build the tree once the widget is mounted."""
        self._build_tree()

    # -- Tree building -----------------------------------------------------

    def _build_tree(self) -> None:
        """Populate the tree from the hardcoded catalog.

        Structure: Cycle -> Component -> Table (-> Variables if available).
        """
        for cycle in self.catalog.get_cycles():
            cycle_node = self.root.add(
                f"[bold]{cycle}[/bold]",
                expand=False,
            )

            tables = self.catalog.get_tables(cycle)

            # Group tables by their DataComponent
            by_component: dict[str, list] = {}
            for table in tables:
                comp_label = table.component.value.title()
                by_component.setdefault(comp_label, []).append(table)

            for comp_label, comp_tables in sorted(by_component.items()):
                comp_node = cycle_node.add(
                    f"[dim]{comp_label}[/dim]",
                    expand=False,
                )
                for table in comp_tables:
                    table_data = {
                        "type": "table",
                        "cycle": cycle,
                        "table": table.name,
                    }
                    table_node = comp_node.add(
                        f"{table.name} -- {table.label}",
                        data=table_data,
                        expand=False,
                    )

                    # Add variable children if the catalog has them
                    for var in table.variables:
                        var_data = {
                            "type": "variable",
                            "cycle": cycle,
                            "table": table.name,
                            "variable": var.name,
                        }
                        table_node.add_leaf(
                            f"  {var.name}: {var.label}",
                            data=var_data,
                        )

    # -- Event handling ----------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Dispatch table/variable selection messages."""
        node_data = event.node.data
        if not isinstance(node_data, dict):
            return

        node_type = node_data.get("type")
        if node_type == "table":
            self.post_message(
                self.TableSelected(
                    cycle=node_data["cycle"],
                    table_name=node_data["table"],
                )
            )
        elif node_type == "variable":
            self.post_message(
                self.VariableSelected(
                    variable_name=node_data["variable"],
                    table_name=node_data["table"],
                    cycle=node_data["cycle"],
                )
            )

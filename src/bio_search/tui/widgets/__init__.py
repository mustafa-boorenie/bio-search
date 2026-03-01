"""TUI widgets for the Bio-Search NHANES application.

Re-exports every widget so callers can do::

    from bio_search.tui.widgets import DataTree, VariableInfo, ...
"""

from bio_search.tui.widgets.chart_widget import ChartWidget
from bio_search.tui.widgets.command_input import CommandInput
from bio_search.tui.widgets.data_tree import DataTree
from bio_search.tui.widgets.progress import EWASProgress
from bio_search.tui.widgets.results_table import ResultsTable
from bio_search.tui.widgets.variable_info import VariableInfo

__all__ = [
    "ChartWidget",
    "CommandInput",
    "DataTree",
    "EWASProgress",
    "ResultsTable",
    "VariableInfo",
]

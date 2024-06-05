from abc import ABC, abstractmethod
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

class DataframeProcessor(ABC):

    def __init__(self, **parameters):
        self.parameters = parameters
        self.console = Console()
        self.summary_table = Table(
            title=f"[royal_blue1][b]{self.__class__.__name__}[/b][/royal_blue1]",
            header_style="sky_blue1",
            border_style="sky_blue1"
        )
        self.summary_table.add_column("Parameters", style="magenta1", justify="left")
        self.summary_table.add_column("Before", style="magenta1", justify="left")
        self.summary_table.add_column("After", style="magenta1", justify="left")
        self.before_summary = ""
        self.after_summary = ""

    def display_summary(self):
        parameters_str = "\n".join(f"{key}: {value}" for key, value in self.parameters.items())
        self.summary_table.add_row(parameters_str, self.before_summary, self.after_summary)
        self.console.print(Panel(self.summary_table, border_style="royal_blue1"))

    @abstractmethod
    def process(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        pass
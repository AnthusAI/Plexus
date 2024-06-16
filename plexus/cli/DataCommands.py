import click
from .DataLakeCommands import lake_group

@click.group()
def data():
    """Profiling the data available for each score in the scorecard."""
    pass

@data.command()
def analyze():
    """
    Perform data profiling for all scores in the scorecard and generate an HTML report with the result and embedded artifacts.
    """
    click.echo("Profiling data...")

data.add_command(lake_group)
import click

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


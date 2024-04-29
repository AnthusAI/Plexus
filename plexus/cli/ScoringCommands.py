import click

@click.command()
def score():
    """Process scoring for one pending request, if there are any."""
    click.echo("Executing Command start from train")


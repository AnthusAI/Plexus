import click

@click.command()
def train():
    """Some classifiers use machine-learning models that require training."""
    click.echo("Executing Command start from train")


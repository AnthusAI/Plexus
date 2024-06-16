import click

@click.group(name='lake')
def lake_group():
    """Sub-group for data lake operations."""
    pass

@lake_group.command(name='setup-aws')
def setup_aws():
    """Set up AWS data lake environment."""
    click.echo("Deploying CDK Stack...")
    # Get the directory of the current script
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # Build the path to the CDK directory
    cdk_project_path = os.path.join(current_file_dir, "../../infrastructure")
    # Deploy the CDK stack
    subprocess.run(["cdk", "deploy"], cwd=cdk_project_path)
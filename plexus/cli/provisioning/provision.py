"""
Provision SageMaker endpoints for trained models.

This module provides CLI commands for provisioning, checking status, and deleting
SageMaker Serverless Inference endpoints.
"""

import click
from plexus.CustomLogging import logging
from plexus.cli.shared.console import console
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


@click.group()
def provision():
    """Provision and manage SageMaker endpoints for trained models."""
    pass


@provision.command(name='endpoint', help="Provision a SageMaker endpoint for a trained model.")
@click.option('--scorecard', '--scorecard-name', 'scorecard_name', required=True,
              help='The name of the scorecard.')
@click.option('--score', '--score-name', 'score_name', required=True,
              help='The name of the score to provision.')
@click.option('--yaml', is_flag=True,
              help='Load scorecard from local YAML files instead of the API.')
@click.option('--version',
              help='Specific score version ID to provision. If not provided with --yaml, reads from local YAML file.')
@click.option('--model-s3-uri',
              help='S3 URI to model.tar.gz. If not provided, uses local trained model.')
@click.option('--deployment-type', type=click.Choice(['serverless', 'realtime']),
              help='Deployment type: serverless or realtime. Defaults to YAML config or serverless.')
@click.option('--memory', type=int,
              help='Memory allocation in MB (1024-6144) for serverless endpoints. Defaults to YAML config or 4096.')
@click.option('--max-concurrency', type=int,
              help='Maximum concurrent invocations (1-200) for serverless endpoints. Defaults to YAML config or 10.')
@click.option('--instance-type',
              help='Instance type for real-time endpoints (e.g., ml.g5.xlarge). Defaults to YAML config.')
@click.option('--min-instances', type=int,
              help='Minimum instance count for real-time (0 for scale-to-zero). Defaults to YAML config or 0.')
@click.option('--max-instances', type=int,
              help='Maximum instance count for real-time. Defaults to YAML config or 1.')
@click.option('--scale-in-cooldown', type=int,
              help='Scale-in cooldown in seconds. Defaults to YAML config or 300.')
@click.option('--scale-out-cooldown', type=int,
              help='Scale-out cooldown in seconds. Defaults to YAML config or 60.')
@click.option('--target-invocations', type=float,
              help='Target invocations per instance. Defaults to YAML config or 1.0.')
@click.option('--pytorch-version', default='2.3.0',
              help='PyTorch inference container version.')
@click.option('--region',
              help='AWS region for infrastructure deployment (e.g., us-east-1). If not specified, uses default region.')
@click.option('--force', is_flag=True,
              help='Force re-provisioning even if endpoint already exists and is up-to-date.')
def provision_endpoint(scorecard_name, score_name, yaml, version, model_s3_uri, deployment_type,
                      memory, max_concurrency, instance_type, min_instances, max_instances,
                      scale_in_cooldown, scale_out_cooldown, target_invocations, pytorch_version, region, force):
    """
    Provision a SageMaker endpoint for a trained model.

    This command:
    1. Finds the trained model (local or S3)
    2. Packages it with inference code
    3. Deploys a SageMaker endpoint using CDK

    Examples:
        # Provision using local trained model
        plexus provision endpoint --scorecard "SelectQuote HCS" --score "Compliance Check"

        # Provision from specific S3 model
        plexus provision endpoint --scorecard "SelectQuote HCS" --score "Compliance Check" \\
            --model-s3-uri s3://bucket/path/to/model.tar.gz

        # Custom resources
        plexus provision endpoint --scorecard "SelectQuote HCS" --score "Compliance Check" \\
            --memory 8192 --max-concurrency 20
    """
    from plexus.cli.provisioning.provisioning_dispatcher import ProvisioningDispatcher

    logging.info(f"Provisioning endpoint for [magenta1][b]{scorecard_name}[/b][/magenta1] / [cyan1][b]{score_name}[/b][/cyan1]")

    try:
        # Use ProvisioningDispatcher (parallel to TrainingDispatcher)
        dispatcher = ProvisioningDispatcher(
            scorecard_name=scorecard_name,
            score_name=score_name,
            yaml=yaml,
            version=version,
            model_s3_uri=model_s3_uri,
            deployment_type=deployment_type,
            memory_mb=memory,
            max_concurrency=max_concurrency,
            instance_type=instance_type,
            min_instances=min_instances,
            max_instances=max_instances,
            scale_in_cooldown=scale_in_cooldown,
            scale_out_cooldown=scale_out_cooldown,
            target_invocations=target_invocations,
            pytorch_version=pytorch_version,
            region=region,
            force=force
        )

        result = dispatcher.dispatch()

        if result.success:
            if result.endpoint_name:
                # Display provisioning success
                console.print(Panel(
                    f"[green]✓ Endpoint provisioned successfully![/green]\n\n"
                    f"[bold]Endpoint:[/bold] {result.endpoint_name}\n"
                    f"[bold]Status:[/bold] {result.status}\n"
                    f"[bold]Model:[/bold] {result.model_s3_uri}",
                    title="Provisioning Complete",
                    border_style="green"
                ))

                # Display test results
                if result.test_result:
                    test_result = result.test_result
                    if test_result['success']:
                        latency_info = f" ({test_result.get('latency_ms', 0):.2f}ms)" if 'latency_ms' in test_result else ""
                        console.print(Panel(
                            f"[green]✓ Endpoint test passed![/green]\n\n"
                            f"{test_result['message']}{latency_info}",
                            title="Endpoint Test",
                            border_style="green"
                        ))
                    else:
                        console.print(Panel(
                            f"[yellow]⚠ Endpoint test had issues[/yellow]\n\n"
                            f"{test_result['message']}",
                            title="Endpoint Test",
                            border_style="yellow"
                        ))
            else:
                # Score doesn't support provisioning
                console.print(Panel(
                    f"[yellow]Score '{score_name}' does not support endpoint provisioning[/yellow]\n\n"
                    f"{result.message}",
                    title="Provisioning Not Supported",
                    border_style="yellow"
                ))
        else:
            console.print(Panel(
                f"[red]✗ Provisioning failed[/red]\n\n"
                f"{result.error}",
                title="Provisioning Failed",
                border_style="red"
            ))

    except Exception as e:
        logging.error(f"Provisioning failed: {str(e)}", exc_info=True)
        console.print(Panel(
            f"[red]✗ Provisioning failed[/red]\n\n{str(e)}",
            title="Error",
            border_style="red"
        ))


@provision.command(name='status', help="Check the status of a provisioned endpoint.")
@click.option('--scorecard', '--scorecard-name', 'scorecard_name', required=True,
              help='The name of the scorecard.')
@click.option('--score', '--score-name', 'score_name', required=True,
              help='The name of the score.')
@click.option('--yaml', is_flag=True,
              help='Load scorecard from local YAML files instead of the API.')
@click.option('--deployment-type', type=click.Choice(['serverless', 'realtime']), default='serverless',
              help='Deployment type to check.')
def status(scorecard_name, score_name, yaml, deployment_type):
    """
    Check the status of a provisioned endpoint.

    Displays endpoint status, model URI, creation time, and other details.

    Examples:
        plexus provision status --scorecard "SelectQuote HCS" --score "Compliance Check"
    """
    from plexus.cli.provisioning.operations import get_endpoint_status_operation

    logging.info(f"Checking endpoint status for {scorecard_name} / {score_name}")

    try:
        status_info = get_endpoint_status_operation(
            scorecard_name=scorecard_name,
            score_name=score_name,
            use_yaml=yaml,
            deployment_type=deployment_type
        )

        if status_info:
            table = Table(title="Endpoint Status", show_header=True)
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="white")

            table.add_row("Endpoint Name", status_info['endpoint_name'])
            table.add_row("Status", status_info['status'])
            table.add_row("Model S3 URI", status_info['model_s3_uri'])

            if status_info.get('creation_time'):
                table.add_row("Created", str(status_info['creation_time']))
            if status_info.get('last_modified_time'):
                table.add_row("Last Modified", str(status_info['last_modified_time']))

            console.print(table)
        else:
            console.print(Panel(
                f"[yellow]No endpoint found for {scorecard_name} / {score_name}[/yellow]",
                title="Not Found",
                border_style="yellow"
            ))

    except Exception as e:
        logging.error(f"Failed to get status: {str(e)}", exc_info=True)
        console.print(Panel(
            f"[red]Error getting status:[/red] {str(e)}",
            title="Error",
            border_style="red"
        ))


@provision.command(name='delete', help="Delete a provisioned endpoint.")
@click.option('--scorecard', '--scorecard-name', 'scorecard_name', required=True,
              help='The name of the scorecard.')
@click.option('--score', '--score-name', 'score_name', required=True,
              help='The name of the score.')
@click.option('--yaml', is_flag=True,
              help='Load scorecard from local YAML files instead of the API.')
@click.option('--deployment-type', type=click.Choice(['serverless', 'realtime']), default='serverless',
              help='Deployment type to delete.')
@click.option('--confirm', is_flag=True,
              help='Skip confirmation prompt.')
def delete(scorecard_name, score_name, yaml, deployment_type, confirm):
    """
    Delete a provisioned endpoint.

    This removes the SageMaker endpoint, endpoint configuration, and model resources.

    Examples:
        plexus provision delete --scorecard "SelectQuote HCS" --score "Compliance Check"
    """
    from plexus.cli.provisioning.operations import delete_endpoint_operation

    if not confirm:
        if not click.confirm(
            f"Delete endpoint for {scorecard_name} / {score_name}?",
            default=False
        ):
            console.print("[yellow]Deletion cancelled[/yellow]")
            return

    logging.info(f"Deleting endpoint for {scorecard_name} / {score_name}")

    try:
        result = delete_endpoint_operation(
            scorecard_name=scorecard_name,
            score_name=score_name,
            use_yaml=yaml,
            deployment_type=deployment_type
        )

        if result['success']:
            console.print(Panel(
                f"[green]✓ Endpoint deleted successfully[/green]\n\n"
                f"Endpoint: {result['endpoint_name']}",
                title="Deletion Complete",
                border_style="green"
            ))
        else:
            console.print(Panel(
                f"[red]✗ Deletion failed[/red]\n\n"
                f"{result.get('error', 'Unknown error')}",
                title="Deletion Failed",
                border_style="red"
            ))

    except Exception as e:
        logging.error(f"Deletion failed: {str(e)}", exc_info=True)
        console.print(Panel(
            f"[red]Error:[/red] {str(e)}",
            title="Error",
            border_style="red"
        ))


if __name__ == '__main__':
    provision()

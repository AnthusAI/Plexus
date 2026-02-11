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


@click.command()
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
def provision(scorecard_name, score_name, yaml, version, model_s3_uri, deployment_type,
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
        plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check"

        # Provision from specific S3 model
        plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check" \\
            --model-s3-uri s3://bucket/path/to/model.tar.gz

        # Custom resources
        plexus provision --scorecard "SelectQuote HCS" --score "Compliance Check" \\
            --memory 8192 --max-concurrency 20
    """
    from plexus.cli.provisioning.provisioning_dispatcher import ProvisioningDispatcher
    import os

    # Validate --yaml flag is not used in production
    environment = os.getenv('PLEXUS_ENVIRONMENT', os.getenv('environment', 'development'))
    if yaml and environment == 'production':
        console.print(Panel(
            "[red]✗ Error:[/red] The --yaml flag cannot be used in production environment.\n\n"
            "Production deployments must use the API to ensure proper version control and auditing.",
            title="Invalid Option",
            border_style="red"
        ))
        return

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
                    # Handle warning case (test was skipped)
                    if 'warning' in test_result:
                        console.print(Panel(
                            f"[yellow]⚠ Endpoint test skipped[/yellow]\n\n"
                            f"{test_result['warning']}",
                            title="Endpoint Test",
                            border_style="yellow"
                        ))
                    elif test_result.get('success'):
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
                            f"{test_result.get('message', 'Unknown issue')}",
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



if __name__ == '__main__':
    provision()

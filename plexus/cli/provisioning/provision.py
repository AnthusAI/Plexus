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
@click.option('--latest', is_flag=True,
              help='Use the most recent score version (overrides --version).')
@click.option('--select-version', is_flag=True,
              help='Interactively select a recent score version (API mode only).')
@click.option('--version-limit', type=int, default=10,
              help='Number of recent versions to show when using --select-version.')
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
def provision(scorecard_name, score_name, yaml, version, latest, select_version, version_limit, model_s3_uri, deployment_type,
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

    if yaml and (latest or select_version):
        console.print(Panel(
            "[red]✗ Error:[/red] --latest/--select-version cannot be used with --yaml.\n\n"
            "YAML mode only uses local configurations.",
            title="Invalid Option",
            border_style="red"
        ))
        return

    if version and (latest or select_version):
        console.print(Panel(
            "[red]✗ Error:[/red] Cannot use --version with --latest or --select-version.",
            title="Invalid Option",
            border_style="red"
        ))
        return

    if latest and select_version:
        console.print(Panel(
            "[red]✗ Error:[/red] Cannot use --latest with --select-version.",
            title="Invalid Option",
            border_style="red"
        ))
        return

    if select_version and not Console().is_terminal:
        console.print(Panel(
            "[red]✗ Error:[/red] --select-version requires an interactive terminal.\n\n"
            "Use --version instead.",
            title="Invalid Option",
            border_style="red"
        ))
        return

    if (latest or select_version) and not yaml:
        # Resolve score ID for version selection
        from plexus.cli.evaluation.evaluations import load_scorecard_from_api, get_latest_score_version
        from plexus.cli.shared.client_utils import create_client

        scorecard_class = load_scorecard_from_api(
            scorecard_identifier=scorecard_name,
            score_names=[score_name]
        )

        score_config = None
        for cfg in scorecard_class.scores:
            if isinstance(cfg, dict):
                if (cfg.get('name') == score_name or
                    cfg.get('key') == score_name or
                    str(cfg.get('id')) == str(score_name) or
                    cfg.get('externalId') == score_name or
                    cfg.get('originalExternalId') == score_name):
                    score_config = cfg
                    break

        if not score_config:
            console.print(Panel(
                f"[red]✗ Error:[/red] Score '{score_name}' not found in scorecard.",
                title="Provisioning Failed",
                border_style="red"
            ))
            return

        score_id = score_config.get('id')
        if not score_id:
            console.print(Panel(
                "[red]✗ Error:[/red] Score ID not found; cannot select a score version.",
                title="Provisioning Failed",
                border_style="red"
            ))
            return

        client = create_client()

        if latest:
            version = get_latest_score_version(client, score_id)
            if not version:
                console.print(Panel(
                    "[red]✗ Error:[/red] No score versions found for this score.",
                    title="Provisioning Failed",
                    border_style="red"
                ))
                return

        if select_version:
            query = """
            query ListScoreVersionByScoreIdAndCreatedAt($scoreId: String!, $sortDirection: ModelSortDirection, $limit: Int) {
                listScoreVersionByScoreIdAndCreatedAt(scoreId: $scoreId, sortDirection: $sortDirection, limit: $limit) {
                    items {
                        id
                        createdAt
                        note
                    }
                }
            }
            """

            result = client.execute(query, {
                'scoreId': score_id,
                'sortDirection': 'DESC',
                'limit': version_limit
            })

            items = result.get('listScoreVersionByScoreIdAndCreatedAt', {}).get('items', [])
            if not items:
                console.print(Panel(
                    "[red]✗ Error:[/red] No score versions found for this score.",
                    title="Provisioning Failed",
                    border_style="red"
                ))
                return

            table = Table(title="Select Score Version")
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Version ID", style="magenta")
            table.add_column("Created", style="green")
            table.add_column("Note", style="white")

            for idx, item in enumerate(items, start=1):
                note = (item.get('note') or '').replace('\n', ' ').strip()
                if len(note) > 80:
                    note = note[:77] + "..."
                table.add_row(str(idx), item.get('id', ''), item.get('createdAt', ''), note)

            console.print(table)
            selection = click.prompt("Select a version", type=int, default=1)
            if selection < 1 or selection > len(items):
                console.print(Panel(
                    "[red]✗ Error:[/red] Invalid selection.",
                    title="Provisioning Failed",
                    border_style="red"
                ))
                return

            version = items[selection - 1].get('id')

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

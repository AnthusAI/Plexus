"""
Procedure CLI Commands - Command-line interface for procedure management.

Provides commands for:
- Creating new experiments
- Listing experiments  
- Showing procedure details
- Updating procedure configurations
- Deleting experiments
- Managing procedure execution

Uses the shared ProcedureService for consistent behavior.
"""

import click
import json
import yaml
import time
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
from datetime import datetime

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console
from .service import ProcedureService

@click.group()
def procedure():
    """Manage procedures for AI system optimization."""
    pass

@procedure.command()
@click.option('--account', '-a', help='Account identifier (key, name, or ID)')
@click.option('--scorecard', '-s', required=True, help='Scorecard identifier (key, name, or ID)')
@click.option('--score', '-c', required=True, help='Score identifier (key, name, or ID)')
@click.option('--yaml', '-y', help='YAML configuration file path')
@click.option('--featured', is_flag=True, help='Mark procedure as featured')
@click.option('--no-root-node', is_flag=True, help='Create procedure without a root node')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def create(account: Optional[str], scorecard: str, score: str, yaml: Optional[str], featured: bool, no_root_node: bool, output: str):
    """Create a new procedure.
    
    Creates an procedure associated with a specific scorecard and score.
    By default, creates a root node with a BeamSearch template. Use --no-root-node 
    to create an empty procedure without any nodes.
    
    Examples:
        plexus procedure create -s "Sales Scorecard" -c "DNC Requested"
        plexus procedure create -s sales-scorecard -c dnc-requested --yaml config.yaml
        plexus procedure create -a my-account -s scorecard-id -c score-id --featured
        plexus procedure create -s scorecard -c score --no-root-node
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    # Load YAML configuration if provided
    yaml_config = None
    if yaml:
        try:
            with open(yaml, 'r') as f:
                yaml_config = f.read()
        except Exception as e:
            console.print(f"[red]Error reading YAML file {yaml}: {str(e)}[/red]")
            return
    
    # Use default account if not specified
    if not account:
        import os
        account = os.environ.get('PLEXUS_ACCOUNT_KEY')
        if not account:
            raise ValueError("PLEXUS_ACCOUNT_KEY environment variable must be set")
    
    console.print(f"Creating procedure for scorecard '{scorecard}' and score '{score}'...")
    
    result = service.create_procedure(
        account_identifier=account,
        scorecard_identifier=scorecard,
        score_identifier=score,
        yaml_config=yaml_config,
        featured=featured,
        create_root_node=not no_root_node
    )
    
    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        return
    
    if output == 'json':
        data = {
            'procedure_id': result.procedure.id,
            'root_node_id': result.root_node.id,
            'initial_version_id': result.initial_version.id,
            'featured': result.procedure.featured,
            'created_at': result.procedure.createdAt.isoformat(),
            'scorecard_id': result.procedure.scorecardId,
            'score_id': result.procedure.scoreId
        }
        console.print(JSON.from_data(data))
    elif output == 'yaml':
        data = {
            'procedure_id': result.procedure.id,
            'root_node_id': result.root_node.id,
            'initial_version_id': result.initial_version.id,
            'featured': result.procedure.featured,
            'created_at': result.procedure.createdAt.isoformat(),
            'scorecard_id': result.procedure.scorecardId,
            'score_id': result.procedure.scoreId
        }
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        # Table format
        console.print(f"[green]✓ {result.message}[/green]")
        
        table = Table(title="Created Procedure")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Procedure ID", result.procedure.id)
        table.add_row("Root Node ID", result.root_node.id)
        table.add_row("Initial Version ID", result.initial_version.id)
        table.add_row("Featured", "Yes" if result.procedure.featured else "No")
        table.add_row("Created", result.procedure.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Scorecard ID", result.procedure.scorecardId or "N/A")
        table.add_row("Score ID", result.procedure.scoreId or "N/A")
        
        console.print(table)

@procedure.command()
@click.option('--account', '-a', help='Account identifier (key, name, or ID)')
@click.option('--scorecard', '-s', help='Filter by scorecard identifier')
@click.option('--limit', '-l', default=20, help='Maximum number of experiments to show')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def list(account: Optional[str], scorecard: Optional[str], limit: int, output: str):
    """List procedures.
    
    Shows experiments ordered by most recent first. Can be filtered by account
    and/or scorecard.
    
    Examples:
        plexus procedure list
        plexus procedure list -a my-account -l 10
        plexus procedure list -s "Sales Scorecard"
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    # Use default account if not specified
    if not account:
        import os
        account = os.environ.get('PLEXUS_ACCOUNT_KEY')
        if not account:
            raise ValueError("PLEXUS_ACCOUNT_KEY environment variable must be set")
    
    experiments = service.list_procedures(
        account_identifier=account,
        scorecard_identifier=scorecard,
        limit=limit
    )
    
    if not experiments:
        console.print("[yellow]No experiments found[/yellow]")
        return
    
    if output == 'json':
        data = []
        for exp in experiments:
            data.append({
                'id': exp.id,
                'featured': exp.featured,
                'created_at': exp.createdAt.isoformat(),
                'updated_at': exp.updatedAt.isoformat(),
                'account_id': exp.accountId,
                'scorecard_id': exp.scorecardId,
                'score_id': exp.scoreId,
                'root_node_id': exp.rootNodeId
            })
        console.print(JSON.from_data(data))
    elif output == 'yaml':
        data = []
        for exp in experiments:
            data.append({
                'id': exp.id,
                'featured': exp.featured,
                'created_at': exp.createdAt.isoformat(),
                'updated_at': exp.updatedAt.isoformat(),
                'account_id': exp.accountId,
                'scorecard_id': exp.scorecardId,
                'score_id': exp.scoreId,
                'root_node_id': exp.rootNodeId
            })
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        # Table format
        table = Table(title=f"Procedures ({len(experiments)} found)")
        table.add_column("ID", style="cyan", width=12)
        table.add_column("Featured", style="yellow", width=8)
        table.add_column("Created", style="green", width=16)
        table.add_column("Scorecard ID", style="blue", width=12)
        table.add_column("Score ID", style="magenta", width=12)
        table.add_column("Root Node", style="white", width=12)
        
        for exp in experiments:
            table.add_row(
                exp.id[:10] + "..." if len(exp.id) > 12 else exp.id,
                "★" if exp.featured else "",
                exp.createdAt.strftime("%Y-%m-%d %H:%M"),
                (exp.scorecardId[:10] + "...") if exp.scorecardId and len(exp.scorecardId) > 12 else (exp.scorecardId or "N/A"),
                (exp.scoreId[:10] + "...") if exp.scoreId and len(exp.scoreId) > 12 else (exp.scoreId or "N/A"),
                (exp.rootNodeId[:10] + "...") if exp.rootNodeId and len(exp.rootNodeId) > 12 else (exp.rootNodeId or "N/A")
            )
        
        console.print(table)

@procedure.command()
@click.argument('procedure_id')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
@click.option('--include-yaml', is_flag=True, help='Include YAML configuration in output')
def show(procedure_id: str, output: str, include_yaml: bool):
    """Show detailed information about an procedure.
    
    Displays comprehensive information including nodes, versions, and configuration.
    
    Examples:
        plexus procedure show abc123def456
        plexus procedure show abc123def456 --include-yaml
        plexus procedure show abc123def456 -o json
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    info = service.get_procedure_info(procedure_id)
    if not info:
        console.print(f"[red]Error: Procedure {procedure_id} not found[/red]")
        return
    
    # Get YAML if requested
    yaml_config = None
    if include_yaml:
        yaml_config = service.get_procedure_yaml(procedure_id)
    
    if output == 'json':
        data = {
            'procedure': {
                'id': info.procedure.id,
                'featured': info.procedure.featured,
                'created_at': info.procedure.createdAt.isoformat(),
                'updated_at': info.procedure.updatedAt.isoformat(),
                'account_id': info.procedure.accountId,
                'scorecard_id': info.procedure.scorecardId,
                'score_id': info.procedure.scoreId,
                'root_node_id': info.procedure.rootNodeId
            },
            'summary': {
                'node_count': info.node_count,
                'version_count': info.version_count,
                'scorecard_name': info.scorecard_name,
                'score_name': info.score_name
            }
        }
        if yaml_config:
            data['yaml_config'] = yaml_config
        console.print(JSON.from_data(data))
    elif output == 'yaml':
        data = {
            'procedure': {
                'id': info.procedure.id,
                'featured': info.procedure.featured,
                'created_at': info.procedure.createdAt.isoformat(),
                'updated_at': info.procedure.updatedAt.isoformat(),
                'account_id': info.procedure.accountId,
                'scorecard_id': info.procedure.scorecardId,
                'score_id': info.procedure.scoreId,
                'root_node_id': info.procedure.rootNodeId
            },
            'summary': {
                'node_count': info.node_count,
                'version_count': info.version_count,
                'scorecard_name': info.scorecard_name,
                'score_name': info.score_name
            }
        }
        if yaml_config:
            data['yaml_config'] = yaml_config
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        # Table format
        console.print(Panel(f"[bold cyan]Procedure Details[/bold cyan]", title="Procedure"))
        
        # Basic info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("ID", info.procedure.id)
        table.add_row("Featured", "★ Yes" if info.procedure.featured else "No")
        table.add_row("Created", info.procedure.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Updated", info.procedure.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Account ID", info.procedure.accountId)
        table.add_row("Root Node ID", info.procedure.rootNodeId or "N/A")
        
        if info.scorecard_name:
            table.add_row("Scorecard", f"{info.scorecard_name} ({info.procedure.scorecardId})")
        else:
            table.add_row("Scorecard ID", info.procedure.scorecardId or "N/A")
        
        if info.score_name:
            table.add_row("Score", f"{info.score_name} ({info.procedure.scoreId})")
        else:
            table.add_row("Score ID", info.procedure.scoreId or "N/A")
        
        console.print(table)
        console.print()
        
        # Summary stats
        stats_table = Table(title="Summary Statistics")
        stats_table.add_column("Metric", style="cyan")
        stats_table.add_column("Count", style="yellow")
        
        stats_table.add_row("Nodes", str(info.node_count))
        stats_table.add_row("Versions", str(info.version_count))
        
        console.print(stats_table)
        
        # Show YAML if requested
        if include_yaml and yaml_config:
            console.print()
            console.print(Panel(yaml_config, title="[bold cyan]YAML Configuration[/bold cyan]", expand=False))

@procedure.command()
@click.argument('procedure_id')
@click.option('--yaml', '-y', help='YAML configuration file path')
@click.option('--note', '-n', help='Note for this configuration version')
def update(procedure_id: str, yaml: Optional[str], note: Optional[str]):
    """Update a procedure's configuration.
    
    Creates a new version with the provided YAML configuration.
    
    Examples:
        plexus procedure update abc123def456 --yaml new-config.yaml
        plexus procedure update abc123def456 --yaml config.yaml --note "Improved exploration"
    """
    if not yaml:
        console.print("[red]Error: --yaml option is required[/red]")
        return
    
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    # Load YAML configuration
    try:
        with open(yaml, 'r') as f:
            yaml_config = f.read()
    except Exception as e:
        console.print(f"[red]Error reading YAML file {yaml}: {str(e)}[/red]")
        return
    
    console.print(f"Updating procedure {procedure_id}...")
    
    success, message = service.update_procedure_config(procedure_id, yaml_config, note)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]Error: {message}[/red]")

@procedure.command()
@click.argument('procedure_id')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def delete(procedure_id: str, confirm: bool):
    """Delete an procedure and all its data.
    
    This will permanently delete the procedure, all its nodes, and all versions.
    This action cannot be undone.
    
    Examples:
        plexus procedure delete abc123def456
        plexus procedure delete abc123def456 --confirm
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    # Get procedure info for confirmation
    info = service.get_procedure_info(procedure_id)
    if not info:
        console.print(f"[red]Error: Procedure {procedure_id} not found[/red]")
        return
    
    if not confirm:
        console.print(f"[yellow]WARNING: This will permanently delete procedure {procedure_id}[/yellow]")
        console.print(f"Procedure has {info.node_count} nodes and {info.version_count} versions")
        if not click.confirm("Are you sure you want to continue?"):
            console.print("Deletion cancelled")
            return
    
    console.print(f"Deleting procedure {procedure_id}...")
    
    success, message = service.delete_procedure(procedure_id)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]Error: {message}[/red]")

@procedure.command()
@click.argument('procedure_id')
@click.option('--output', '-o', help='Output file path (default: experiment-{id}.yaml)')
def pull(procedure_id: str, output: Optional[str]):
    """Pull the latest YAML configuration from an procedure.
    
    Saves the experiment's current YAML configuration to a file.
    
    Examples:
        plexus procedure pull abc123def456
        plexus procedure pull abc123def456 --output my-config.yaml
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ProcedureService(client)
    
    yaml_config = service.get_procedure_yaml(procedure_id)
    if not yaml_config:
        console.print(f"[red]Error: Could not get YAML configuration for procedure {procedure_id}[/red]")
        return
    
    if not output:
        output = f"experiment-{procedure_id[:8]}.yaml"
    
    try:
        with open(output, 'w') as f:
            f.write(yaml_config)
        console.print(f"[green]✓ Saved configuration to {output}[/green]")
    except Exception as e:
        console.print(f"[red]Error writing to {output}: {str(e)}[/red]")

@procedure.command()
@click.argument('procedure_id', required=False)
@click.option('--yaml', '-y', 'yaml_file', help='YAML file to run (creates procedure if needed)')
@click.option('--max-iterations', type=int, help='Maximum number of iterations')
@click.option('--timeout', type=int, help='Timeout in seconds')
@click.option('--async-mode', is_flag=True, help='Run procedure asynchronously')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without actual execution')
@click.option('--restart-from-root-node', is_flag=True, help='Delete all non-root graph nodes and restart from scratch')
@click.option('--openai-api-key', help='OpenAI API key for AI-powered experiments (or set OPENAI_API_KEY env var)')
@click.option('--set', '-s', 'set_params', multiple=True, help='Set procedure parameter as key=value (e.g., --set scorecard="AW - Confirmation")')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def run(procedure_id: Optional[str], yaml_file: Optional[str], max_iterations: Optional[int], timeout: Optional[int],
        async_mode: bool, dry_run: bool, restart_from_root_node: bool, openai_api_key: Optional[str], set_params: tuple, output: str):
    """Run a procedure - either by ID or directly from a YAML file.

    You can run a procedure in two ways:
    1. By ID: plexus procedure run <procedure-id>
    2. From YAML: plexus procedure run --yaml procedure.yaml

    Running from YAML is like executing a script - it creates the procedure
    (if needed) and immediately runs it.

    Examples:
        # Run from YAML file (recommended for Tactus procedures)
        plexus procedure run --yaml my_procedure.yaml
        plexus procedure run --yaml my_procedure.yaml --dry-run
        plexus procedure run -y procedure.yaml --max-iterations 50

        # Run by ID (for existing procedures)
        plexus procedure run abc123def456
        plexus procedure run abc123def456 --max-iterations 50 --timeout 300
        plexus procedure run abc123def456 --async-mode -o json
        plexus procedure run abc123def456 --restart-from-root-node

        # Pass parameters to a procedure
        plexus procedure run -y optimizer.yaml -s scorecard="My Scorecard" -s score="My Score" -s max_samples=100
    """
    # Validate arguments
    if not procedure_id and not yaml_file:
        console.print("[red]Error: Either provide a procedure ID or use --yaml flag[/red]")
        console.print("Examples:")
        console.print("  plexus procedure run --yaml procedure.yaml")
        console.print("  plexus procedure run <procedure-id>")
        return

    if procedure_id and yaml_file:
        console.print("[red]Error: Cannot specify both procedure ID and --yaml flag[/red]")
        console.print("Use one or the other:")
        console.print("  plexus procedure run --yaml procedure.yaml")
        console.print("  plexus procedure run <procedure-id>")
        return

    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    # If running from YAML, create the procedure first
    if yaml_file:
        console.print(f"[cyan]Running procedure from YAML: {yaml_file}[/cyan]")

        # Load YAML file
        try:
            with open(yaml_file, 'r') as f:
                yaml_config = f.read()
        except Exception as e:
            console.print(f"[red]Error reading YAML file {yaml_file}: {str(e)}[/red]")
            return

        # Create the procedure
        service = ProcedureService(client)

        # Use default account
        import os
        account = os.environ.get('PLEXUS_ACCOUNT_KEY')
        if not account:
            console.print("[red]Error: PLEXUS_ACCOUNT_KEY environment variable must be set[/red]")
            return

        # Check if this is a Tactus procedure
        import yaml as yaml_lib
        try:
            config = yaml_lib.safe_load(yaml_config)
            is_tactus = config.get('class') == 'Tactus'
        except:
            is_tactus = False
            config = {}

        # Build stage_configs from the YAML stages declaration
        stage_configs = None
        yaml_stages = config.get('stages', []) if isinstance(config, dict) else []
        if yaml_stages:
            from plexus.cli.shared.task_progress_tracker import StageConfig
            stage_configs = {
                stage.title(): StageConfig(order=i + 1, status_message=f"{stage.title()} stage")
                for i, stage in enumerate(yaml_stages)
            }

        # Extract scorecard/score identifiers so the procedure DB record can carry
        # the foreign-key association and show names in the UI.
        # Priority: --set params override YAML param value: fields.
        scorecard_identifier_for_create = None
        score_identifier_for_create = None
        # 1. Pull defaults from YAML param value: fields
        yaml_params = config.get('params', {}) if isinstance(config, dict) else {}
        for key, meta in yaml_params.items() if isinstance(yaml_params, dict) else []:
            if not isinstance(meta, dict):
                continue
            val = meta.get('value')
            if not val:
                continue
            if key in ('scorecard', 'scorecard_id'):
                scorecard_identifier_for_create = str(val)
            elif key in ('score', 'score_id'):
                score_identifier_for_create = str(val)
        # 2. --set params take precedence
        if set_params:
            for param in set_params:
                if '=' in param:
                    k, _, v = param.partition('=')
                    k = k.strip().strip('"').strip("'")
                    v = v.strip().strip('"').strip("'")
                    if k in ('scorecard', 'scorecard_id') and v:
                        scorecard_identifier_for_create = v
                    elif k in ('score', 'score_id') and v:
                        score_identifier_for_create = v

        console.print("Creating procedure from YAML...")
        result = service.create_procedure(
            account_identifier=account,
            scorecard_identifier=scorecard_identifier_for_create,
            score_identifier=score_identifier_for_create,
            yaml_config=yaml_config,
            featured=False,
            create_root_node=not is_tactus,  # Don't create root node for Tactus procedures
            stage_configs=stage_configs,
        )

        # If scorecard/score resolution failed, retry without them rather than aborting.
        if not result.success and (scorecard_identifier_for_create or score_identifier_for_create):
            console.print(f"[yellow]Warning: Could not resolve scorecard/score identifiers ({result.message}); creating procedure without association.[/yellow]")
            result = service.create_procedure(
                account_identifier=account,
                scorecard_identifier=None,
                score_identifier=None,
                yaml_config=yaml_config,
                featured=False,
                create_root_node=not is_tactus,
                stage_configs=stage_configs,
            )

        if not result.success:
            console.print(f"[red]Error creating procedure: {result.message}[/red]")
            return

        procedure_id = result.procedure.id
        console.print(f"[green]✓ Created procedure {procedure_id}[/green]")
        console.print()

    if restart_from_root_node:
        console.print(f"[yellow]⚠ Restarting from root node - deleting all existing hypothesis nodes...[/yellow]")

    console.print(f"Running procedure {procedure_id} with task tracking...")

    # Build options dictionary
    options = {}
    if max_iterations is not None:
        options['max_iterations'] = max_iterations
    if timeout is not None:
        options['timeout'] = timeout
    if async_mode:
        options['async_mode'] = async_mode
    if dry_run:
        options['dry_run'] = dry_run
    if restart_from_root_node:
        options['restart_from_root_node'] = restart_from_root_node

    # Add AI options
    if openai_api_key:
        options['openai_api_key'] = openai_api_key

    # Parse --set key=value params into context dict
    if set_params:
        param_context = {}
        for param in set_params:
            if '=' not in param:
                console.print(f"[red]Error: --set value must be key=value, got: {param}[/red]")
                return
            key, value = param.split('=', 1)
            # Try to parse numeric/boolean values
            if value.lower() == 'true':
                value = True
            elif value.lower() == 'false':
                value = False
            else:
                try:
                    value = int(value)
                except ValueError:
                    try:
                        value = float(value)
                    except ValueError:
                        pass  # Keep as string
            param_context[key.strip()] = value
        options['context'] = param_context
    
    # Get account ID for task tracking
    from plexus.cli.report.utils import resolve_account_id_for_command
    account_id = resolve_account_id_for_command(client, None)
    
    # Run the procedure with task tracking (async)
    import asyncio
    from plexus.cli.shared.experiment_runner import run_experiment_with_task_tracking
    
    result = asyncio.run(run_experiment_with_task_tracking(
        procedure_id=procedure_id,
        client=client,
        account_id=account_id,
        **options
    ))
    
    if result.get('status') == 'error':
        console.print(f"[red]Error: {result.get('error')}[/red]")
        return
    
    if output == 'json':
        console.print(JSON.from_data(result))
    elif output == 'yaml':
        console.print(yaml.dump(result, default_flow_style=False))
    else:
        # Table format
        status = result.get('status', 'unknown')
        status_color = {
            'completed': 'green',
            'running': 'yellow', 
            'initiated': 'blue',
            'error': 'red'
        }.get(status, 'white')
        
        console.print(f"[{status_color}]✓ {result.get('message', 'Procedure run completed')}[/{status_color}]")
        
        # Basic results table
        table = Table(title="Procedure Run Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Procedure ID", result.get('procedure_id', 'N/A'))
        table.add_row("Status", status.upper())
        
        details = result.get('details', {})
        if details:
            if details.get('experiment_name'):
                table.add_row("Procedure Name", details['experiment_name'])
            if details.get('scorecard_name'):
                table.add_row("Scorecard", details['scorecard_name'])
            if details.get('score_name'):
                table.add_row("Score", details['score_name'])
            if details.get('node_count'):
                table.add_row("Node Count", str(details['node_count']))
        
        # Show MCP tools information
        mcp_info = result.get('mcp_info', {})
        if mcp_info:
            tools_count = len(mcp_info.get('available_tools', []))
            table.add_row("MCP Tools", f"{tools_count} tools available")
            
            # Show options that were used
            experiment_options = details.get('options', {})
            if experiment_options:
                table.add_row("", "")  # Spacer
                for key, value in experiment_options.items():
                    table.add_row(f"Option: {key}", str(value))
        
        console.print(table)

@procedure.command('test-specs')
@click.argument('procedure_id', required=False)
@click.option('--yaml', '-y', 'yaml_file', help='Procedure YAML file path')
@click.option('--mode', type=click.Choice(['mock', 'integration']), default='mock', show_default=True, help='Specification execution mode')
@click.option('--scenario', help='Optional scenario name filter')
@click.option('--no-parallel', is_flag=True, help='Run scenarios sequentially')
@click.option('--workers', type=int, help='Max worker processes when running in parallel')
@click.option('--output', '-o', type=click.Choice(['table', 'json', 'yaml']), default='table', show_default=True, help='Output format')
def test_specs(
    procedure_id: Optional[str],
    yaml_file: Optional[str],
    mode: str,
    scenario: Optional[str],
    no_parallel: bool,
    workers: Optional[int],
    output: str
):
    """Run embedded Tactus Specification blocks from a procedure.

    Exactly one input source is required:
    1. Procedure record: `plexus procedure test-specs <procedure-id>`
    2. YAML file: `plexus procedure test-specs --yaml path/to/procedure.yaml`
    """
    if not procedure_id and not yaml_file:
        console.print("[red]Error: provide either a procedure ID or --yaml[/red]")
        return
    if procedure_id and yaml_file:
        console.print("[red]Error: cannot specify both procedure ID and --yaml[/red]")
        return
    if workers is not None and workers <= 0:
        console.print("[red]Error: --workers must be a positive integer[/red]")
        return

    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    service = ProcedureService(client)

    yaml_config = None
    if yaml_file:
        try:
            with open(yaml_file, 'r') as f:
                yaml_config = f.read()
        except Exception as e:
            console.print(f"[red]Error reading YAML file {yaml_file}: {str(e)}[/red]")
            return

    try:
        result = service.test_procedure_specs(
            procedure_id=procedure_id,
            yaml_config=yaml_config,
            mode=mode,
            scenario=scenario,
            parallel=not no_parallel,
            workers=workers
        )
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if output == 'json':
        console.print(JSON.from_data(result))
        return
    if output == 'yaml':
        console.print(yaml.dump(result, default_flow_style=False, sort_keys=False))
        return

    summary = result.get('summary', {})
    status_label = "PASS" if result.get('success') else "FAIL"
    status_color = "green" if result.get('success') else "red"
    console.print(
        f"[{status_color}]{status_label}[/{status_color}] "
        f"{summary.get('passed_scenarios', 0)}/{summary.get('total_scenarios', 0)} scenarios passed "
        f"(mode={result.get('mode')})"
    )

    table = Table(title="Procedure Spec Results")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Procedure ID", result.get('metadata', {}).get('procedure_id') or "N/A")
    table.add_row("Scenario Filter", result.get('metadata', {}).get('scenario_filter') or "N/A")
    table.add_row("Parallel", str(result.get('metadata', {}).get('parallel')))
    table.add_row("Workers", str(result.get('metadata', {}).get('workers') or "auto"))
    table.add_row("Passed", str(summary.get('passed_scenarios', 0)))
    table.add_row("Failed", str(summary.get('failed_scenarios', 0)))
    table.add_row("Duration (s)", str(summary.get('duration_seconds', 0)))
    console.print(table)

    if summary.get('failed_scenarios', 0) > 0:
        console.print("\n[red]Failed Step Messages:[/red]")
        for feature in result.get('features', []):
            for scenario_result in feature.get('scenarios', []):
                for message in scenario_result.get('failed_step_messages', []):
                    console.print(f"- {feature.get('name')} / {scenario_result.get('name')}: {message}")

@procedure.command()
@click.option('--output', '-o', help='Output file path (default: experiment-template.yaml)')
def template(output: Optional[str]):
    """Generate a template YAML configuration for procedures.

    DEPRECATED: Users should manage procedure templates via the dashboard or API.
    See example-procedure-prompts.yaml in the project root for reference.

    Examples:
        plexus procedure template
        plexus procedure template --output my-template.yaml
    """
    console.print("[yellow]⚠️  This command is deprecated.[/yellow]")
    console.print("\nProcedure templates should be managed via:")
    console.print("  1. Dashboard UI (create ProcedureTemplate)")
    console.print("  2. Store YAML directly in Procedure.code field")
    console.print("\nSee example-procedure-prompts.yaml for reference.")
    return


@procedure.command()
@click.argument('procedure_id')
def resume(procedure_id: str):
    """Resume a procedure that is waiting for human response.

    This command is idempotent - safe to call anytime. If the procedure is:
    - WAITING_FOR_HUMAN with a response: Continues execution
    - WAITING_FOR_HUMAN without a response: No-op (still waiting)
    - Already COMPLETE or ERROR: No-op
    - RUNNING: No-op

    Examples:
        plexus procedure resume proc-123abc
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.resume_service import resume_procedure

    console.print(f"Checking procedure {procedure_id}...")

    try:
        result = resume_procedure(client, procedure_id)

        if result['resumed']:
            console.print(f"[green]✓ Procedure resumed successfully[/green]")
            console.print(f"Status: {result.get('status', 'RUNNING')}")
            if result.get('message'):
                console.print(f"Message: {result['message']}")
        else:
            console.print(f"[yellow]• No action taken[/yellow]")
            console.print(f"Reason: {result.get('reason', 'Unknown')}")
            console.print(f"Status: {result.get('status', 'Unknown')}")

    except Exception as e:
        console.print(f"[red]Error resuming procedure: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@procedure.command()
def resume_all():
    """Resume all procedures that are waiting for human response.

    Scans all procedures with status WAITING_FOR_HUMAN and resumes those
    that have received responses. This is idempotent and safe to call repeatedly.

    Examples:
        plexus procedure resume-all
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.resume_service import resume_all_pending

    console.print("Scanning for procedures waiting for human response...")

    try:
        result = resume_all_pending(client)

        console.print(f"\n[green]✓ Scan complete[/green]")
        console.print(f"Found: {result['found']} procedures waiting")
        console.print(f"Resumed: {result['resumed']} procedures")

        if result['resumed'] > 0:
            console.print("\nResumed procedures:")
            for proc_id in result.get('resumed_ids', []):
                console.print(f"  • {proc_id}")

    except Exception as e:
        console.print(f"[red]Error resuming procedures: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@procedure.command()
@click.option('--interval', default=5, help='Polling interval in seconds')
def watch(interval: int):
    """Watch for HITL responses and auto-resume procedures.

    Continuously polls for procedures waiting for human responses and
    automatically resumes them when responses are received. Useful during
    development and testing to avoid manual resume commands.

    Press Ctrl+C to stop watching.

    Examples:
        plexus procedure watch                  # Poll every 5 seconds (default)
        plexus procedure watch --interval 10    # Poll every 10 seconds
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.resume_service import resume_all_pending

    console.print(f"[cyan]Watching for HITL responses every {interval}s...[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]\n")

    try:
        while True:
            result = resume_all_pending(client)

            if result['resumed'] > 0:
                console.print(f"[green]✓ Resumed {result['resumed']} procedure(s)[/green]")
                for proc_id in result.get('resumed_ids', []):
                    console.print(f"  • {proc_id}")
            elif result['found'] > 0:
                console.print(f"[dim]• {result['found']} procedure(s) still waiting...[/dim]")

            time.sleep(interval)

    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped watching.[/yellow]")


@procedure.command()
@click.option('--scorecard', '-s', required=True, help='Scorecard identifier (name, key, or ID)')
@click.option('--score', '-c', required=True, help='Score identifier (name, key, or ID)')
@click.option('--days', '-d', default=90, help='Feedback window in days (default: 90)')
@click.option('--max-samples', type=int, default=None, help='Maximum feedback samples per evaluation (default: all available)')
@click.option('--max-iterations', type=int, default=10, help='Maximum optimization iterations (default: 10)')
@click.option('--improvement-threshold', type=float, default=0.02, help='Minimum AC1 improvement to continue (default: 0.02)')
@click.option('--dry-run', is_flag=True, help='Run analysis only without making score updates')
@click.option('--resume-accuracy-eval', type=str, default=None, help='Reuse existing accuracy baseline evaluation ID (skip running baselines)')
@click.option('--resume-feedback-eval', type=str, default=None, help='Reuse existing feedback baseline evaluation ID (skip running baselines)')
@click.option('--version', '-v', type=str, default=None, help='Score version ID to start from instead of the champion version')
@click.option('--hint', type=str, default=None, help='Expert hint to guide the optimizer (included verbatim in agent context)')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def optimize(scorecard: str, score: str, days: int, max_samples: int, max_iterations: int, improvement_threshold: float, dry_run: bool, resume_accuracy_eval: str, resume_feedback_eval: str, version: str, hint: str, output: str):
    """Run feedback alignment optimization with RCA for a score.

    This command runs the iterative optimization loop:
    1. Run baseline feedback evaluation with RCA
    2. Analyze RCA and propose targeted improvements
    3. Create new score version and evaluate
    4. Compare metrics against baseline
    5. Repeat until convergence or max iterations

    Examples:
        # Basic optimization
        plexus procedure optimize -s customer-service -c empathy

        # With custom parameters
        plexus procedure optimize -s sales -c dnc-check --days 60 --max-iterations 5

        # Dry run (no changes)
        plexus procedure optimize -s test-sc -c test-score --dry-run

        # Conservative threshold (only continue if ≥5% improvement)
        plexus procedure optimize -s compliance -c safety --improvement-threshold 0.05
    """
    import os
    from pathlib import Path

    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    # Find the feedback alignment optimizer YAML
    # First check if we're in the Plexus repo
    yaml_path = Path(__file__).parent.parent.parent / "procedures" / "feedback_alignment_optimizer.yaml"

    if not yaml_path.exists():
        console.print(f"[red]Error: Could not find feedback_alignment_optimizer.yaml at {yaml_path}[/red]")
        console.print("[yellow]Hint: This command requires the procedure YAML to be in plexus/procedures/[/yellow]")
        return

    console.print(f"[cyan]Starting feedback alignment optimization...[/cyan]")
    console.print(f"  Scorecard: {scorecard}")
    console.print(f"  Score: {score}")
    console.print(f"  Feedback window: {days} days")
    console.print(f"  Max iterations: {max_iterations}")
    console.print(f"  Improvement threshold: {improvement_threshold:.2%}")
    console.print(f"  Dry run: {'Yes' if dry_run else 'No'}")
    console.print()

    # Build params JSON
    params = {
        "scorecard": scorecard,
        "score": score,
        "days": days,
        "max_iterations": max_iterations,
        "improvement_threshold": improvement_threshold,
        "dry_run": dry_run
    }
    if max_samples is not None:
        params["max_samples"] = max_samples
    if resume_accuracy_eval is not None:
        params["resume_accuracy_eval"] = resume_accuracy_eval
    if resume_feedback_eval is not None:
        params["resume_feedback_eval"] = resume_feedback_eval
    if version is not None:
        params["start_version"] = version
    if hint is not None:
        params["hint"] = hint

    # Load YAML
    try:
        with open(yaml_path, 'r') as f:
            yaml_config = f.read()
    except Exception as e:
        console.print(f"[red]Error reading procedure YAML: {str(e)}[/red]")
        return

    # Create procedure
    service = ProcedureService(client)
    account = os.environ.get('PLEXUS_ACCOUNT_KEY')
    if not account:
        console.print("[red]Error: PLEXUS_ACCOUNT_KEY environment variable must be set[/red]")
        return

    console.print("Creating optimization procedure...")
    result = service.create_procedure(
        account_identifier=account,
        scorecard_identifier=scorecard,
        score_identifier=score,
        yaml_config=yaml_config,
        featured=False,
        create_root_node=False,
        score_version_id=version,
    )

    if not result.success:
        console.print(f"[red]Error creating procedure: {result.message}[/red]")
        return

    procedure_id = result.procedure.id
    console.print(f"[green]✓ Created procedure {procedure_id}[/green]")
    console.print()

    # Run the procedure
    console.print(f"[cyan]Running optimization procedure...[/cyan]")
    console.print(f"[dim]Approval gates are surfaced through Plexus HITL (dashboard/chat).[/dim]")
    console.print()

    # Get account ID for task tracking
    from plexus.cli.report.utils import resolve_account_id_for_command
    account_id = resolve_account_id_for_command(client, None)

    # Run with task tracking
    import asyncio
    from plexus.cli.shared.experiment_runner import run_experiment_with_task_tracking

    options = {
        'context': params,
    }

    exec_result = asyncio.run(run_experiment_with_task_tracking(
        procedure_id=procedure_id,
        client=client,
        account_id=account_id,
        **options
    ))

    if exec_result.get('status') == 'error':
        console.print(f"[red]Error: {exec_result.get('error')}[/red]")
        return

    # Convert Lua tables to native Python types for serialization
    import json as json_mod

    def _lua_to_python(obj):
        """Recursively convert Lua tables to Python dicts/lists."""
        try:
            if hasattr(obj, 'keys') and hasattr(obj, 'values') and not isinstance(obj, dict):
                # Lua table acting as dict
                return {_lua_to_python(k): _lua_to_python(v) for k, v in obj.items()}
            elif isinstance(obj, dict):
                return {k: _lua_to_python(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_lua_to_python(v) for v in obj]
            elif isinstance(obj, tuple):
                return [_lua_to_python(v) for v in obj]
            elif hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
                return [_lua_to_python(v) for v in obj]
            else:
                return obj
        except (TypeError, ValueError):
            return str(obj)

    try:
        exec_result_clean = json_mod.loads(json_mod.dumps(_lua_to_python(exec_result), default=str))
    except (TypeError, ValueError):
        exec_result_clean = exec_result

    # Parse result
    if output == 'json':
        console.print(JSON.from_data(exec_result_clean))
    elif output == 'yaml':
        console.print(yaml.dump(exec_result_clean, default_flow_style=False))
    else:
        # Table format - show summary
        console.print()
        console.print("[green]✓ Optimization complete[/green]")
        console.print()

        # Extract key info from result
        iterations = exec_result_clean.get('result', {}).get('iterations', [])
        improvement = exec_result_clean.get('result', {}).get('improvement', 0)
        status = exec_result_clean.get('result', {}).get('status', 'unknown')

        table = Table(title="Optimization Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Status", status)
        table.add_row("Total Iterations", str(len(iterations)))
        table.add_row("AC1 Improvement", f"{improvement:+.4f}")

        if iterations:
            baseline = iterations[0].get('metrics') if isinstance(iterations[0], dict) else None
            final = iterations[-1].get('metrics') if isinstance(iterations[-1], dict) else None
            if baseline and isinstance(baseline, dict):
                table.add_row("Baseline AC1", f"{baseline.get('alignment', 0):.4f}")
            if final and isinstance(final, dict):
                table.add_row("Final AC1", f"{final.get('alignment', 0):.4f}")

        console.print(table)

        if iterations:
            console.print()
            console.print("[bold]Iteration Summary:[/bold]")
            for it in iterations:
                if not isinstance(it, dict):
                    continue
                deltas = it.get('deltas')
                if deltas and isinstance(deltas, dict):
                    delta = deltas.get('alignment', 0)
                    delta_str = f"[green]{delta:+.4f}[/green]" if delta >= 0 else f"[red]{delta:+.4f}[/red]"
                else:
                    delta_str = "N/A"
                hypothesis = it.get('hypothesis', 'N/A') or 'N/A'
                iteration_num = it.get('iteration', '?')
                console.print(f"  {iteration_num}. {hypothesis[:60]}... (AC1 {delta_str})")


@procedure.command()
@click.argument('procedure_id')
@click.option('--after', '-a', help='Clear checkpoints after this step name')
def reset(procedure_id: str, after: Optional[str]):
    """Reset procedure checkpoints for testing.

    Clears checkpoints to allow re-execution. Useful for testing and development.

    Without --after: Clears ALL checkpoints (procedure restarts from beginning)
    With --after: Clears checkpoint and all subsequent ones (partial reset)

    Examples:
        plexus procedure reset proc-123abc
        plexus procedure reset proc-123abc --after "evaluate_candidate_1"
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.reset_service import reset_checkpoints

    if after:
        console.print(f"Clearing checkpoints after '{after}' for procedure {procedure_id}...")
    else:
        console.print(f"[yellow]⚠️  Clearing ALL checkpoints for procedure {procedure_id}...[/yellow]")

    try:
        result = reset_checkpoints(client, procedure_id, after_step=after)

        console.print(f"[green]✓ Checkpoints cleared[/green]")
        console.print(f"Cleared: {result['cleared_count']} checkpoints")
        console.print(f"Remaining: {result['remaining_count']} checkpoints")

        console.print(f"\n[blue]→ Run 'plexus procedure run {procedure_id}' to re-execute[/blue]")

    except Exception as e:
        console.print(f"[red]Error resetting checkpoints: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


# Add to CLI
if __name__ == "__main__":
    procedure()

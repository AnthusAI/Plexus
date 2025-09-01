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
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
from datetime import datetime

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console
from .service import ProcedureService, DEFAULT_PROCEDURE_YAML

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
        account = os.environ.get('PLEXUS_ACCOUNT_KEY', 'call-criteria')
    
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
        account = os.environ.get('PLEXUS_ACCOUNT_KEY', 'call-criteria')
    
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
        yaml_config = service.get_experiment_yaml(procedure_id)
    
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
    
    yaml_config = service.get_experiment_yaml(procedure_id)
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
@click.argument('procedure_id')
@click.option('--max-iterations', type=int, help='Maximum number of iterations')
@click.option('--timeout', type=int, help='Timeout in seconds')
@click.option('--async-mode', is_flag=True, help='Run procedure asynchronously')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without actual execution')
@click.option('--openai-api-key', help='OpenAI API key for AI-powered experiments (or set OPENAI_API_KEY env var)')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def run(procedure_id: str, max_iterations: Optional[int], timeout: Optional[int], 
        async_mode: bool, dry_run: bool, openai_api_key: Optional[str], output: str):
    """Run an procedure with the given ID.
    
    Executes the procedure using its configured YAML settings. The experiment
    will process its nodes according to the defined workflow and return results.
    
    Examples:
        plexus procedure run abc123def456
        plexus procedure run abc123def456 --dry-run
        plexus procedure run abc123def456 --max-iterations 50 --timeout 300
        plexus procedure run abc123def456 --async-mode -o json
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
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
    
    # Add AI options
    if openai_api_key:
        options['openai_api_key'] = openai_api_key
    
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

@procedure.command()
@click.option('--output', '-o', help='Output file path (default: experiment-template.yaml)')
def template(output: Optional[str]):
    """Generate a template YAML configuration for procedures.
    
    Creates a sample YAML file with the default BeamSearch configuration
    that can be customized for new experiments.
    
    Examples:
        plexus procedure template
        plexus procedure template --output my-template.yaml
    """
    if not output:
        output = "experiment-template.yaml"
    
    try:
        with open(output, 'w') as f:
            f.write(DEFAULT_PROCEDURE_YAML)
        console.print(f"[green]✓ Created template at {output}[/green]")
        console.print("\nEdit the template and use it with:")
        console.print(f"  plexus procedure create -s SCORECARD -c SCORE --yaml {output}")
    except Exception as e:
        console.print(f"[red]Error writing template to {output}: {str(e)}[/red]")

# Add to CLI
if __name__ == "__main__":
    procedure()
"""
Experiment CLI Commands - Command-line interface for experiment management.

Provides commands for:
- Creating new experiments
- Listing experiments  
- Showing experiment details
- Updating experiment configurations
- Deleting experiments
- Managing experiment execution

Uses the shared ExperimentService for consistent behavior.
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
from .service import ExperimentService, DEFAULT_EXPERIMENT_YAML

@click.group()
def experiment():
    """Manage experiments for AI system optimization."""
    pass

@experiment.command()
@click.option('--account', '-a', help='Account identifier (key, name, or ID)')
@click.option('--scorecard', '-s', required=True, help='Scorecard identifier (key, name, or ID)')
@click.option('--score', '-c', required=True, help='Score identifier (key, name, or ID)')
@click.option('--yaml', '-y', help='YAML configuration file path')
@click.option('--featured', is_flag=True, help='Mark experiment as featured')
@click.option('--no-root-node', is_flag=True, help='Create experiment without a root node')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def create(account: Optional[str], scorecard: str, score: str, yaml: Optional[str], featured: bool, no_root_node: bool, output: str):
    """Create a new experiment.
    
    Creates an experiment associated with a specific scorecard and score.
    By default, creates a root node with a BeamSearch template. Use --no-root-node 
    to create an empty experiment without any nodes.
    
    Examples:
        plexus experiment create -s "Sales Scorecard" -c "DNC Requested"
        plexus experiment create -s sales-scorecard -c dnc-requested --yaml config.yaml
        plexus experiment create -a my-account -s scorecard-id -c score-id --featured
        plexus experiment create -s scorecard -c score --no-root-node
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
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
    
    console.print(f"Creating experiment for scorecard '{scorecard}' and score '{score}'...")
    
    result = service.create_experiment(
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
            'experiment_id': result.experiment.id,
            'root_node_id': result.root_node.id,
            'initial_version_id': result.initial_version.id,
            'featured': result.experiment.featured,
            'created_at': result.experiment.createdAt.isoformat(),
            'scorecard_id': result.experiment.scorecardId,
            'score_id': result.experiment.scoreId
        }
        console.print(JSON.from_data(data))
    elif output == 'yaml':
        data = {
            'experiment_id': result.experiment.id,
            'root_node_id': result.root_node.id,
            'initial_version_id': result.initial_version.id,
            'featured': result.experiment.featured,
            'created_at': result.experiment.createdAt.isoformat(),
            'scorecard_id': result.experiment.scorecardId,
            'score_id': result.experiment.scoreId
        }
        console.print(yaml.dump(data, default_flow_style=False))
    else:
        # Table format
        console.print(f"[green]✓ {result.message}[/green]")
        
        table = Table(title="Created Experiment")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Experiment ID", result.experiment.id)
        table.add_row("Root Node ID", result.root_node.id)
        table.add_row("Initial Version ID", result.initial_version.id)
        table.add_row("Featured", "Yes" if result.experiment.featured else "No")
        table.add_row("Created", result.experiment.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Scorecard ID", result.experiment.scorecardId or "N/A")
        table.add_row("Score ID", result.experiment.scoreId or "N/A")
        
        console.print(table)

@experiment.command()
@click.option('--account', '-a', help='Account identifier (key, name, or ID)')
@click.option('--scorecard', '-s', help='Filter by scorecard identifier')
@click.option('--limit', '-l', default=20, help='Maximum number of experiments to show')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def list(account: Optional[str], scorecard: Optional[str], limit: int, output: str):
    """List experiments.
    
    Shows experiments ordered by most recent first. Can be filtered by account
    and/or scorecard.
    
    Examples:
        plexus experiment list
        plexus experiment list -a my-account -l 10
        plexus experiment list -s "Sales Scorecard"
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
    # Use default account if not specified
    if not account:
        import os
        account = os.environ.get('PLEXUS_ACCOUNT_KEY', 'call-criteria')
    
    experiments = service.list_experiments(
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
        table = Table(title=f"Experiments ({len(experiments)} found)")
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

@experiment.command()
@click.argument('experiment_id')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
@click.option('--include-yaml', is_flag=True, help='Include YAML configuration in output')
def show(experiment_id: str, output: str, include_yaml: bool):
    """Show detailed information about an experiment.
    
    Displays comprehensive information including nodes, versions, and configuration.
    
    Examples:
        plexus experiment show abc123def456
        plexus experiment show abc123def456 --include-yaml
        plexus experiment show abc123def456 -o json
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
    info = service.get_experiment_info(experiment_id)
    if not info:
        console.print(f"[red]Error: Experiment {experiment_id} not found[/red]")
        return
    
    # Get YAML if requested
    yaml_config = None
    if include_yaml:
        yaml_config = service.get_experiment_yaml(experiment_id)
    
    if output == 'json':
        data = {
            'experiment': {
                'id': info.experiment.id,
                'featured': info.experiment.featured,
                'created_at': info.experiment.createdAt.isoformat(),
                'updated_at': info.experiment.updatedAt.isoformat(),
                'account_id': info.experiment.accountId,
                'scorecard_id': info.experiment.scorecardId,
                'score_id': info.experiment.scoreId,
                'root_node_id': info.experiment.rootNodeId
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
            'experiment': {
                'id': info.experiment.id,
                'featured': info.experiment.featured,
                'created_at': info.experiment.createdAt.isoformat(),
                'updated_at': info.experiment.updatedAt.isoformat(),
                'account_id': info.experiment.accountId,
                'scorecard_id': info.experiment.scorecardId,
                'score_id': info.experiment.scoreId,
                'root_node_id': info.experiment.rootNodeId
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
        console.print(Panel(f"[bold cyan]Experiment Details[/bold cyan]", title="Experiment"))
        
        # Basic info table
        table = Table(show_header=False, box=None)
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white")
        
        table.add_row("ID", info.experiment.id)
        table.add_row("Featured", "★ Yes" if info.experiment.featured else "No")
        table.add_row("Created", info.experiment.createdAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Updated", info.experiment.updatedAt.strftime("%Y-%m-%d %H:%M:%S UTC"))
        table.add_row("Account ID", info.experiment.accountId)
        table.add_row("Root Node ID", info.experiment.rootNodeId or "N/A")
        
        if info.scorecard_name:
            table.add_row("Scorecard", f"{info.scorecard_name} ({info.experiment.scorecardId})")
        else:
            table.add_row("Scorecard ID", info.experiment.scorecardId or "N/A")
        
        if info.score_name:
            table.add_row("Score", f"{info.score_name} ({info.experiment.scoreId})")
        else:
            table.add_row("Score ID", info.experiment.scoreId or "N/A")
        
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

@experiment.command()
@click.argument('experiment_id')
@click.option('--yaml', '-y', help='YAML configuration file path')
@click.option('--note', '-n', help='Note for this configuration version')
def update(experiment_id: str, yaml: Optional[str], note: Optional[str]):
    """Update an experiment's configuration.
    
    Creates a new version with the provided YAML configuration.
    
    Examples:
        plexus experiment update abc123def456 --yaml new-config.yaml
        plexus experiment update abc123def456 --yaml config.yaml --note "Improved exploration"
    """
    if not yaml:
        console.print("[red]Error: --yaml option is required[/red]")
        return
    
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
    # Load YAML configuration
    try:
        with open(yaml, 'r') as f:
            yaml_config = f.read()
    except Exception as e:
        console.print(f"[red]Error reading YAML file {yaml}: {str(e)}[/red]")
        return
    
    console.print(f"Updating experiment {experiment_id}...")
    
    success, message = service.update_experiment_config(experiment_id, yaml_config, note)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]Error: {message}[/red]")

@experiment.command()
@click.argument('experiment_id')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def delete(experiment_id: str, confirm: bool):
    """Delete an experiment and all its data.
    
    This will permanently delete the experiment, all its nodes, and all versions.
    This action cannot be undone.
    
    Examples:
        plexus experiment delete abc123def456
        plexus experiment delete abc123def456 --confirm
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
    # Get experiment info for confirmation
    info = service.get_experiment_info(experiment_id)
    if not info:
        console.print(f"[red]Error: Experiment {experiment_id} not found[/red]")
        return
    
    if not confirm:
        console.print(f"[yellow]WARNING: This will permanently delete experiment {experiment_id}[/yellow]")
        console.print(f"Experiment has {info.node_count} nodes and {info.version_count} versions")
        if not click.confirm("Are you sure you want to continue?"):
            console.print("Deletion cancelled")
            return
    
    console.print(f"Deleting experiment {experiment_id}...")
    
    success, message = service.delete_experiment(experiment_id)
    
    if success:
        console.print(f"[green]✓ {message}[/green]")
    else:
        console.print(f"[red]Error: {message}[/red]")

@experiment.command()
@click.argument('experiment_id')
@click.option('--output', '-o', help='Output file path (default: experiment-{id}.yaml)')
def pull(experiment_id: str, output: Optional[str]):
    """Pull the latest YAML configuration from an experiment.
    
    Saves the experiment's current YAML configuration to a file.
    
    Examples:
        plexus experiment pull abc123def456
        plexus experiment pull abc123def456 --output my-config.yaml
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    service = ExperimentService(client)
    
    yaml_config = service.get_experiment_yaml(experiment_id)
    if not yaml_config:
        console.print(f"[red]Error: Could not get YAML configuration for experiment {experiment_id}[/red]")
        return
    
    if not output:
        output = f"experiment-{experiment_id[:8]}.yaml"
    
    try:
        with open(output, 'w') as f:
            f.write(yaml_config)
        console.print(f"[green]✓ Saved configuration to {output}[/green]")
    except Exception as e:
        console.print(f"[red]Error writing to {output}: {str(e)}[/red]")

@experiment.command()
@click.argument('experiment_id')
@click.option('--max-iterations', type=int, help='Maximum number of iterations')
@click.option('--timeout', type=int, help='Timeout in seconds')
@click.option('--async-mode', is_flag=True, help='Run experiment asynchronously')
@click.option('--dry-run', is_flag=True, help='Perform a dry run without actual execution')
@click.option('--openai-api-key', help='OpenAI API key for AI-powered experiments (or set OPENAI_API_KEY env var)')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def run(experiment_id: str, max_iterations: Optional[int], timeout: Optional[int], 
        async_mode: bool, dry_run: bool, openai_api_key: Optional[str], output: str):
    """Run an experiment with the given ID.
    
    Executes the experiment using its configured YAML settings. The experiment
    will process its nodes according to the defined workflow and return results.
    
    Examples:
        plexus experiment run abc123def456
        plexus experiment run abc123def456 --dry-run
        plexus experiment run abc123def456 --max-iterations 50 --timeout 300
        plexus experiment run abc123def456 --async-mode -o json
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return
    
    console.print(f"Running experiment {experiment_id} with task tracking...")
    
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
    
    # Run the experiment with task tracking (async)
    import asyncio
    from plexus.cli.shared.experiment_runner import run_experiment_with_task_tracking
    
    result = asyncio.run(run_experiment_with_task_tracking(
        experiment_id=experiment_id,
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
        
        console.print(f"[{status_color}]✓ {result.get('message', 'Experiment run completed')}[/{status_color}]")
        
        # Basic results table
        table = Table(title="Experiment Run Results")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")
        
        table.add_row("Experiment ID", result.get('experiment_id', 'N/A'))
        table.add_row("Status", status.upper())
        
        details = result.get('details', {})
        if details:
            if details.get('experiment_name'):
                table.add_row("Experiment Name", details['experiment_name'])
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

@experiment.command()
@click.option('--output', '-o', help='Output file path (default: experiment-template.yaml)')
def template(output: Optional[str]):
    """Generate a template YAML configuration for experiments.
    
    Creates a sample YAML file with the default BeamSearch configuration
    that can be customized for new experiments.
    
    Examples:
        plexus experiment template
        plexus experiment template --output my-template.yaml
    """
    if not output:
        output = "experiment-template.yaml"
    
    try:
        with open(output, 'w') as f:
            f.write(DEFAULT_EXPERIMENT_YAML)
        console.print(f"[green]✓ Created template at {output}[/green]")
        console.print("\nEdit the template and use it with:")
        console.print(f"  plexus experiment create -s SCORECARD -c SCORE --yaml {output}")
    except Exception as e:
        console.print(f"[red]Error writing template to {output}: {str(e)}[/red]")

# Add to CLI
if __name__ == "__main__":
    experiment()
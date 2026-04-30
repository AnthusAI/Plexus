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
from typing import Any, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
from datetime import datetime


def _json_safe(obj: Any) -> Any:
    """Recursively convert non-serializable objects (e.g. Pydantic models) to plain dicts/lists."""
    _dict = __builtins__["dict"] if isinstance(__builtins__, dict) else dict  # type: ignore[index]
    _list = __builtins__["list"] if isinstance(__builtins__, dict) else list  # type: ignore[index]
    if type(obj) is _dict or (hasattr(obj, "items") and hasattr(obj, "keys") and not hasattr(obj, "model_dump")):
        try:
            return {k: _json_safe(v) for k, v in obj.items()}
        except Exception:
            pass
    if type(obj) is _list or isinstance(obj, (tuple,)):
        try:
            return [_json_safe(v) for v in obj]
        except Exception:
            pass
    if hasattr(obj, "model_dump"):
        try:
            return _json_safe(obj.model_dump())
        except Exception:
            return str(obj)
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        try:
            return _json_safe(vars(obj))
        except Exception:
            pass
    try:
        import json as _json
        _json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)

from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console
from plexus.cli.shared.optimizer_results import OptimizerResultsService
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
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def create(account: Optional[str], scorecard: str, score: str, yaml: Optional[str], featured: bool, output: str):
    """Create a new procedure.
    
    Creates an procedure associated with a specific scorecard and score.
    
    Examples:
        plexus procedure create -s "Sales Scorecard" -c "DNC Requested"
        plexus procedure create -s sales-scorecard -c dnc-requested --yaml config.yaml
        plexus procedure create -a my-account -s scorecard-id -c score-id --featured
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
        featured=featured
    )
    
    if not result.success:
        console.print(f"[red]Error: {result.message}[/red]")
        return
    
    if output == 'json':
        data = {
            'procedure_id': result.procedure.id,
            'featured': result.procedure.featured,
            'created_at': result.procedure.createdAt.isoformat(),
            'scorecard_id': result.procedure.scorecardId,
            'score_id': result.procedure.scoreId
        }
        console.print(JSON.from_data(data))
    elif output == 'yaml':
        data = {
            'procedure_id': result.procedure.id,
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
        
        for exp in experiments:
            table.add_row(
                exp.id[:10] + "..." if len(exp.id) > 12 else exp.id,
                "★" if exp.featured else "",
                exp.createdAt.strftime("%Y-%m-%d %H:%M"),
                (exp.scorecardId[:10] + "...") if exp.scorecardId and len(exp.scorecardId) > 12 else (exp.scorecardId or "N/A"),
                (exp.scoreId[:10] + "...") if exp.scoreId and len(exp.scoreId) > 12 else (exp.scoreId or "N/A")
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
            },
            'summary': {
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
            },
            'summary': {
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


@procedure.command("timeout-stale")
@click.option('--account', '-a', help='Account identifier (key, name, or ID)')
@click.option('--threshold-seconds', type=int, default=3600, show_default=True, help='Mark RUNNING procedures stale after this many seconds without chat activity')
@click.option('--lookback-hours', type=int, default=72, show_default=True, help='Only consider procedures started within this many hours')
@click.option('--dry-run', is_flag=True, help='Show stale procedures without updating records')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def timeout_stale(account: Optional[str], threshold_seconds: int, lookback_hours: int, dry_run: bool, output: str):
    """Detect and mark stale procedure runs using chat-message inactivity.

    A RUNNING procedure is considered stale when it has produced no new chat
    messages for the configured threshold.
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.report.utils import resolve_account_id_for_command
    from .stale_timeout import timeout_stale_procedures

    account_id = resolve_account_id_for_command(client, account)
    result = timeout_stale_procedures(
        client=client,
        account_id=account_id,
        threshold_seconds=threshold_seconds,
        lookback_hours=lookback_hours,
        dry_run=dry_run,
    )

    if output == 'json':
        console.print(JSON.from_data(_json_safe(result)))
        return
    if output == 'yaml':
        console.print(yaml.dump(result, default_flow_style=False))
        return

    summary = (
        f"Recent started {result.get('recent_started_count', 0)} | "
        f"Checked RUNNING {result.get('checked', 0)} | "
        f"Timed out {len(result.get('timed_out') or [])} | "
        f"Skipped {len(result.get('skipped') or [])}"
    )
    style = "yellow" if dry_run else "green"
    console.print(f"[{style}]{summary}[/{style}]")

    recent_started = result.get("recent_started") or []
    if recent_started:
        recent_table = Table(title=f"Procedures Started In Last {lookback_hours} Hours")
        recent_table.add_column("Procedure", style="cyan")
        recent_table.add_column("Task", style="magenta")
        recent_table.add_column("Status", style="white")
        recent_table.add_column("Started", style="green")
        recent_table.add_column("Updated", style="yellow")
        for item in recent_started:
            recent_table.add_row(
                str(item.get("procedure_id") or ""),
                str(item.get("task_id") or ""),
                str(item.get("status") or ""),
                str(item.get("started_at") or "N/A"),
                str(item.get("updated_at") or "N/A"),
            )
        console.print(recent_table)

    timed_out = result.get("timed_out") or []
    if timed_out:
        table = Table(title="Stale Procedures")
        table.add_column("Procedure", style="cyan")
        table.add_column("Task", style="magenta")
        table.add_column("Last Chat Activity", style="white")
        table.add_column("Silence (min)", style="yellow", justify="right")
        table.add_column("Action", style="green")
        for item in timed_out:
            silence_minutes = int((item.get("silence_seconds") or 0) / 60)
            table.add_row(
                str(item.get("procedure_id") or ""),
                str(item.get("task_id") or ""),
                str(item.get("last_chat_activity_at") or "N/A"),
                str(silence_minutes),
                "Would fail" if dry_run else "Failed",
            )
        console.print(table)
    elif dry_run:
        console.print("[green]No stale procedures detected[/green]")

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
@click.option('--openai-api-key', help='OpenAI API key for AI-powered experiments (or set OPENAI_API_KEY env var)')
@click.option('--set', '-s', 'set_params', multiple=True, help='Set procedure parameter as key=value (e.g., --set scorecard="AW - Confirmation")')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def run(procedure_id: Optional[str], yaml_file: Optional[str], max_iterations: Optional[int], timeout: Optional[int],
        async_mode: bool, dry_run: bool, openai_api_key: Optional[str], set_params: tuple, output: str):
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
        parsed_set_params: dict = {}
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
                    parsed_set_params[k] = v

        # Inject --set param values into YAML params so they are persisted in the
        # stored procedure code (the same way the dashboard does it at creation time).
        if parsed_set_params and isinstance(config, dict) and 'params' in config:
            yaml_params_def = config.get('params', {})
            if isinstance(yaml_params_def, dict):
                for k, v in parsed_set_params.items():
                    if k in yaml_params_def and isinstance(yaml_params_def[k], dict):
                        yaml_params_def[k]['value'] = v
                yaml_config = yaml_lib.dump(config, allow_unicode=True, default_flow_style=False)

        console.print("Creating procedure from YAML...")
        result = service.create_procedure(
            account_identifier=account,
            scorecard_identifier=scorecard_identifier_for_create,
            score_identifier=score_identifier_for_create,
            yaml_config=yaml_config,
            featured=False,
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
                stage_configs=stage_configs,
            )

        if not result.success:
            console.print(f"[red]Error creating procedure: {result.message}[/red]")
            return

        procedure_id = result.procedure.id
        console.print(f"[green]✓ Created procedure {procedure_id}[/green]")
        console.print()


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
    from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking
    
    result = asyncio.run(run_procedure_with_task_tracking(
        procedure_id=procedure_id,
        client=client,
        account_id=account_id,
        **options
    ))
    
    if result.get('status') == 'error':
        console.print(f"[red]Error: {result.get('error')}[/red]")
        return
    
    if output == 'json':
        console.print(JSON.from_data(_json_safe(result)))
    elif output == 'yaml':
        console.print(yaml.dump(result, default_flow_style=False))
    else:
        # Table format
        status = result.get('status', 'unknown')
        status_color = {
            'completed': 'green',
            'COMPLETED': 'green',
            'running': 'yellow', 
            'RUNNING': 'yellow',
            'WAITING_FOR_HUMAN': 'yellow',
            'initiated': 'blue',
            'error': 'red',
            'FAILED': 'red',
            'failed': 'red',
            'STALLED': 'yellow',
            'stalled': 'yellow',
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
        console.print(JSON.from_data(_json_safe(result)))
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
@click.option('--resume-regression-eval', type=str, default=None, help='Reuse existing regression baseline evaluation ID (skip running baselines)')
@click.option('--resume-recent-eval', type=str, default=None, help='Reuse existing recent baseline evaluation ID (skip running baselines)')
@click.option('--version', '-v', type=str, default=None, help='Score version ID to start from instead of the champion version')
@click.option('--hint', type=str, default=None, help='Expert hint to guide the optimizer (included verbatim in agent context)')
@click.option(
    '--agent-model',
    'agent_models',
    multiple=True,
    help='Per-agent model override as agent=model. Repeatable. Example: --agent-model hypothesis_planner=gpt-5.4-mini',
)
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table', help='Output format')
def optimize(scorecard: str, score: str, days: int, max_samples: int, max_iterations: int, improvement_threshold: float, dry_run: bool, resume_regression_eval: str, resume_recent_eval: str, version: str, hint: str, agent_models: tuple[str, ...], output: str):
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
    if agent_models:
        console.print(f"  Agent model overrides: {', '.join(agent_models)}")
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
    if resume_regression_eval is not None:
        params["resume_regression_eval"] = resume_regression_eval
    if resume_recent_eval is not None:
        params["resume_recent_eval"] = resume_recent_eval
    if version is not None:
        params["start_version"] = version
    if hint is not None:
        params["hint"] = hint
    if agent_models:
        overrides = {}
        for raw_override in agent_models:
            if "=" not in raw_override:
                console.print(f"[red]Error: --agent-model must be formatted as agent=model, got {raw_override!r}[/red]")
                return
            agent_name, model_name = raw_override.split("=", 1)
            agent_name = agent_name.strip()
            model_name = model_name.strip()
            if not agent_name or not model_name:
                console.print(f"[red]Error: --agent-model must include a non-empty agent and model, got {raw_override!r}[/red]")
                return
            overrides[agent_name] = model_name
        params["agent_models"] = overrides

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
    from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking

    options = {
        'context': params,
    }

    exec_result = asyncio.run(run_procedure_with_task_tracking(
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
@click.option('--checkpoints-only', is_flag=True, default=False,
              help='Clear only checkpoints, preserving accumulated State (use before continuation)')
def reset(procedure_id: str, after: Optional[str], checkpoints_only: bool):
    """Reset procedure checkpoints for testing.

    Clears checkpoints to allow re-execution. Useful for testing and development.

    Without --after: Clears ALL checkpoints (procedure restarts from beginning)
    With --after: Clears checkpoint and all subsequent ones (partial reset)
    With --checkpoints-only: Clears checkpoints but preserves State (for continuation runs)

    Examples:
        plexus procedure reset proc-123abc
        plexus procedure reset proc-123abc --after "evaluate_candidate_1"
        plexus procedure reset proc-123abc --checkpoints-only
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.reset_service import reset_checkpoints, reset_checkpoints_only

    if checkpoints_only:
        console.print(f"Clearing checkpoints (preserving State) for procedure {procedure_id}...")
    elif after:
        console.print(f"Clearing checkpoints after '{after}' for procedure {procedure_id}...")
    else:
        console.print(f"[yellow]⚠️  Clearing ALL checkpoints for procedure {procedure_id}...[/yellow]")

    try:
        if checkpoints_only:
            result = reset_checkpoints_only(client, procedure_id)
        else:
            result = reset_checkpoints(client, procedure_id, after_step=after)

        console.print(f"[green]✓ Checkpoints cleared[/green]")
        console.print(f"Cleared: {result['cleared_count']} checkpoints")
        console.print(f"Remaining: {result['remaining_count']} checkpoints")

        console.print(f"\n[blue]→ Run 'plexus procedure run {procedure_id}' to re-execute[/blue]")

    except Exception as e:
        console.print(f"[red]Error resetting checkpoints: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@procedure.command('continue')
@click.argument('procedure_id')
@click.option('--additional-cycles', '-n', type=int, default=3,
              help='Number of additional cycles to run (default: 3)')
@click.option('--hint', '-h', 'hint', default=None,
              help='Optional instructions to guide the continuation run')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table')
def continue_(procedure_id: str, additional_cycles: int, hint: Optional[str], output: str):
    """Continue a completed optimizer procedure for additional cycles.

    Updates max_iterations, clears Tactus replay checkpoints (preserving
    accumulated State), then re-dispatches the procedure.  The optimizer
    detects prior iterations and skips expensive dataset/baseline init.

    Examples:
        plexus procedure continue abc-123
        plexus procedure continue abc-123 --additional-cycles 5
        plexus procedure continue abc-123 -n 2 --hint "focus on false positives"
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.continuation_service import (
        build_continuation_context,
        prepare_continuation,
    )

    console.print(f"Preparing continuation for procedure {procedure_id} (+{additional_cycles} cycles)...")

    try:
        info = prepare_continuation(client, procedure_id, additional_cycles, hint)
    except Exception as e:
        console.print(f"[red]Error preparing continuation: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return

    console.print(
        f"[green]✓ Ready[/green] — {info['completed_cycles']} cycles done, "
        f"running to {info['new_max_iterations']} total"
    )
    if info['hint_applied']:
        console.print(f"  Hint: {hint}")

    console.print("Dispatching procedure run...")

    from plexus.cli.report.utils import resolve_account_id_for_command
    account_id = resolve_account_id_for_command(client, None)

    import asyncio
    from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking
    context = build_continuation_context(
        client,
        procedure_id,
        max_iterations=info["new_max_iterations"],
        hint=hint,
    )

    try:
        result = asyncio.run(run_procedure_with_task_tracking(
            procedure_id=procedure_id,
            client=client,
            account_id=account_id,
            context=context,
        ))
    except Exception as e:
        console.print(f"[red]Error dispatching procedure: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return

    if output == 'json':
        import json as _json
        console.print(_json.dumps(result, indent=2, default=str))
    else:
        status = result.get('status', 'unknown')
        color = {
            'completed': 'green',
            'COMPLETED': 'green',
            'running': 'yellow',
            'RUNNING': 'yellow',
            'WAITING_FOR_HUMAN': 'yellow',
            'initiated': 'blue',
            'error': 'red',
            'FAILED': 'red',
            'failed': 'red',
            'STALLED': 'yellow',
            'stalled': 'yellow',
        }.get(status, 'white')
        console.print(f"[{color}]{result.get('message', 'Continuation dispatched')}[/{color}]")
        console.print(f"Procedure: {procedure_id} | Task: {result.get('task_id', 'N/A')}")


@procedure.command('branch')
@click.argument('source_id')
@click.option('--cycle', '-c', type=int, required=True,
              help='Branch from after this cycle number')
@click.option('--additional-cycles', '-n', type=int, default=3,
              help='Number of cycles to run in the branch (default: 3)')
@click.option('--hint', '-h', 'hint', default=None,
              help='Optional instructions for the branch run')
@click.option('--name', default=None, help='Name for the new branch procedure')
@click.option('--output', '-o', type=click.Choice(['json', 'yaml', 'table']), default='table')
def branch(source_id: str, cycle: int, additional_cycles: int, hint: Optional[str],
           name: Optional[str], output: str):
    """Branch a procedure from cycle N into a new procedure.

    Creates a new procedure whose State is a copy of source_id truncated to
    cycle N, then dispatches it.  The optimizer detects N prior cycles and
    runs additional cycles from cycle N+1.

    Examples:
        plexus procedure branch abc-123 --cycle 2
        plexus procedure branch abc-123 --cycle 2 --additional-cycles 5
        plexus procedure branch abc-123 -c 3 -n 4 --hint "try structural prompt changes"
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.continuation_service import (
        build_continuation_context,
        prepare_branch,
    )

    console.print(f"Branching {source_id} from cycle {cycle} (+{additional_cycles} cycles)...")

    try:
        info = prepare_branch(client, source_id, cycle, additional_cycles, hint, name)
    except Exception as e:
        console.print(f"[red]Error preparing branch: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return

    target_id = info['target_id']
    console.print(
        f"[green]✓ Branch created[/green]: {target_id}\n"
        f"  Name: {info['target_name']}\n"
        f"  Cycles: {cycle} carried over, running to {info['new_max_iterations']} total"
    )

    console.print("Dispatching branch run...")

    from plexus.cli.report.utils import resolve_account_id_for_command
    account_id = resolve_account_id_for_command(client, None)

    import asyncio
    from plexus.cli.shared.experiment_runner import run_procedure_with_task_tracking
    context = build_continuation_context(
        client,
        target_id,
        max_iterations=info["new_max_iterations"],
        hint=hint,
    )

    try:
        result = asyncio.run(run_procedure_with_task_tracking(
            procedure_id=target_id,
            client=client,
            account_id=account_id,
            context=context,
        ))
    except Exception as e:
        console.print(f"[red]Error dispatching branch: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        return

    if output == 'json':
        import json as _json
        console.print(_json.dumps({**info, **result}, indent=2, default=str))
    else:
        status = result.get('status', 'unknown')
        color = {
            'completed': 'green',
            'COMPLETED': 'green',
            'running': 'yellow',
            'RUNNING': 'yellow',
            'WAITING_FOR_HUMAN': 'yellow',
            'initiated': 'blue',
            'error': 'red',
            'FAILED': 'red',
            'failed': 'red',
            'STALLED': 'yellow',
            'stalled': 'yellow',
        }.get(status, 'white')
        console.print(f"[{color}]{result.get('message', 'Branch dispatched')}[/{color}]")
        console.print(f"Branch procedure: {target_id} | Task: {result.get('task_id', 'N/A')}")


@procedure.command('clone-state')
@click.argument('source_id')
@click.argument('target_id')
@click.option('--truncate-to-cycle', '-n', type=int, required=True,
              help='Copy only the first N cycles of state to the target procedure')
def clone_state(source_id: str, target_id: str, truncate_to_cycle: int):
    """Clone procedure state to a branch target, truncated to cycle N.

    Copies accumulated optimizer State (iterations, baselines, dataset, etc.)
    from SOURCE_ID to TARGET_ID, keeping only the first N cycles.  The target
    procedure gets empty checkpoints so the optimizer runs fresh from cycle N+1.

    Used internally by the 'Branch from cycle N' UI action.

    Examples:
        plexus procedure clone-state src-uuid tgt-uuid --truncate-to-cycle 3
    """
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    from plexus.cli.procedure.reset_service import clone_state_for_branch

    console.print(f"Cloning state from {source_id} → {target_id} (truncating to {truncate_to_cycle} cycles)...")

    try:
        result = clone_state_for_branch(client, source_id, target_id, truncate_to_cycle)
        console.print(f"[green]✓ State cloned[/green]")
        console.print(f"Iterations copied: {result['iterations_copied']}")
        console.print(f"Truncated to cycle: {result['truncated_to_cycle']}")
        console.print(f"\n[blue]→ Run 'plexus procedure run {target_id}' to execute the branch[/blue]")
    except Exception as e:
        console.print(f"[red]Error cloning state: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())


@procedure.command("index-optimizer-run")
@click.argument("procedure_id")
@click.option("--force", is_flag=True, help="Rewrite optimizer artifacts even if the task already has them attached")
@click.option("--output", "-o", type=click.Choice(["json", "yaml", "table"]), default="table", show_default=True)
def index_optimizer_run(procedure_id: str, force: bool, output: str):
    """Index one historical optimizer run into canonical task attachments."""
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    service = OptimizerResultsService(client)
    try:
        result = service.index_optimizer_run(procedure_id, force=force)
    except Exception as exc:
        console.print(f"[red]Error indexing optimizer run: {exc}[/red]")
        return

    payload = {
        "procedure_id": procedure_id,
        "task_id": result["task_id"],
        "pointer": result["pointer"],
        "summary": result["manifest"].get("summary"),
        "best": result["manifest"].get("best"),
    }

    if output == "json":
        click.echo(json.dumps(payload, indent=2, default=str))
        return
    if output == "yaml":
        click.echo(yaml.dump(payload, default_flow_style=False))
        return

    table = Table(title=f"Indexed Optimizer Run {procedure_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Task", payload["task_id"])
    table.add_row("Manifest", payload["pointer"]["manifest"])
    table.add_row("Events", payload["pointer"]["events"])
    table.add_row("Runtime log", payload["pointer"]["runtime_log"])
    table.add_row("Completed cycles", str((payload["summary"] or {}).get("completed_cycles") or "—"))
    table.add_row("Winning version", (payload["best"] or {}).get("winning_version_id") or "—")
    table.add_row("Best feedback alignment evaluation", (payload["best"] or {}).get("best_feedback_evaluation_id") or "—")
    table.add_row("Best regression alignment evaluation", (payload["best"] or {}).get("best_accuracy_evaluation_id") or "—")
    console.print(table)


@procedure.command("optimizer-summary")
@click.argument("procedure_id")
@click.option("--runtime-log", is_flag=True, help="Include a runtime log excerpt")
@click.option("--events", is_flag=True, help="Include an events.jsonl excerpt")
@click.option("--log-lines", default=80, show_default=True, help="Number of trailing lines to include for excerpts")
@click.option("--output", "-o", type=click.Choice(["json", "yaml", "table"]), default="table", show_default=True)
def optimizer_summary(procedure_id: str, runtime_log: bool, events: bool, log_lines: int, output: str):
    """Summarize one indexed optimizer procedure and its candidate/evaluation history."""
    client = create_client()
    if not client:
        console.print("[red]Error: Could not create API client[/red]")
        return

    service = OptimizerResultsService(client)
    try:
        payload = service.summarize_optimizer_procedure(
            procedure_id,
            include_runtime_log=runtime_log,
            include_events=events,
            log_lines=log_lines,
        )
    except Exception as exc:
        console.print(f"[red]Error loading optimizer summary: {exc}[/red]")
        return

    if output == "json":
        click.echo(json.dumps(payload, indent=2, default=str))
        return
    if output == "yaml":
        click.echo(yaml.dump(payload, default_flow_style=False))
        return

    summary = payload.get("summary") or {}
    best = payload.get("best") or {}
    table = Table(title=f"Optimizer Summary {procedure_id}")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Status", str((payload.get("procedure") or {}).get("status") or "—"))
    table.add_row("Cycles", f"{summary.get('completed_cycles') or '—'}/{summary.get('configured_max_iterations') or '—'}")
    table.add_row("Stop reason", summary.get("stop_reason") or "—")
    table.add_row("Winning version", best.get("winning_version_id") or "—")
    table.add_row("Best feedback alignment evaluation", best.get("best_feedback_evaluation_url") or best.get("best_feedback_evaluation_id") or "—")
    table.add_row("Best regression alignment evaluation", best.get("best_accuracy_evaluation_url") or best.get("best_accuracy_evaluation_id") or "—")
    table.add_row("Manifest", (payload.get("artifact_pointer") or {}).get("manifest") or "—")
    table.add_row("Runtime log", (payload.get("artifact_pointer") or {}).get("runtime_log") or "—")
    console.print(table)

    cycles = Table(title="Cycles")
    cycles.add_column("Cycle", style="cyan")
    cycles.add_column("Status", style="white")
    cycles.add_column("Version", style="magenta")
    cycles.add_column("Feedback AC1", style="green")
    cycles.add_column("Regression AC1", style="green")
    for cycle in payload.get("cycles") or []:
        cycles.add_row(
            str(cycle.get("cycle") or "—"),
            str(cycle.get("status") or "—"),
            str(cycle.get("version_id") or "—"),
            f"{cycle['feedback_alignment']:.4f}" if cycle.get("feedback_alignment") is not None else "—",
            f"{cycle['accuracy_alignment']:.4f}" if cycle.get("accuracy_alignment") is not None else "—",
        )
    console.print(cycles)


# Add to CLI
if __name__ == "__main__":
    procedure()

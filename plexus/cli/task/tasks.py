import click
from typing import Optional, Dict, List
import rich.table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
from plexus.dashboard.api.models.task import Task
from plexus.dashboard.api.models.task_stage import TaskStage
from plexus.cli.shared.client_utils import create_client
from plexus.cli.shared.console import console
from plexus.cli.report.utils import resolve_account_id_for_command
import json

def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime with proper handling of None values"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"

def format_task_content(task: Task) -> Text:
    """Format task details into a rich text object"""
    content = Text()
    
    # Basic info using a table for alignment
    basic_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
    basic_table.add_column("Field", style="bold", width=20)  # Fixed width for alignment
    basic_table.add_column("Value")
    basic_table.add_row("ID:", task.id)
    basic_table.add_row("Account ID:", task.accountId)
    basic_table.add_row("Scorecard ID:", task.scorecardId if task.scorecardId else '-')
    basic_table.add_row("Score ID:", task.scoreId if task.scoreId else '-')
    basic_table.add_row("Type:", task.type)
    basic_table.add_row("Status:", task.status)
    basic_table.add_row("Target:", task.target)
    basic_table.add_row("Command:", task.command)
    basic_table.add_row("Current Stage:", task.currentStageId if task.currentStageId else '-')
    basic_table.add_row("Worker Node:", task.workerNodeId if task.workerNodeId else '-')
    basic_table.add_row("Dispatch Status:", task.dispatchStatus if task.dispatchStatus else '-')
    
    # Create a string buffer to capture table output
    from io import StringIO
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(basic_table)
    content.append(buffer.getvalue())
    
    # Timing information using a table
    content.append("\nTiming:\n", style="bold magenta")
    timing_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
    timing_table.add_column("Field", style="bold", width=20)  # Fixed width for alignment
    timing_table.add_column("Value")
    timing_table.add_row("Created:", format_datetime(task.createdAt))
    timing_table.add_row("Updated:", format_datetime(task.updatedAt))
    timing_table.add_row("Started:", format_datetime(task.startedAt))
    timing_table.add_row("Completed:", format_datetime(task.completedAt))
    timing_table.add_row("Est. Completion:", format_datetime(task.estimatedCompletionAt))
    
    # Use the same buffer technique for timing table
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(timing_table)
    content.append(buffer.getvalue())
    
    # Get and sort task stages
    stages = task.get_stages()
    if stages:
        content.append("\nStages:\n", style="bold cyan")
        # Sort stages by order
        sorted_stages = sorted(stages, key=lambda s: s.order if s.order is not None else float('inf'))
        
        for stage in sorted_stages:
            # Get status with color
            status_style = ""
            if stage.status == "RUNNING":
                status_style = "blue"
            elif stage.status == "COMPLETED":
                status_style = "green"
            elif stage.status == "FAILED":
                status_style = "red"
            elif stage.status == "PENDING":
                status_style = "yellow"
            
            # Create a table for each stage
            stage_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
            stage_table.add_column("Field", style="bold", width=20)
            stage_table.add_column("Value")
            
            # Add stage details
            stage_table.add_row("Stage:", stage.name)
            stage_table.add_row("Order:", str(stage.order if stage.order is not None else "-"))
            stage_table.add_row(
                "Status:", 
                f"[{status_style}]{stage.status}[/{status_style}]" if status_style else stage.status
            )
            
            # Add progress if available
            if stage.totalItems:
                processed = stage.processedItems if stage.processedItems is not None else 0
                stage_table.add_row("Progress:", f"{processed}/{stage.totalItems}")
            
            # Add timing information
            stage_table.add_row("Started:", format_datetime(stage.startedAt))
            stage_table.add_row("Completed:", format_datetime(stage.completedAt))
            if stage.estimatedCompletionAt:
                stage_table.add_row("Est. Completion:", format_datetime(stage.estimatedCompletionAt))
            
            # Add status message if present
            if stage.statusMessage:
                stage_table.add_row("Message:", stage.statusMessage)
            
            # Use the same buffer technique for stage table
            buffer = StringIO()
            console = rich.console.Console(file=buffer, force_terminal=False)
            console.print(stage_table)
            content.append(buffer.getvalue())
            content.append("\n")  # Add spacing between stages
    
    # Additional details
    if task.description:
        content.append("\nDescription: ", style="bold")
        content.append(f"{task.description}\n")
    
    if task.metadata:
        content.append("\nMetadata:\n", style="bold")
        try:
            # If metadata is already a dict, use it directly
            metadata = task.metadata if isinstance(task.metadata, dict) else json.loads(task.metadata)
            # Create a table for metadata
            metadata_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
            metadata_table.add_column("Key", style="bold", width=20)  # Fixed width for alignment
            metadata_table.add_column("Value")
            
            for key, value in metadata.items():
                if any(isinstance(value, t) for t in (Dict, List)):
                    # Pretty print nested structures with proper indentation
                    formatted_value = json.dumps(value, indent=2)
                    # Add indentation to each line after the first
                    indented_value = formatted_value.replace('\n', '\n    ')
                    metadata_table.add_row(key + ":", indented_value)
                else:
                    metadata_table.add_row(key + ":", str(value))
            
            # Use the same buffer technique for metadata table
            buffer = StringIO()
            console = rich.console.Console(file=buffer, force_terminal=False)
            console.print(metadata_table)
            content.append(buffer.getvalue())
        except (json.JSONDecodeError, AttributeError):
            # Fallback if metadata isn't valid JSON
            content.append(f"  {task.metadata}\n")
    
    # Error information if present
    if task.errorMessage or task.errorDetails:
        content.append("\nError Information:\n", style="bold red")
        error_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
        error_table.add_column("Field", style="bold", width=20)  # Fixed width for alignment
        error_table.add_column("Value")
        if task.errorMessage:
            error_table.add_row("Message:", task.errorMessage)
        if task.errorDetails:
            error_table.add_row("Details:", str(task.errorDetails))
        
        # Use the same buffer technique for error table
        buffer = StringIO()
        console = rich.console.Console(file=buffer, force_terminal=False)
        console.print(error_table)
        content.append(buffer.getvalue())
    
    # Universal Code Output if present
    if task.output:
        content.append("\nUniversal Code Output:\n", style="bold green")
        
        # Check if output is too long and provide a summary instead
        if len(task.output) > 800:
            # Show just the header and structure for long outputs
            lines = task.output.split('\n')
            
            # Take header comments and first few data lines
            header_lines = []
            data_lines = []
            in_header = True
            
            for line in lines:
                if line.strip().startswith('#') or line.strip() == '':
                    if in_header:
                        header_lines.append(line)
                elif in_header:
                    in_header = False
                    data_lines.append(line)
                elif len(data_lines) < 10:  # Show first 10 data lines
                    data_lines.append(line)
                else:
                    break
            
            # Combine header and limited data
            preview_content = '\n'.join(header_lines + data_lines)
            if len(data_lines) >= 10:
                preview_content += '\n\n# ... (output truncated - see attached files for complete data)\n'
                preview_content += f'# Total output size: {len(task.output)} characters\n'
                preview_content += f'# Full output available in attached files\n'
            
            content.append(f"{preview_content}\n")
        else:
            # Show full output for shorter content
            content.append(f"{task.output}\n")
    
    # Error output if present  
    if task.error:
        content.append("\nError Details:\n", style="bold red")
        error_preview = task.error[:1000] + "..." if len(task.error) > 1000 else task.error
        content.append(f"{error_preview}\n")
    
    # File attachments if present
    if task.attachedFiles:
        content.append("\nAttached Files:\n", style="bold cyan")
        for file_key in task.attachedFiles:
            content.append(f"  • {file_key}\n", style="dim")
    
    # Raw Output if present (stdout/stderr)
    if task.stdout or task.stderr:
        content.append("\nRaw Output:\n", style="bold")
        if task.stdout:
            content.append("  stdout:\n", style="dim")
            stdout_preview = task.stdout[:500] + "..." if len(task.stdout) > 500 else task.stdout
            content.append(f"{stdout_preview}\n")
        if task.stderr:
            content.append("  stderr:\n", style="dim")
            stderr_preview = task.stderr[:500] + "..." if len(task.stderr) > 500 else task.stderr
            content.append(f"{stderr_preview}\n")
    
    return content

@click.group()
def tasks():
    """Manage task records in the dashboard"""
    pass

@tasks.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--status', help='Filter by status (PENDING, RUNNING, COMPLETED, FAILED)')
@click.option('--type', help='Filter by task type')
@click.option('--limit', type=int, default=10, help='Number of records to show (default: 10)')
@click.option('--all', 'show_all', is_flag=True, help='Show all records')
def list(account: Optional[str], status: Optional[str], type: Optional[str], limit: int, show_all: bool):
    """List tasks with optional filtering"""
    client = create_client()
    
    # Resolve account ID using the same pattern as feedback commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Use the GSI for proper ordering
    query = f"""
    query ListTaskByAccountIdAndUpdatedAt($accountId: String!) {{
        listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC) {{
            items {{
                {Task.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query, {'accountId': account_id})
    tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])
    
    # Apply any remaining filters client-side
    if status:
        tasks = [t for t in tasks if t.get('status') == status]
    if type:
        tasks = [t for t in tasks if t.get('type') == type]
    
    if not tasks:
        console.print("[yellow]No tasks found matching the criteria[/yellow]")
        return
    
    # Apply limit unless --all is specified
    if not show_all:
        tasks = tasks[:limit]
        console.print(f"[dim]Showing {len(tasks)} most recent tasks. Use --all to show all records.[/dim]\n")
    else:
        console.print(f"[dim]Showing all {len(tasks)} tasks.[/dim]\n")
    
    # Print each task in its own panel
    for task_data in tasks:
        task = Task.from_dict(task_data, client)
        panel = Panel(
            format_task_content(task),
            title=f"[bold]{task.type} Task - {task.status}[/bold]",
            border_style="blue" if task.status == "RUNNING" else 
                        "green" if task.status == "COMPLETED" else
                        "red" if task.status == "FAILED" else
                        "yellow"
        )
        console.print(panel)
        console.print()  # Add spacing between panels

@tasks.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
def last(account: Optional[str]):
    """Show the most recent task for an account"""
    client = create_client()
    
    # Resolve account ID using the same pattern as feedback commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Use the GSI for proper ordering to get the most recent task
    query = f"""
    query ListTaskByAccountIdAndUpdatedAt($accountId: String!) {{
        listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
            items {{
                {Task.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query, {'accountId': account_id})
    tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])
    
    if not tasks:
        console.print("[yellow]No tasks found for this account[/yellow]")
        return
    
    # Get the most recent task
    task_data = tasks[0]
    task = Task.from_dict(task_data, client)
    
    # Display the task details
    panel = Panel(
        format_task_content(task),
        title=f"[bold]Most Recent Task: {task.type} - {task.status}[/bold]",
        border_style="blue" if task.status == "RUNNING" else 
                    "green" if task.status == "COMPLETED" else
                    "red" if task.status == "FAILED" else
                    "yellow"
    )
    console.print(panel)

@tasks.command()
@click.option('--task-id', help='Delete a specific task by ID')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--status', help='Delete tasks with specific status (PENDING, RUNNING, COMPLETED, FAILED)')
@click.option('--type', help='Delete tasks of specific type')
@click.option('--all', 'delete_all', is_flag=True, help='Delete all tasks (across all accounts if --account not specified)')
@click.option('-y', '--yes', is_flag=True, help='Skip confirmation prompt')
def delete(task_id: Optional[str], account: Optional[str], status: Optional[str], type: Optional[str], delete_all: bool, yes: bool):
    """Delete tasks and their stages.
    
    Requires --all flag to delete all tasks.
    Use -y/--yes to skip confirmation prompts.
    Always deletes associated TaskStage records.
    """
    client = create_client()
    
    # Validate deletion criteria
    if not any([task_id, status, type, delete_all]):
        console.print("[red]Error: Must specify either --task-id, --status, --type, or --all[/red]")
        return click.get_current_context().exit(1)
    
    account_id = None
    if not delete_all or account:
        # Resolve account ID if we need to filter by account
        account_id = resolve_account_id_for_command(client, account)
    
    # Query tasks based on account
    if account_id:
        query = f"""
        query ListTaskByAccountIdAndUpdatedAt($accountId: String!) {{
            listTaskByAccountIdAndUpdatedAt(accountId: $accountId, sortDirection: DESC) {{
                items {{
                    {Task.fields()}
                }}
            }}
        }}
        """
        result = client.execute(query, {'accountId': account_id})
        tasks = result.get('listTaskByAccountIdAndUpdatedAt', {}).get('items', [])
    else:
        # Query all tasks when no account specified
        query = f"""
        query ListTasks {{
            listTasks {{
                items {{
                    {Task.fields()}
                }}
            }}
        }}
        """
        result = client.execute(query)
        tasks = result.get('listTasks', {}).get('items', [])
    
    if not tasks:
        message = "No tasks found for the account" if account_id else "No tasks found"
        console.print(f"[yellow]{message}[/yellow]")
        return
    
    # Apply filters if not deleting all
    if not delete_all:
        if task_id:
            tasks = [t for t in tasks if t.get('id') == task_id]
        if status:
            tasks = [t for t in tasks if t.get('status') == status]
        if type:
            tasks = [t for t in tasks if t.get('type') == type]
    
    if not tasks:
        console.print("[yellow]No tasks found matching the criteria[/yellow]")
        return
    
    # Show tasks that will be deleted
    table = rich.table.Table(show_header=True, header_style="bold red")
    table.add_column("ID")
    table.add_column("Account ID")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Target")
    table.add_column("Command")
    
    for task_data in tasks:
        task = Task.from_dict(task_data, client)
        table.add_row(
            task.id,
            task.accountId,
            task.type,
            task.status,
            task.target,
            task.command
        )
    
    # Show warning for all tasks deletion
    if delete_all:
        scope = "ALL accounts" if not account else f"account {account or 'default'}"
        console.print(f"\n[bold red]⚠️  WARNING: You are about to delete ALL tasks for {scope}![/bold red]")
        console.print("[red]This action cannot be undone.[/red]\n")
    
    console.print("[bold red]The following tasks will be deleted:[/bold red]")
    console.print(table)
    console.print(f"\nTotal tasks to be deleted: [bold red]{len(tasks)}[/bold red]")
    
    # Get confirmation unless --yes is used
    if not yes:
        scope = "ALL accounts" if not account else f"this account"
        message = f"Are you absolutely sure you want to delete ALL tasks for {scope}?" if delete_all else "Are you sure you want to delete these tasks?"
        confirm = click.confirm(f"\n{message}", default=False)
        if not confirm:
            console.print("[yellow]Operation cancelled[/yellow]")
            return
    
    # Delete tasks and their stages
    deleted_count = 0
    stage_count = 0
    
    with click.progressbar(tasks, label='Deleting tasks') as progress_tasks:
        for task_data in progress_tasks:
            task = Task.from_dict(task_data, client)
            
            # First delete all stages
            stages = task.get_stages()
            for stage in stages:
                mutation = """
                mutation DeleteTaskStage($input: DeleteTaskStageInput!) {
                    deleteTaskStage(input: $input) {
                        id
                    }
                }
                """
                client.execute(mutation, {'input': {'id': stage.id}})
                stage_count += 1
            
            # Then delete the task
            mutation = """
            mutation DeleteTask($input: DeleteTaskInput!) {
                deleteTask(input: $input) {
                    id
                }
            }
            """
            client.execute(mutation, {'input': {'id': task.id}})
            deleted_count += 1
    
    console.print(f"\n[green]Successfully deleted {deleted_count} tasks and {stage_count} associated stages[/green]")

@tasks.command()
@click.option('--id', required=True, help='Task ID to get information for.')
def info(id: str):
    """Get detailed information about a specific task by its ID."""
    client = create_client()
    console.print(f"Fetching details for Task ID: [cyan]{id}[/cyan]")
    
    try:
        task = Task.get_by_id(id, client)
        if not task:
            console.print(f"[yellow]Task not found: {id}[/yellow]")
            return
        
        # Format and display task details using the existing helper
        task_content = format_task_content(task)
        console.print(Panel(task_content, title=f"Task Details: {task.id}", border_style="blue"))
        
    except Exception as e:
        console.print(f"[red]Error retrieving task {id}: {e}[/red]")
        # Optionally log the full traceback
        import traceback
        print(traceback.format_exc())

# Create an alias 'task' that's synonymous with 'tasks'
@click.group()
def task():
    """Manage task records in the dashboard (alias for 'tasks')"""
    pass

# Add all the same commands to the 'task' group
task.add_command(list)
task.add_command(last)
task.add_command(delete)
task.add_command(info) 
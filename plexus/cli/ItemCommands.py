import click
from typing import Optional, Dict, List
import rich.table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.cli.client_utils import create_client
from .console import console
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.cli.item_logic import (
    resolve_item, 
    insert_items, 
    upsert_items, 
    _process_item_folder
)
import json

def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime with proper handling of None values"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"

def format_item_content(item: Item) -> Text:
    """Format item details into a rich text object"""
    content = Text()
    
    # Basic info using a table for alignment
    basic_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
    basic_table.add_column("Field", style="bold", width=20)  # Fixed width for alignment
    basic_table.add_column("Value")
    basic_table.add_row("ID:", item.id)
    basic_table.add_row("Account ID:", item.accountId if item.accountId else '-')
    basic_table.add_row("Evaluation ID:", item.evaluationId if item.evaluationId else '-')
    basic_table.add_row("Score ID:", item.scoreId if item.scoreId else '-')
    basic_table.add_row("Description:", item.description if item.description else '-')
    basic_table.add_row("External ID:", item.externalId if item.externalId else '-')
    basic_table.add_row("Is Evaluation:", str(item.isEvaluation) if item.isEvaluation is not None else '-')
    
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
    timing_table.add_row("Created:", format_datetime(item.createdAt))
    timing_table.add_row("Updated:", format_datetime(item.updatedAt))
    
    # Use the same buffer technique for timing table
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(timing_table)
    content.append(buffer.getvalue())
    
    # Text content section
    if item.text:
        content.append("\nText Content:\n", style="bold cyan")
        # Truncate very long text for display
        display_text = item.text
        if len(display_text) > 500:
            display_text = display_text[:500] + "..."
        content.append(f"  {display_text}\n")
    
    # Metadata section
    if item.metadata:
        content.append("\nMetadata:\n", style="bold cyan")
        try:
            # Create a table for metadata
            metadata_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
            metadata_table.add_column("Key", style="bold", width=20)  # Fixed width for alignment
            metadata_table.add_column("Value")
            
            for key, value in item.metadata.items():
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
        except Exception:
            # Fallback if metadata isn't valid JSON
            content.append(f"  {item.metadata}\n")
    
    # Identifiers section
    if item.identifiers:
        content.append("\nIdentifiers:\n", style="bold yellow")
        try:
            # Create a table for identifiers
            identifiers_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
            identifiers_table.add_column("Key", style="bold", width=20)  # Fixed width for alignment
            identifiers_table.add_column("Value")
            
            for key, value in item.identifiers.items():
                if any(isinstance(value, t) for t in (Dict, List)):
                    # Pretty print nested structures with proper indentation
                    formatted_value = json.dumps(value, indent=2)
                    # Add indentation to each line after the first
                    indented_value = formatted_value.replace('\n', '\n    ')
                    identifiers_table.add_row(key + ":", indented_value)
                else:
                    identifiers_table.add_row(key + ":", str(value))
            
            # Use the same buffer technique for identifiers table
            buffer = StringIO()
            console = rich.console.Console(file=buffer, force_terminal=False)
            console.print(identifiers_table)
            content.append(buffer.getvalue())
        except Exception:
            # Fallback if identifiers isn't valid JSON
            content.append(f"  {item.identifiers}\n")
    
    # Attached files section
    if item.attachedFiles:
        content.append("\nAttached Files:\n", style="bold green")
        for i, file_path in enumerate(item.attachedFiles, 1):
            content.append(f"  {i}. {file_path}\n")
    
    return content

def get_score_results_for_item(item_id: str, client) -> List[ScoreResult]:
    """Get all score results for a specific item, sorted by updatedAt descending"""
    query = f"""
    query ListScoreResultByItemId($itemId: String!) {{
        listScoreResultByItemId(itemId: $itemId) {{
            items {{
                {ScoreResult.fields()}
                updatedAt
                createdAt
            }}
        }}
    }}
    """
    
    result = client.execute(query, {'itemId': item_id})
    score_results_data = result.get('listScoreResultByItemId', {}).get('items', [])
    
    # Convert to ScoreResult objects and add timestamp fields manually
    score_results = []
    for sr_data in score_results_data:
        score_result = ScoreResult.from_dict(sr_data, client)
        # Manually add timestamp fields that aren't in the standard fields
        if 'updatedAt' in sr_data:
            if isinstance(sr_data['updatedAt'], str):
                score_result.updatedAt = datetime.fromisoformat(
                    sr_data['updatedAt'].replace('Z', '+00:00')
                )
            else:
                score_result.updatedAt = sr_data['updatedAt']
        if 'createdAt' in sr_data:
            if isinstance(sr_data['createdAt'], str):
                score_result.createdAt = datetime.fromisoformat(
                    sr_data['createdAt'].replace('Z', '+00:00')
                )
            else:
                score_result.createdAt = sr_data['createdAt']
        score_results.append(score_result)
    
    # Sort by updatedAt in Python since GraphQL doesn't support it
    score_results.sort(key=lambda sr: getattr(sr, 'updatedAt', datetime.min), reverse=True)
    
    return score_results

def format_score_results_content(score_results: List[ScoreResult]) -> Text:
    """Format score results into a rich text object"""
    content = Text()
    
    if not score_results:
        content.append("No score results found for this item.\n", style="dim")
        return content
    
    content.append(f"\nScore Results ({len(score_results)} found):\n", style="bold green")
    
    # Create a table for score results
    results_table = rich.table.Table(show_header=True, box=rich.table.box.ROUNDED)
    results_table.add_column("Score Name", style="bold")
    results_table.add_column("Value", justify="right")
    results_table.add_column("Confidence", justify="right")
    results_table.add_column("Correct", justify="center")
    results_table.add_column("Scorecard ID")
    results_table.add_column("Evaluation ID")
    results_table.add_column("Updated")
    
    for sr in score_results:
        # Format value with appropriate precision
        numeric_val = getattr(sr, 'numeric_value', None)
        if numeric_val is None:
            # Fallback: try to convert value directly if numeric_value property doesn't exist
            try:
                numeric_val = float(sr.value) if sr.value is not None else None
            except (ValueError, TypeError):
                numeric_val = None
        value_str = f"{numeric_val:.3f}" if numeric_val is not None else "N/A"
        
        # Format confidence with appropriate precision
        confidence_str = f"{sr.confidence:.3f}" if sr.confidence is not None else "N/A"
        
        # Format correct status with colors
        correct_str = "N/A"
        correct_style = ""
        if sr.correct is not None:
            if sr.correct:
                correct_str = "✓"
                correct_style = "green"
            else:
                correct_str = "✗"
                correct_style = "red"
        
        # Format updated time
        updated_str = format_datetime(getattr(sr, 'updatedAt', None))
        
        results_table.add_row(
            sr.scoreName if sr.scoreName else (sr.scoreId[:8] + "..." if sr.scoreId else "N/A"),
            value_str,
            confidence_str,
            f"[{correct_style}]{correct_str}[/{correct_style}]" if correct_style else correct_str,
            sr.scorecardId[:8] + "..." if sr.scorecardId else "N/A",
            sr.evaluationId[:8] + "..." if sr.evaluationId else "N/A",
            updated_str
        )
    
    # Use the same buffer technique
    from io import StringIO
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(results_table)
    content.append(buffer.getvalue())
    
    return content

@click.group()
def items():
    """Manage item records in the dashboard"""
    pass

@items.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--evaluation-id', help='Evaluation ID for the item (required for evaluation items)')
@click.option('--score-id', help='Score ID for the item')
@click.option('--text', help='Text content of the item')
@click.option('--metadata', help='Metadata for the item as a JSON string')
@click.option('--identifiers', help='Identifiers for the item as a JSON string')
@click.option('--external-id', help='External ID for the item')
@click.option('--description', help='Description for the item')
@click.option('--is-evaluation/--is-prediction', 'is_evaluation', default=False, help='Flag to mark item as for evaluation or prediction (default: prediction)')
@click.option('--attached-files', help='Comma-separated list of attached file paths')
def create(account: Optional[str], evaluation_id: Optional[str], score_id: Optional[str], text: Optional[str],
           metadata: Optional[str], identifiers: Optional[str], external_id: Optional[str],
           description: Optional[str], is_evaluation: bool, attached_files: Optional[str]):
    """Create a new item."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)

    if not account_id:
        console.print("[red]Account ID is required. Provide with --account or set PLEXUS_ACCOUNT_ID.[/red]")
        return

    if is_evaluation and not evaluation_id:
        console.print("[red]--evaluation-id is required for evaluation items.[/red]")
        return

    # The create method in the model handles setting a default for prediction items if evaluationId is None
    if not is_evaluation and not evaluation_id:
        evaluation_id = None

    kwargs = {
        'accountId': account_id,
        'isEvaluation': is_evaluation,
    }

    if score_id:
        kwargs['scoreId'] = score_id
    if external_id:
        kwargs['externalId'] = external_id
    if description:
        kwargs['description'] = description

    item_metadata = None
    if metadata:
        try:
            item_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON format for --metadata.[/red]")
            return
    
    if identifiers:
        try:
            kwargs['identifiers'] = json.loads(identifiers)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON format for --identifiers.[/red]")
            return

    if attached_files:
        kwargs['attachedFiles'] = [f.strip() for f in attached_files.split(',')]

    try:
        console.print(f"Creating new item...")
        
        new_item = Item.create(
            client=client,
            evaluationId=evaluation_id,
            text=text,
            metadata=item_metadata,
            **kwargs
        )
        
        console.print(f"[green]Successfully created item with ID: {new_item.id}[/green]")
        panel = Panel(
            format_item_content(new_item),
            title=f"[bold]New Item {new_item.id[:8]}...[/bold]",
            border_style="cyan"
        )
        console.print(panel)

    except Exception as e:
        console.print(f"[red]Error creating item: {e}[/red]")
        import traceback
        print(traceback.format_exc())

@items.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--evaluation-id', help='Filter by evaluation ID')
@click.option('--limit', type=int, default=10, help='Number of records to show (default: 10)')
@click.option('--all', 'show_all', is_flag=True, help='Show all records')
def list(account: Optional[str], evaluation_id: Optional[str], limit: int, show_all: bool):
    """List items with optional filtering, ordered by created timestamp (most recent first)"""
    client = create_client()
    
    # Resolve account ID using the same pattern as other commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Use the GSI for proper ordering by account and createdAt
    query = f"""
    query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
        listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC) {{
            items {{
                {Item.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query, {'accountId': account_id})
    items = result.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
    
    # Apply any remaining filters client-side
    if evaluation_id:
        items = [i for i in items if i.get('evaluationId') == evaluation_id]
    
    if not items:
        console.print("[yellow]No items found matching the criteria[/yellow]")
        return
    
    # Apply limit unless --all is specified
    if not show_all:
        items = items[:limit]
        console.print(f"[dim]Showing {len(items)} most recent items. Use --all to show all records.[/dim]\n")
    else:
        console.print(f"[dim]Showing all {len(items)} items.[/dim]\n")
    
    # Print each item in its own panel
    for item_data in items:
        item = Item.from_dict(item_data, client)
        panel = Panel(
            format_item_content(item),
            title=f"[bold]Item {item.id[:8]}...[/bold]",
            border_style="cyan"
        )
        console.print(panel)
        console.print()  # Add spacing between panels

@items.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--show-score-results', is_flag=True, help='Show all score results for this item')
def last(account: Optional[str], show_score_results: bool):
    """Show the most recent item for an account"""
    client = create_client()
    
    # Resolve account ID using the same pattern as other commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Use the GSI for proper ordering to get the most recent item
    query = f"""
    query ListItemByAccountIdAndCreatedAt($accountId: String!) {{
        listItemByAccountIdAndCreatedAt(accountId: $accountId, sortDirection: DESC, limit: 1) {{
            items {{
                {Item.fields()}
            }}
        }}
    }}
    """
    
    result = client.execute(query, {'accountId': account_id})
    items = result.get('listItemByAccountIdAndCreatedAt', {}).get('items', [])
    
    if not items:
        console.print("[yellow]No items found for this account[/yellow]")
        return
    
    # Get the most recent item
    item_data = items[0]
    item = Item.from_dict(item_data, client)
    
    # Format item content
    item_content = format_item_content(item)
    
    # Get score results if requested
    if show_score_results:
        score_results = get_score_results_for_item(item.id, client)
        score_results_content = format_score_results_content(score_results)
        item_content.append(score_results_content)
    
    # Display the item details
    panel = Panel(
        item_content,
        title=f"[bold]Most Recent Item: {item.id[:8]}...[/bold]",
        border_style="cyan"
    )
    console.print(panel)

@items.command()
@click.option('--item', 'item_identifier', required=True, help='Item ID, external ID, or identifier to get information for.')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--show-score-results', is_flag=True, help='Show all score results for this item')
def info(item_identifier: str, account: Optional[str], show_score_results: bool):
    """Get detailed information about a specific item by its ID, external ID, or identifier."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)
    console.print(f"Fetching details for Item: [cyan]{item_identifier}[/cyan]")
    
    try:
        item = resolve_item(client, account_id, item_identifier)
        if not item:
            console.print(f"[yellow]Item not found: {item_identifier}[/yellow]")
            return
        
        # Format item content
        item_content = format_item_content(item)
        
        # Get score results if requested
        if show_score_results:
            score_results = get_score_results_for_item(item.id, client)
            score_results_content = format_score_results_content(score_results)
            item_content.append(score_results_content)
        
        # Format and display item details
        console.print(Panel(item_content, title=f"Item Details: {item.id}", border_style="cyan"))
        
    except Exception as e:
        console.print(f"[red]Error retrieving item {item_identifier}: {e}[/red]")
        # Optionally log the full traceback
        import traceback
        print(traceback.format_exc())

@items.command()
@click.option('--item', 'item_identifier', required=True, help='Item ID, external ID, or identifier to update.')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--text', help='New text content of the item')
@click.option('--metadata', help='New metadata for the item as a JSON string')
@click.option('--description', help='New description for the item')
@click.option('--attached-files', help='New comma-separated list of attached file paths')
def update(item_identifier: str, account: Optional[str], text: Optional[str], metadata: Optional[str], description: Optional[str], attached_files: Optional[str]):
    """Update an existing item."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)

    item = resolve_item(client, account_id, item_identifier)
    if not item:
        console.print(f"[red]Item '{item_identifier}' not found.[/red]")
        return

    update_kwargs = {}
    if text is not None:
        update_kwargs['text'] = text
    if description is not None:
        update_kwargs['description'] = description
    if attached_files is not None:
        update_kwargs['attachedFiles'] = [f.strip() for f in attached_files.split(',')]
    if metadata is not None:
        try:
            update_kwargs['metadata'] = json.loads(metadata)
        except json.JSONDecodeError:
            console.print("[red]Invalid JSON format for --metadata.[/red]")
            return

    if not update_kwargs:
        console.print("[yellow]No fields to update.[/yellow]")
        return

    try:
        updated_item = item.update(**update_kwargs)
        console.print(f"[green]Successfully updated item {updated_item.id}[/green]")
        panel = Panel(
            format_item_content(updated_item),
            title=f"[bold]Updated Item {updated_item.id[:8]}...[/bold]",
            border_style="cyan"
        )
        console.print(panel)
    except Exception as e:
        console.print(f"[red]Error updating item: {e}[/red]")

@items.command()
@click.option('--item', 'item_identifier', required=True, help='Item ID, external ID, or identifier to delete.')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.confirmation_option(prompt='Are you sure you want to delete this item?')
def delete(item_identifier: str, account: Optional[str]):
    """Delete an item."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)

    item = resolve_item(client, account_id, item_identifier)
    if not item:
        console.print(f"[red]Item '{item_identifier}' not found.[/red]")
        return

    try:
        item.delete()
        console.print(f"[green]Successfully deleted item {item.id}[/green]")
    except Exception as e:
        console.print(f"[red]Error deleting item: {e}[/red]")

@items.command()
@click.option('--item', 'item_path_glob', required=True, help='Path to item folder(s), can include wildcards.')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--evaluation-id', help='Evaluation ID for the item(s)')
@click.option('--score-id', help='Score ID for the item(s)')
@click.option('--is-evaluation/--is-prediction', 'is_evaluation', default=False, help='Flag to mark item as for evaluation or prediction (default: prediction)')
def insert(item_path_glob: str, account: Optional[str], evaluation_id: Optional[str], score_id: Optional[str], is_evaluation: bool):
    """Insert one or more items from folder paths."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)

    if not account_id:
        console.print("[red]Account ID is required. Provide with --account or set PLEXUS_ACCOUNT_ID.[/red]")
        return

    results = insert_items(client, account_id, item_path_glob, evaluation_id, score_id, is_evaluation)

    for result in results:
        if result['status'] == 'success':
            console.print(f"[green]Successfully inserted item with ID: {result['item'].id}[/green]")
        else:
            console.print(f"[red]Error inserting item from {result['path']}: {result['message']}[/red]")

@items.command()
@click.option('--item', 'item_path_glob', required=True, help='Path to item folder(s), can include wildcards.')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--evaluation-id', help='Evaluation ID for the item(s)')
@click.option('--score-id', help='Score ID for the item(s)')
@click.option('--is-evaluation/--is-prediction', 'is_evaluation', default=False, help='Flag to mark item as for evaluation or prediction (default: prediction)')
def upsert(item_path_glob: str, account: Optional[str], evaluation_id: Optional[str], score_id: Optional[str], is_evaluation: bool):
    """Upsert one or more items from folder paths."""
    client = create_client()
    account_id = resolve_account_id_for_command(client, account)

    if not account_id:
        console.print("[red]Account ID is required. Provide with --account or set PLEXUS_ACCOUNT_ID.[/red]")
        return

    results = upsert_items(client, account_id, item_path_glob, evaluation_id, score_id, is_evaluation)

    for result in results:
        if result['status'] == 'inserted':
            console.print(f"[green]Successfully inserted item with ID: {result['item'].id}[/green]")
        elif result['status'] == 'updated':
            console.print(f"[green]Successfully updated item {result['item'].id}[/green]")
        else:
            console.print(f"[red]Error upserting item from {result['path']}: {result['message']}[/red]")

# Create an alias 'item' that's synonymous with 'items'
@click.group()
def item():
    """Manage item records in the dashboard (alias for 'items')"""
    pass

# Add all the same commands to the 'item' group
item.add_command(create)
item.add_command(list)
item.add_command(last)
item.add_command(info)
item.add_command(update)
item.add_command(delete)
item.add_command(insert)
item.add_command(upsert)

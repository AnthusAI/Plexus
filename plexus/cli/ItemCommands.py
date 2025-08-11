import click
from typing import Optional, Dict, List
import rich.table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
from plexus.dashboard.api.models.item import Item
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.models.feedback_item import FeedbackItem
from plexus.dashboard.api.models.identifier import Identifier
from plexus.cli.client_utils import create_client
from .console import console
from plexus.cli.reports.utils import resolve_account_id_for_command
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
    basic_table.add_row("Created By Type:", item.createdByType if item.createdByType else '-')
    
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
                if any(isinstance(value, t) for t in (dict, list)):
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
                if any(isinstance(value, t) for t in (dict, list)):
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
                cost
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
        # Attach cost if API returns it or embed from metadata
        try:
            if 'cost' in sr_data and sr_data['cost'] is not None:
                setattr(score_result, 'cost', sr_data['cost'])
            elif isinstance(score_result.metadata, dict) and 'cost' in score_result.metadata:
                setattr(score_result, 'cost', score_result.metadata['cost'])
        except Exception:
            pass
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
    """Format score results into a rich text object using simple formatting"""
    content = Text()
    
    if not score_results:
        content.append("No score results found for this item.\n", style="dim")
        return content
    
    content.append(f"\nScore Results ({len(score_results)} found):\n", style="bold green")
    
    for i, sr in enumerate(score_results, 1):
        # Format value - display string values as-is, format numeric values with precision
        if sr.value is not None:
            try:
                numeric_val = float(sr.value)
                value_str = f"{numeric_val:.3f}"
            except (ValueError, TypeError):
                value_str = str(sr.value)
        else:
            value_str = "N/A"
        
        # Format confidence with appropriate precision
        confidence_str = f"{sr.confidence:.3f}" if sr.confidence is not None else "N/A"
        
        # Format correct status with colors
        correct_str = "N/A"
        if sr.correct is not None:
            if sr.correct:
                correct_str = "✓"
            else:
                correct_str = "✗"
        
        # Score header
        score_name = sr.scoreName if sr.scoreName else (sr.scoreId[:8] + "..." if sr.scoreId else f"Score {i}")
        content.append(f"\n  [{i}] {score_name}\n", style="bold cyan")
        
        # Score details
        content.append(f"    Value: {value_str}\n", style="white")
        content.append(f"    Confidence: {confidence_str}\n")
        content.append(f"    Correct: {correct_str}\n")
        content.append(f"    Updated: {format_datetime(getattr(sr, 'updatedAt', None))}\n")
        
        # Add metadata if available
        if sr.scorecardId:
            content.append(f"    Scorecard ID: {sr.scorecardId[:8]}...\n", style="dim")
        if sr.evaluationId:
            content.append(f"    Evaluation ID: {sr.evaluationId[:8]}...\n", style="dim")
        
        # Add cost if available
        cost_value = getattr(sr, 'cost', None)
        if cost_value is None and isinstance(sr.metadata, dict):
            cost_value = sr.metadata.get('cost')
        if cost_value is not None:
            content.append("    Cost:\n", style="bold blue")
            try:
                import json as _json
                content.append("      " + _json.dumps(cost_value, indent=2) + "\n", style="dim")
            except Exception:
                content.append(f"      {cost_value}\n", style="dim")

        # Add explanation if available
        if sr.explanation and sr.explanation.strip():
            content.append("    Explanation:\n", style="bold blue")
            explanation_lines = sr.explanation.strip().split('\n')
            for line in explanation_lines:
                if line.strip():
                    content.append(f"      {line}\n", style="dim")
                else:
                    content.append("\n")
    
    return content

def get_feedback_items_for_item(item_id: str, client) -> List[FeedbackItem]:
    """Get all feedback items for a specific item, sorted by updatedAt descending"""
    try:
        feedback_items, _ = FeedbackItem.list(
            client=client,
            filter={'itemId': {'eq': item_id}},
            limit=1000
        )
        # Sort by updatedAt descending
        feedback_items.sort(key=lambda fi: getattr(fi, 'updatedAt', datetime.min), reverse=True)
        return feedback_items
    except Exception as e:
        console.print(f"[red]Error retrieving feedback items for {item_id}: {e}[/red]")
        return []

def format_feedback_items_content(feedback_items: List[FeedbackItem]) -> Text:
    """Format feedback items into a rich text object"""
    content = Text()
    
    if not feedback_items:
        content.append("No feedback items found for this item.\n", style="dim")
        return content
    
    content.append(f"\nFeedback Items ({len(feedback_items)} found):\n", style="bold green")
    
    # Create a table for feedback items
    feedback_table = rich.table.Table(show_header=True, box=rich.table.box.ROUNDED)
    feedback_table.add_column("Cache Key", style="bold")
    feedback_table.add_column("Score ID")
    feedback_table.add_column("Initial Answer", justify="left")
    feedback_table.add_column("Final Answer", justify="left")
    feedback_table.add_column("Agreement", justify="center")
    feedback_table.add_column("Editor", justify="left")
    feedback_table.add_column("Updated")
    
    for fi in feedback_items:
        # Format agreement with colors
        agreement_str = "N/A"
        agreement_style = ""
        if fi.isAgreement is not None:
            if fi.isAgreement:
                agreement_str = "✓"
                agreement_style = "green"
            else:
                agreement_str = "✗"
                agreement_style = "red"
        
        # Truncate long text fields
        initial_answer = (fi.initialAnswerValue[:30] + "...") if fi.initialAnswerValue and len(fi.initialAnswerValue) > 30 else (fi.initialAnswerValue or "N/A")
        final_answer = (fi.finalAnswerValue[:30] + "...") if fi.finalAnswerValue and len(fi.finalAnswerValue) > 30 else (fi.finalAnswerValue or "N/A")
        
        feedback_table.add_row(
            fi.cacheKey or "N/A",
            fi.scoreId[:8] + "..." if fi.scoreId else "N/A",
            initial_answer,
            final_answer,
            f"[{agreement_style}]{agreement_str}[/{agreement_style}]" if agreement_style else agreement_str,
            fi.editorName or "N/A",
            format_datetime(getattr(fi, 'updatedAt', None))
        )
    
    # Use the same buffer technique
    from io import StringIO
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(feedback_table)
    content.append(buffer.getvalue())
    
    return content

def find_item_by_any_identifier(client, identifier_value: str, account_id: str) -> Optional[Item]:
    """Find an item using any identifier - can be ID, external ID, or identifier values"""
    # Try direct ID lookup first
    try:
        item = Item.get_by_id(identifier_value, client)
        if item and item.accountId == account_id:
            return item
    except Exception:
        pass
    
    # Try external ID lookup
    try:
        items = Item.list(
            client=client,
            filter={
                'and': [
                    {'accountId': {'eq': account_id}},
                    {'externalId': {'eq': identifier_value}}
                ]
            },
            limit=1
        )
        if items:
            return items[0]
    except Exception:
        pass
    
    # Try identifier lookup using the Identifier model
    try:
        identifier = Identifier.find_by_value(identifier_value, account_id, client)
        if identifier:
            return Item.get_by_id(identifier.itemId, client)
    except Exception:
        pass
    
    return None

@click.group()
def items():
    """Manage item records in the dashboard"""
    pass

@items.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--evaluation-id', help='Evaluation ID (optional, defaults to "prediction-default" for non-evaluation items)')
@click.option('--text', help='Text content for the item')
@click.option('--description', help='Description for the item')
@click.option('--external-id', help='External ID for the item')
@click.option('--metadata', help='JSON metadata for the item')
@click.option('--identifiers', help='JSON identifiers for the item (e.g., {"formId": "123", "reportId": "456"})')
@click.option('--is-evaluation', is_flag=True, default=False, help='Mark this as an evaluation item')
@click.option('--score-id', help='Associated score ID')
def create(account: Optional[str], evaluation_id: Optional[str], text: Optional[str], 
          description: Optional[str], external_id: Optional[str], metadata: Optional[str], 
          identifiers: Optional[str], is_evaluation: bool, score_id: Optional[str]):
    """Create a new item"""
    client = create_client()
    
    # Resolve account ID
    account_id = resolve_account_id_for_command(client, account)
    
    try:
        # Parse JSON fields if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON format for metadata[/red]")
                return
        
        parsed_identifiers = None
        if identifiers:
            try:
                parsed_identifiers = json.loads(identifiers)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON format for identifiers[/red]")
                return
        
        # Use upsert_by_identifiers if identifiers are provided for deduplication
        if parsed_identifiers:
            item_id, was_created, error = Item.upsert_by_identifiers(
                client=client,
                account_id=account_id,
                identifiers=parsed_identifiers,
                external_id=external_id,
                description=description,
                text=text,
                metadata=parsed_metadata,
                evaluation_id=evaluation_id,
                is_evaluation=is_evaluation
            )
            
            if error:
                console.print(f"[red]Error creating item: {error}[/red]")
                return
            
            if was_created:
                console.print(f"[green]Successfully created item: {item_id}[/green]")
            else:
                console.print(f"[yellow]Item already exists, updated: {item_id}[/yellow]")
            
            # Show the created/updated item details
            item = Item.get_by_id(item_id, client)
            if item:
                panel = Panel(
                    format_item_content(item),
                    title=f"[bold]{'Created' if was_created else 'Updated'} Item: {item.id[:8]}...[/bold]",
                    border_style="green" if was_created else "yellow"
                )
                console.print(panel)
        else:
            # Direct creation without deduplication
            create_kwargs = {
                'accountId': account_id,
                'isEvaluation': is_evaluation
            }
            
            if external_id:
                create_kwargs['externalId'] = external_id
            if description:
                create_kwargs['description'] = description
            if score_id:
                create_kwargs['scoreId'] = score_id
            
            item = Item.create(
                client=client,
                evaluationId=evaluation_id or ('prediction-default' if not is_evaluation else 'evaluation-default'),
                text=text,
                metadata=parsed_metadata,
                **create_kwargs
            )
            
            console.print(f"[green]Successfully created item: {item.id}[/green]")
            
            # Show the created item details
            panel = Panel(
                format_item_content(item),
                title=f"[bold]Created Item: {item.id[:8]}...[/bold]",
                border_style="green"
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
@click.option('--minimal', is_flag=True, help='Show minimal info without score results and feedback items')
def last(account: Optional[str], minimal: bool):
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
    
    # Get score results and feedback items by default (unless minimal mode)
    if not minimal:
        score_results = get_score_results_for_item(item.id, client)
        score_results_content = format_score_results_content(score_results)
        item_content.append(score_results_content)
        
        feedback_items = get_feedback_items_for_item(item.id, client)
        feedback_items_content = format_feedback_items_content(feedback_items)
        item_content.append(feedback_items_content)
    
    # Display the item details
    panel = Panel(
        item_content,
        title=f"[bold]Most Recent Item: {item.id[:8]}...[/bold]",
        border_style="cyan"
    )
    console.print(panel)

@items.command()
@click.option('--id', help='Item identifier - can be ID, external ID, or any identifier value')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--minimal', is_flag=True, help='Show minimal info without score results and feedback items')
@click.argument('identifier', required=False)
def info(id: Optional[str], account: Optional[str], minimal: bool, identifier: Optional[str]):
    """Get detailed information about a specific item by any identifier.
    
    Can search by:
    - Item ID (direct lookup)
    - External ID (within account)
    - Any identifier value (formId, reportId, etc.)
    
    Usage:
      plexus items info --id <identifier>
      plexus items info <identifier>  (shorthand)
    """
    client = create_client()
    
    # Use either --id option or positional argument
    search_id = id or identifier
    if not search_id:
        console.print("[red]Error: Please provide an identifier using --id or as an argument[/red]")
        return
    
    # Resolve account ID
    account_id = resolve_account_id_for_command(client, account)
    
    console.print(f"Searching for Item with identifier: [cyan]{search_id}[/cyan]")
    
    try:
        # Use the flexible lookup function
        item = find_item_by_any_identifier(client, search_id, account_id)
        
        if not item:
            console.print(f"[yellow]Item not found with identifier: {search_id}[/yellow]")
            console.print("[dim]Tried: direct ID lookup, external ID lookup, and identifier value lookup[/dim]")
            return
        
        # Format item content
        item_content = format_item_content(item)
        
        # Get score results and feedback items by default (unless minimal mode)
        if not minimal:
            score_results = get_score_results_for_item(item.id, client)
            score_results_content = format_score_results_content(score_results)
            item_content.append(score_results_content)
            
            feedback_items = get_feedback_items_for_item(item.id, client)
            feedback_items_content = format_feedback_items_content(feedback_items)
            item_content.append(feedback_items_content)
        
        # Format and display item details
        console.print(Panel(item_content, title=f"Item Details: {item.id}", border_style="cyan"))
        
    except Exception as e:
        console.print(f"[red]Error retrieving item with identifier {search_id}: {e}[/red]")
        import traceback
        print(traceback.format_exc())

@items.command()
@click.option('--id', help='Item identifier - can be ID, external ID, or any identifier value')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--text', help='Update text content for the item')
@click.option('--description', help='Update description for the item')
@click.option('--external-id', help='Update external ID for the item')
@click.option('--metadata', help='Update JSON metadata for the item')
@click.option('--score-id', help='Update associated score ID')
@click.argument('identifier', required=False)
def update(id: Optional[str], account: Optional[str], text: Optional[str], 
          description: Optional[str], external_id: Optional[str], metadata: Optional[str], 
          score_id: Optional[str], identifier: Optional[str]):
    """Update an existing item
    
    Usage:
      plexus items update --id <identifier> --text "New text"
      plexus items update <identifier> --text "New text"  (shorthand)
    """
    client = create_client()
    
    # Use either --id option or positional argument
    search_id = id or identifier
    if not search_id:
        console.print("[red]Error: Please provide an identifier using --id or as an argument[/red]")
        return
    
    # Resolve account ID
    account_id = resolve_account_id_for_command(client, account)
    
    try:
        # Find the item
        item = find_item_by_any_identifier(client, search_id, account_id)
        
        if not item:
            console.print(f"[yellow]Item not found with identifier: {search_id}[/yellow]")
            return
        
        # Parse metadata if provided
        parsed_metadata = None
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                console.print("[red]Invalid JSON format for metadata[/red]")
                return
        
        # Build update kwargs
        update_kwargs = {}
        if text is not None:
            update_kwargs['text'] = text
        if description is not None:
            update_kwargs['description'] = description
        if external_id is not None:
            update_kwargs['externalId'] = external_id
        if parsed_metadata is not None:
            update_kwargs['metadata'] = parsed_metadata
        if score_id is not None:
            update_kwargs['scoreId'] = score_id
        
        if not update_kwargs:
            console.print("[yellow]No updates specified. Use options like --text, --description, etc.[/yellow]")
            return
        
        # Perform the update
        console.print(f"Updating item: [cyan]{item.id}[/cyan]")
        updated_item = item.update(**update_kwargs)
        
        console.print(f"[green]Successfully updated item: {updated_item.id}[/green]")
        
        # Show the updated item details
        panel = Panel(
            format_item_content(updated_item),
            title=f"[bold]Updated Item: {updated_item.id[:8]}...[/bold]",
            border_style="green"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error updating item: {e}[/red]")
        import traceback
        print(traceback.format_exc())

@items.command()
@click.option('--id', help='Item identifier - can be ID, external ID, or any identifier value')
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--force', is_flag=True, help='Force deletion without confirmation')
@click.argument('identifier', required=False)
def delete(id: Optional[str], account: Optional[str], force: bool, identifier: Optional[str]):
    """Delete an item
    
    Usage:
      plexus items delete --id <identifier>
      plexus items delete <identifier>  (shorthand)
    """
    client = create_client()
    
    # Use either --id option or positional argument
    search_id = id or identifier
    if not search_id:
        console.print("[red]Error: Please provide an identifier using --id or as an argument[/red]")
        return
    
    # Resolve account ID
    account_id = resolve_account_id_for_command(client, account)
    
    try:
        # Find the item
        item = find_item_by_any_identifier(client, search_id, account_id)
        
        if not item:
            console.print(f"[yellow]Item not found with identifier: {search_id}[/yellow]")
            return
        
        # Show item details before deletion
        console.print(f"Found item to delete: [cyan]{item.id}[/cyan]")
        panel = Panel(
            format_item_content(item),
            title=f"[bold]Item to Delete: {item.id[:8]}...[/bold]",
            border_style="red"
        )
        console.print(panel)
        
        # Confirm deletion unless --force is used
        if not force:
            import click
            if not click.confirm(f"Are you sure you want to delete item {item.id}?"):
                console.print("[yellow]Deletion cancelled[/yellow]")
                return
        
        # Perform the deletion
        mutation = """
        mutation DeleteItem($input: DeleteItemInput!) {
            deleteItem(input: $input) {
                id
            }
        }
        """
        
        result = client.execute(mutation, {'input': {'id': item.id}})
        
        if result and 'deleteItem' in result and result['deleteItem']:
            console.print(f"[green]Successfully deleted item: {item.id}[/green]")
        else:
            console.print(f"[red]Failed to delete item: {item.id}[/red]")
            console.print(f"Response: {result}")
        
    except Exception as e:
        console.print(f"[red]Error deleting item: {e}[/red]")
        import traceback
        print(traceback.format_exc())

@items.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--file', 'json_file', help='JSON file containing item data or array of items')
@click.option('--data', help='JSON string containing item data or array of items')
@click.option('--evaluation-id', help='Default evaluation ID for items (optional)')
@click.option('--is-evaluation', is_flag=True, default=False, help='Mark items as evaluation items')
@click.option('--dry-run', is_flag=True, help='Show what would be processed without actually upserting')
@click.option('--batch-size', type=int, default=10, help='Number of items to process in each batch (default: 10)')
def upsert(account: Optional[str], json_file: Optional[str], data: Optional[str], 
          evaluation_id: Optional[str], is_evaluation: bool, dry_run: bool, batch_size: int):
    """Upsert items from JSON file or data
    
    Supports:
    - Single item: {"text": "content", "metadata": {...}, "identifiers": {...}}
    - Array of items: [{"text": "content1", ...}, {"text": "content2", ...}]
    
    Required fields in each item:
    - text: The text content
    - identifiers: Dict with identifier values (e.g., {"formId": "123", "reportId": "456"})
    
    Optional fields:
    - metadata: Dict with metadata
    - description: Item description
    - externalId: External ID
    - evaluationId: Override default evaluation ID
    - isEvaluation: Override default evaluation flag
    - scoreId: Associated score ID
    
    Examples:
      plexus items upsert --file items.json
      plexus items upsert --data '{"text": "test", "identifiers": {"formId": "123"}}'
      plexus items upsert --file bulk_items.json --batch-size 50 --dry-run
    """
    client = create_client()
    
    # Resolve account ID
    account_id = resolve_account_id_for_command(client, account)
    
    # Get JSON data
    json_data = None
    if json_file:
        try:
            with open(json_file, 'r') as f:
                json_data = json.load(f)
            console.print(f"[green]Loaded data from file: {json_file}[/green]")
        except FileNotFoundError:
            console.print(f"[red]File not found: {json_file}[/red]")
            return
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON in file {json_file}: {e}[/red]")
            return
    elif data:
        try:
            json_data = json.loads(data)
            console.print("[green]Loaded data from command line[/green]")
        except json.JSONDecodeError as e:
            console.print(f"[red]Invalid JSON data: {e}[/red]")
            return
    else:
        console.print("[red]Error: Must provide either --file or --data[/red]")
        return
    
    # Normalize to array
    import builtins
    if isinstance(json_data, dict):
        items_data = [json_data]
    elif isinstance(json_data, builtins.list):
        items_data = json_data
    else:
        console.print("[red]Error: JSON data must be an object or array of objects[/red]")
        return
    
    if not items_data:
        console.print("[yellow]No items found in data[/yellow]")
        return
    
    console.print(f"[cyan]Processing {len(items_data)} items in batches of {batch_size}[/cyan]")
    
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No changes will be made[/yellow]")
    
    # Process items in batches
    success_count = 0
    error_count = 0
    updated_count = 0
    created_count = 0
    
    for batch_start in range(0, len(items_data), batch_size):
        batch_end = min(batch_start + batch_size, len(items_data))
        batch = items_data[batch_start:batch_end]
        
        console.print(f"\n[bold]Processing batch {batch_start//batch_size + 1} ({batch_start + 1}-{batch_end} of {len(items_data)})[/bold]")
        
        for i, item_data in enumerate(batch, batch_start + 1):
            try:
                # Validate required fields
                if 'text' not in item_data:
                    console.print(f"[red]Item {i}: Missing required 'text' field[/red]")
                    error_count += 1
                    continue
                
                if 'identifiers' not in item_data or not item_data['identifiers']:
                    console.print(f"[red]Item {i}: Missing required 'identifiers' field[/red]")
                    error_count += 1
                    continue
                
                # Extract item fields
                text = item_data['text']
                identifiers = item_data['identifiers']
                metadata = item_data.get('metadata')
                description = item_data.get('description')
                external_id = item_data.get('externalId')
                item_evaluation_id = item_data.get('evaluationId', evaluation_id)
                item_is_evaluation = item_data.get('isEvaluation', is_evaluation)
                score_id = item_data.get('scoreId')
                
                # Show what we would process
                identifiers_str = ', '.join([f"{k}={v}" for k, v in identifiers.items()])
                console.print(f"  Item {i}: [cyan]{identifiers_str}[/cyan] - {text[:50]}{'...' if len(text) > 50 else ''}")
                
                if dry_run:
                    console.print(f"    [dim]Would upsert with: description={description}, metadata={'Yes' if metadata else 'No'}[/dim]")
                    success_count += 1
                    continue
                
                # Perform the upsert
                item_id, was_created, error = Item.upsert_by_identifiers(
                    client=client,
                    account_id=account_id,
                    identifiers=identifiers,
                    external_id=external_id,
                    description=description,
                    text=text,
                    metadata=metadata,
                    evaluation_id=item_evaluation_id,
                    is_evaluation=item_is_evaluation
                )
                
                if error:
                    console.print(f"    [red]Error: {error}[/red]")
                    error_count += 1
                else:
                    if was_created:
                        console.print(f"    [green]Created: {item_id}[/green]")
                        created_count += 1
                    else:
                        console.print(f"    [yellow]Updated: {item_id}[/yellow]")
                        updated_count += 1
                    success_count += 1
                    
                    # Update score ID if provided and different
                    if score_id:
                        try:
                            item = Item.get_by_id(item_id, client)
                            if item and item.scoreId != score_id:
                                item.update(scoreId=score_id)
                                console.print(f"    [cyan]Updated scoreId: {score_id}[/cyan]")
                        except Exception as e:
                            console.print(f"    [yellow]Warning: Could not update scoreId: {e}[/yellow]")
                
            except Exception as e:
                console.print(f"    [red]Unexpected error processing item {i}: {e}[/red]")
                error_count += 1
                import traceback
                print(traceback.format_exc())
    
    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    if dry_run:
        console.print(f"  [cyan]Would process: {success_count} items[/cyan]")
        console.print(f"  [red]Errors: {error_count} items[/red]")
    else:
        console.print(f"  [green]Created: {created_count} items[/green]")
        console.print(f"  [yellow]Updated: {updated_count} items[/yellow]")
        console.print(f"  [cyan]Total processed: {success_count} items[/cyan]")
        console.print(f"  [red]Errors: {error_count} items[/red]")

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
item.add_command(upsert)
item.add_command(delete) 
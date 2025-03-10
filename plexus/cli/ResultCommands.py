import click
from typing import Optional, List, Dict, Any
import rich.table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
import json
from datetime import datetime
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.dashboard.api.client import PlexusDashboardClient
from .console import console

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    return PlexusDashboardClient()

def format_datetime(dt: Optional[datetime]) -> str:
    """Format datetime with proper handling of None values"""
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "N/A"

def resolve_scorecard_identifier(client, identifier):
    """Resolve a scorecard identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetScorecard {{
            getScorecard(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getScorecard'):
            return identifier
    except:
        pass
    
    # Try lookup by key
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by externalId
    try:
        query = f"""
        query ListScorecards {{
            listScorecards(filter: {{ externalId: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScorecards', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

def resolve_account_identifier(client, identifier):
    """Resolve an account identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetAccount {{
            getAccount(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getAccount'):
            return identifier
    except:
        pass
    
    # Try lookup by key
    try:
        query = f"""
        query ListAccounts {{
            listAccounts(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listAccounts', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListAccounts {{
            listAccounts(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listAccounts', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

def format_score_result(result_data: Dict[str, Any]) -> Panel:
    """
    Format a score result into a rich panel with full-width display.
    
    Args:
        result_data: Dictionary containing score result data
        
    Returns:
        A rich Panel object containing the formatted score result
    """
    content = Text()
    
    # Basic info using a table for alignment
    basic_table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
    basic_table.add_column("Field", style="bold", width=20)  # Fixed width for alignment
    basic_table.add_column("Value")
    
    # Add all the basic fields
    basic_table.add_row("ID:", result_data.get('id', 'N/A'))
    basic_table.add_row("Value:", str(result_data.get('value', 'N/A')))
    basic_table.add_row("Confidence:", str(result_data.get('confidence', 'N/A')))
    basic_table.add_row("Correct:", str(result_data.get('correct', 'N/A')))
    basic_table.add_row("Item ID:", result_data.get('itemId', 'N/A'))
    basic_table.add_row("Account ID:", result_data.get('accountId', 'N/A'))
    basic_table.add_row("Scorecard ID:", result_data.get('scorecardId', 'N/A'))
    basic_table.add_row("Scoring Job ID:", result_data.get('scoringJobId', 'N/A') or 'N/A')
    basic_table.add_row("Evaluation ID:", result_data.get('evaluationId', 'N/A') or 'N/A')
    
    # Add timestamps if available
    if result_data.get('createdAt'):
        created_at = datetime.fromisoformat(result_data['createdAt'].replace('Z', '+00:00'))
        basic_table.add_row("Created At:", format_datetime(created_at))
    
    if result_data.get('updatedAt'):
        updated_at = datetime.fromisoformat(result_data['updatedAt'].replace('Z', '+00:00'))
        basic_table.add_row("Updated At:", format_datetime(updated_at))
    
    # Create a string buffer to capture table output
    from io import StringIO
    buffer = StringIO()
    console = rich.console.Console(file=buffer, force_terminal=False)
    console.print(basic_table)
    content.append(buffer.getvalue())
    
    # Helper function to parse and format JSON data
    def format_json_data(data, field_name, style="bold magenta"):
        if not data:
            return
            
        # Add the field header with proper styling and a divider line
        content.append("\n")
        
        # Create a divider line with the field name
        divider = "─" * 5 + f" {field_name} " + "─" * 40
        content.append(divider, style=style)
        content.append("\n")
        
        # Handle string data (needs parsing)
        if isinstance(data, str):
            try:
                # Check if the data is a JSON string with escaped quotes
                if data.startswith('"') and data.endswith('"'):
                    # Remove the outer quotes and unescape the inner quotes
                    data = data[1:-1].replace('\\"', '"')
                
                # Parse the JSON string
                parsed_data = json.loads(data)
                
                # Use Rich's JSON formatter for pretty display with proper indentation
                json_str = json.dumps(parsed_data, indent=4)
                content.append(json_str)
            except json.JSONDecodeError:
                content.append(str(data))
        # Handle dict data
        elif data is not None:
            # Convert to properly indented JSON string
            json_str = json.dumps(data, indent=4)
            content.append(json_str)
    
    # Format metadata if present
    format_json_data(result_data.get('metadata'), "METADATA", "bold cyan")
    
    # Format trace if present
    trace_data = result_data.get('trace')
    if trace_data:
        # Add extra whitespace before the trace section for better separation
        content.append("\n\n")  # Two newlines for extra spacing
        
        # Create a divider line with the field name
        divider = "─" * 5 + " TRACE " + "─" * 40
        content.append(divider, style="bold green")
        content.append("\n")
        
        # Handle string data (needs parsing)
        if isinstance(trace_data, str):
            try:
                # Check if the data is a JSON string with escaped quotes
                if trace_data.startswith('"') and trace_data.endswith('"'):
                    # Remove the outer quotes and unescape the inner quotes
                    trace_data = trace_data[1:-1].replace('\\"', '"')
                
                # Parse the JSON string
                parsed_data = json.loads(trace_data)
                
                # Use Rich's JSON formatter for pretty display with proper indentation
                json_str = json.dumps(parsed_data, indent=4)
                content.append(json_str)
            except json.JSONDecodeError:
                content.append(str(trace_data))
        # Handle dict data
        elif trace_data is not None:
            # Convert to properly indented JSON string
            json_str = json.dumps(trace_data, indent=4)
            content.append(json_str)
    
    # Add explanation if present
    explanation = result_data.get('explanation')
    if explanation:
        content.append("\n")
        divider = "─" * 5 + " EXPLANATION " + "─" * 40
        content.append(divider, style="bold yellow")
        content.append("\n")
        content.append(explanation)
    
    # Create a panel with the result ID as the title
    panel = Panel(
        content,
        title=f"Score Result: {result_data.get('id')}",
        expand=False,
        border_style="blue"
    )
    
    return panel

@click.group()
def results():
    """Manage score result records in the dashboard"""
    pass

@results.command()
@click.option('--scorecard', help='Filter by scorecard (accepts ID, name, key, or external ID)')
@click.option('--account', help='Filter by account (accepts ID, name, or key)')
@click.option('--limit', type=int, default=10, help='Number of records to show (default: 10)')
def list(scorecard: Optional[str], account: Optional[str], limit: int):
    """List score results with optional filtering"""
    client = create_client()
    
    # Require either scorecard or account
    if not scorecard and not account:
        console.print("[bold red]Error:[/bold red] You must specify either --scorecard or --account")
        return
    
    # Resolve scorecard ID if provided
    scorecard_id = None
    if scorecard:
        scorecard_id = resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
    
    # Resolve account ID if provided
    account_id = None
    if account:
        account_id = resolve_account_identifier(client, account)
        if not account_id:
            console.print(f"[bold red]Error:[/bold red] No account found with identifier: {account}")
            return
    
    # Build the query based on filters
    if scorecard_id:
        # Use the GSI for scorecard-specific results
        query = f"""
        query ListScoreResultByScorecardId($scorecardId: String!, $limit: Int!) {{
            listScoreResultByScorecardId(
                scorecardId: $scorecardId, 
                limit: $limit
            ) {{
                items {{
                    id
                    value
                    confidence
                    correct
                    itemId
                    accountId
                    scorecardId
                    scoringJobId
                    evaluationId
                    metadata
                    trace
                    explanation
                    updatedAt
                    createdAt
                }}
            }}
        }}
        """
        variables = {
            'scorecardId': scorecard_id,
            'limit': limit
        }
        
        console.print(f"[dim]Fetching results for scorecard {scorecard_id}...[/dim]")
        response = client.execute(query, variables)
        results = response.get('listScoreResultByScorecardId', {}).get('items', [])
        
        # Sort results by updatedAt in descending order
        results.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        
    elif account_id:
        # Use the GSI for account-specific results with updatedAt sorting
        query = f"""
        query ListScoreResultByAccountIdAndUpdatedAt($accountId: String!, $limit: Int!) {{
            listScoreResultByAccountIdAndUpdatedAt(
                accountId: $accountId, 
                sortDirection: DESC,
                limit: $limit
            ) {{
                items {{
                    id
                    value
                    confidence
                    correct
                    itemId
                    accountId
                    scorecardId
                    scoringJobId
                    evaluationId
                    metadata
                    trace
                    explanation
                    updatedAt
                    createdAt
                }}
            }}
        }}
        """
        variables = {
            'accountId': account_id,
            'limit': limit
        }
        
        console.print(f"[dim]Fetching most recent results for account {account_id}...[/dim]")
        response = client.execute(query, variables)
        results = response.get('listScoreResultByAccountIdAndUpdatedAt', {}).get('items', [])
    
    # Display results
    if not results:
        console.print("[yellow]No score results found.[/yellow]")
        return
    
    # Print a header with the count
    console.print(f"[bold]Score Results[/bold] ({len(results)} items)\n")
    
    # Display each result as a panel
    for result in results:
        panel = format_score_result(result)
        console.print(panel)
        console.print()  # Add a blank line between panels

@results.command()
@click.option('--id', required=True, help='Score result ID to get info about')
def info(id: str):
    """Get detailed information about a specific score result"""
    client = create_client()
    
    # Query for the specific score result
    query = f"""
    query GetScoreResult($id: ID!) {{
        getScoreResult(id: $id) {{
            id
            value
            confidence
            correct
            itemId
            accountId
            scorecardId
            scoringJobId
            evaluationId
            metadata
            trace
            explanation
            updatedAt
            createdAt
        }}
    }}
    """
    
    try:
        response = client.execute(query, {'id': id})
        result = response.get('getScoreResult')
        
        if not result:
            console.print(f"[bold red]Error:[/bold red] No score result found with ID: {id}")
            return
        
        # Format and display the result using the shared formatting function
        panel = format_score_result(result)
        console.print(panel)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}") 
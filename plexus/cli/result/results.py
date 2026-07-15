import click
from typing import Optional, List, Dict, Any
import rich.table
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.json import JSON
import json
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from plexus.dashboard.api.models.score_result import ScoreResult
from plexus.cli.shared.client_utils import create_client
from plexus.cli.report.utils import resolve_account_id_for_command
from plexus.cli.shared.console import console
from plexus.utils.dependency_snapshots import check_score_result_dependency_snapshot_current

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


def resolve_score_identifier(client, scorecard_id: str, identifier: str) -> Optional[str]:
    """Resolve a score identifier to its dashboard ID within a scorecard."""

    try:
        query = """
        query GetScore($id: ID!) {
            getScore(id: $id) {
                id
                scorecardId
            }
        }
        """
        result = client.execute(query, {"id": identifier})
        score = result.get("getScore")
        if score and score.get("scorecardId") == scorecard_id:
            return score.get("id")
    except Exception:
        pass

    query = """
    query ListScores($filter: ModelScoreFilterInput, $limit: Int) {
        listScores(filter: $filter, limit: $limit) {
            items {
                id
                name
                key
                externalId
                scorecardId
            }
        }
    }
    """
    for field in ("key", "name", "externalId", "id"):
        try:
            response = client.execute(
                query,
                {
                    "filter": {
                        "scorecardId": {"eq": scorecard_id},
                        field: {"eq": identifier},
                    },
                    "limit": 1,
                },
            )
            items = response.get("listScores", {}).get("items", []) or []
            if items:
                return items[0].get("id")
        except Exception:
            continue
    return None


def _json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _fetch_recent_score_results_for_dependency_audit(
    *,
    client,
    account_id: str,
    scorecard_id: str,
    score_id: str,
    days: int,
    limit: int,
) -> List[Dict[str, Any]]:
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    query = """
    query ListScoreResultsByScorecardAndUpdatedAt(
        $scorecardId: String!,
        $startTime: String!,
        $endTime: String!,
        $accountId: String!,
        $scoreId: String!,
        $limit: Int,
        $nextToken: String
    ) {
        listScoreResultByScorecardIdAndUpdatedAt(
            scorecardId: $scorecardId,
            updatedAt: { between: [$startTime, $endTime] },
            filter: {
                accountId: { eq: $accountId },
                scoreId: { eq: $scoreId },
                type: { eq: "prediction" }
            },
            sortDirection: DESC,
            limit: $limit,
            nextToken: $nextToken
        ) {
            items {
                id
                value
                explanation
                itemId
                accountId
                scorecardId
                scoreId
                scoreVersionId
                metadata
                trace
                type
                status
                createdAt
                updatedAt
            }
            nextToken
        }
    }
    """
    collected: List[Dict[str, Any]] = []
    next_token = None
    while len(collected) < limit:
        response = client.execute(
            query,
            {
                "scorecardId": scorecard_id,
                "startTime": start_time.isoformat(),
                "endTime": end_time.isoformat(),
                "accountId": account_id,
                "scoreId": score_id,
                "limit": min(500, limit - len(collected)),
                "nextToken": next_token,
            },
        )
        payload = response.get("listScoreResultByScorecardIdAndUpdatedAt", {}) or {}
        collected.extend(payload.get("items", []) or [])
        next_token = payload.get("nextToken")
        if not next_token:
            break
    return collected[:limit]


async def _audit_dependency_snapshots(client, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    audited = []
    for row in rows:
        score_result = ScoreResult.from_dict(row, client)
        check = await check_score_result_dependency_snapshot_current(
            score_result=score_result,
            client=client,
            item_id=score_result.itemId,
            account_id=score_result.accountId,
        )
        status = "match"
        if not check.get("has_dependency_snapshot"):
            status = "no_snapshot"
        elif not check.get("matches", True):
            status = "mismatch"

        metadata = _json_object(row.get("metadata"))
        trace = _json_object(row.get("trace"))
        snapshot = trace.get("dependency_snapshot_v1") or metadata.get("dependency_snapshot_v1") or {}
        audited.append({
            "status": status,
            "reason": check.get("reason"),
            "score_result_id": row.get("id"),
            "item_id": row.get("itemId"),
            "score_id": row.get("scoreId"),
            "score_version_id": row.get("scoreVersionId"),
            "value": row.get("value"),
            "updated_at": row.get("updatedAt"),
            "snapshot_hash": check.get("snapshot_hash") or snapshot.get("hash"),
            "current_snapshot_hash": check.get("current_snapshot_hash"),
            "dependency_score_result_ids": [
                dependency.get("score_result_id")
                for dependency in snapshot.get("dependencies", [])
                if isinstance(dependency, dict)
            ],
        })
    return audited

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
def score_results():
    """Manage score result records in the dashboard"""
    pass

@score_results.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--scorecard', help='Filter by scorecard (accepts ID, name, key, or external ID)')
@click.option('--limit', type=int, default=10, help='Number of records to show (default: 10)')
@click.option('--all', 'show_all', is_flag=True, help='Show all records')
def list(account: Optional[str], scorecard: Optional[str], limit: int, show_all: bool):
    """List score results with optional filtering, ordered by updated timestamp (most recent first)"""
    client = create_client()
    
    # Resolve account ID using the same pattern as other commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Resolve scorecard ID if provided
    scorecard_id = None
    if scorecard:
        scorecard_id = resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
    
    # Build the query based on filters
    if scorecard_id:
        # Use the GSI for scorecard-specific results
        query = f"""
        query ListScoreResultByScorecardId($scorecardId: String!) {{
            listScoreResultByScorecardId(scorecardId: $scorecardId) {{
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
        variables = {'scorecardId': scorecard_id}
        
        console.print(f"[dim]Fetching results for scorecard {scorecard_id}...[/dim]")
        response = client.execute(query, variables)
        results = response.get('listScoreResultByScorecardId', {}).get('items', [])
        
        # Sort results by updatedAt in descending order (most recent first)
        results.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        
    else:
        # Use the GSI for account-specific results with updatedAt sorting
        query = f"""
        query ListScoreResultByAccountIdAndUpdatedAt($accountId: String!) {{
            listScoreResultByAccountIdAndUpdatedAt(
                accountId: $accountId, 
                sortDirection: DESC
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
        variables = {'accountId': account_id}
        
        console.print(f"[dim]Fetching most recent results for account {account_id}...[/dim]")
        response = client.execute(query, variables)
        results = response.get('listScoreResultByAccountIdAndUpdatedAt', {}).get('items', [])
    
    if not results:
        console.print("[yellow]No score results found matching the criteria[/yellow]")
        return
    
    # Apply limit unless --all is specified
    if not show_all:
        results = results[:limit]
        console.print(f"[dim]Showing {len(results)} most recent score results. Use --all to show all records.[/dim]\n")
    else:
        console.print(f"[dim]Showing all {len(results)} score results.[/dim]\n")
    
    # Display each result as a panel
    for result in results:
        panel = format_score_result(result)
        console.print(panel)
        console.print()  # Add a blank line between panels

@score_results.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--scorecard', help='Filter by scorecard (accepts ID, name, key, or external ID)')
def last(account: Optional[str], scorecard: Optional[str]):
    """Show the most recent score result for an account"""
    client = create_client()
    
    # Resolve account ID using the same pattern as other commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Resolve scorecard ID if provided
    scorecard_id = None
    if scorecard:
        scorecard_id = resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
    
    # Build the query based on filters
    if scorecard_id:
        # Use the GSI for scorecard-specific results
        query = f"""
        query ListScoreResultByScorecardId($scorecardId: String!) {{
            listScoreResultByScorecardId(scorecardId: $scorecardId, limit: 1) {{
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
        variables = {'scorecardId': scorecard_id}
        
        response = client.execute(query, variables)
        results = response.get('listScoreResultByScorecardId', {}).get('items', [])
        
        # Sort results by updatedAt in descending order and take the first one
        results.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        
    else:
        # Use the GSI for account-specific results with updatedAt sorting
        query = f"""
        query ListScoreResultByAccountIdAndUpdatedAt($accountId: String!) {{
            listScoreResultByAccountIdAndUpdatedAt(
                accountId: $accountId, 
                sortDirection: DESC,
                limit: 1
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
        variables = {'accountId': account_id}
        
        response = client.execute(query, variables)
        results = response.get('listScoreResultByAccountIdAndUpdatedAt', {}).get('items', [])
    
    if not results:
        console.print("[yellow]No score results found for this account[/yellow]")
        return
    
    # Get the most recent result
    result = results[0]
    
    # Display the result
    panel = format_score_result(result)
    console.print(Panel(
        panel.renderable,
        title=f"[bold]Most Recent Score Result: {result.get('id')}[/bold]",
        border_style="cyan"
    ))


@score_results.command(name="audit-dependencies")
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Computed/dependent score identifier (ID, name, key, or external ID)')
@click.option('--days', type=int, default=7, show_default=True, help='Updated-at window to inspect')
@click.option('--limit', type=int, default=100, show_default=True, help='Maximum score results to audit')
@click.option('--output', type=click.Choice(["table", "json"]), default="table", show_default=True)
def audit_dependencies(
    account: Optional[str],
    scorecard: str,
    score: str,
    days: int,
    limit: int,
    output: str,
):
    """Audit dependency snapshots for recent computed ScoreResults."""

    client = create_client()
    account_id = resolve_account_id_for_command(client, account)
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        raise click.ClickException(f"No scorecard found with identifier: {scorecard}")

    score_id = resolve_score_identifier(client, scorecard_id, score)
    if not score_id:
        raise click.ClickException(f"No score found with identifier '{score}' in scorecard {scorecard_id}")

    rows = _fetch_recent_score_results_for_dependency_audit(
        client=client,
        account_id=account_id,
        scorecard_id=scorecard_id,
        score_id=score_id,
        days=days,
        limit=limit,
    )
    audited = asyncio.run(_audit_dependency_snapshots(client, rows))

    summary = {
        "scorecard_id": scorecard_id,
        "score_id": score_id,
        "days": days,
        "limit": limit,
        "total": len(audited),
        "match": sum(1 for row in audited if row["status"] == "match"),
        "mismatch": sum(1 for row in audited if row["status"] == "mismatch"),
        "no_snapshot": sum(1 for row in audited if row["status"] == "no_snapshot"),
        "rows": audited,
    }

    if output == "json":
        click.echo(json.dumps(summary, indent=2, default=str))
        return

    table = rich.table.Table(title="Dependency Snapshot Audit")
    table.add_column("Status")
    table.add_column("ScoreResult")
    table.add_column("Item")
    table.add_column("Value")
    table.add_column("Updated")
    table.add_column("Reason")
    table.add_column("Snapshot Hash")
    table.add_column("Current Hash")
    for row in audited:
        style = "green" if row["status"] == "match" else "yellow" if row["status"] == "no_snapshot" else "red"
        table.add_row(
            row["status"],
            row.get("score_result_id") or "",
            row.get("item_id") or "",
            str(row.get("value") or ""),
            row.get("updated_at") or "",
            row.get("reason") or "",
            (row.get("snapshot_hash") or "")[:12],
            (row.get("current_snapshot_hash") or "")[:12],
            style=style,
        )
    console.print(table)
    console.print(
        f"[bold]Total:[/bold] {summary['total']}  "
        f"[green]match:[/green] {summary['match']}  "
        f"[red]mismatch:[/red] {summary['mismatch']}  "
        f"[yellow]no_snapshot:[/yellow] {summary['no_snapshot']}"
    )


@score_results.command()
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
            attachments
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

@score_results.command()
@click.option('--id', required=True, help='Score result ID to delete')
@click.option('--confirm', is_flag=True, help='Skip confirmation prompt')
def delete(id: str, confirm: bool):
    """Delete a specific score result by ID"""
    client = create_client()
    
    if not confirm:
        # Get the score result first to show what we're about to delete
        try:
            query = f"""
            query GetScoreResult($id: ID!) {{
                getScoreResult(id: $id) {{
                    id
                    value
                    accountId
                    scorecardId
                    itemId
                    updatedAt
                    createdAt
                }}
            }}
            """
            response = client.execute(query, {'id': id})
            result = response.get('getScoreResult')
            
            if not result:
                console.print(f"[bold red]Error:[/bold red] No score result found with ID: {id}")
                return
                
            console.print(f"[bold yellow]About to delete score result:[/bold yellow]")
            console.print(f"  ID: {result['id']}")
            console.print(f"  Value: {result['value']}")
            console.print(f"  Account: {result['accountId']}")
            console.print(f"  Scorecard: {result['scorecardId']}")
            console.print(f"  Item: {result['itemId']}")
            console.print(f"  Created: {result.get('createdAt', 'N/A')}")
            
            if not click.confirm("Are you sure you want to delete this score result?"):
                console.print("[yellow]Deletion cancelled.[/yellow]")
                return
                
        except Exception as e:
            console.print(f"[bold red]Error getting score result info:[/bold red] {str(e)}")
            return
    
    # Perform the deletion
    try:
        mutation = f"""
        mutation DeleteScoreResult($id: ID!) {{
            deleteScoreResult(input: {{ id: $id }}) {{
                id
            }}
        }}
        """
        
        response = client.execute(mutation, {'id': id})
        deleted_result = response.get('deleteScoreResult')
        
        if deleted_result:
            console.print(f"[bold green]Successfully deleted score result:[/bold green] {deleted_result['id']}")
        else:
            console.print(f"[bold red]Error:[/bold red] Failed to delete score result {id}")
            
    except Exception as e:
        console.print(f"[bold red]Error deleting score result:[/bold red] {str(e)}")

@score_results.command()
@click.option('--account', help='Account key or ID (optional, uses default from environment if not provided)')
@click.option('--scorecard', help='Scorecard identifier (accepts ID, name, key, or external ID)')
@click.option('--score-id', help='Score ID to associate with the error score result')
@click.option('--item-id', help='Item ID to associate with the error score result')
@click.option('--count', type=int, default=1, help='Number of error score results to create (default: 1)')
@click.option('--value', default='Error', help='Value for the error score result (default: "Error")')
@click.option('--code', default='500', help='HTTP response code for the error (default: "500")')
def create_error(account: Optional[str], scorecard: Optional[str], score_id: Optional[str], item_id: Optional[str], count: int, value: str, code: str):
    """Create test score results with error codes for testing error detection (temporary command)"""
    client = create_client()
    
    # Resolve account ID using the same pattern as other commands
    account_id = resolve_account_id_for_command(client, account)
    
    # Resolve scorecard ID if provided, otherwise use a default or create a dummy one
    scorecard_id = None
    if scorecard:
        scorecard_id = resolve_scorecard_identifier(client, scorecard)
        if not scorecard_id:
            console.print(f"[bold red]Error:[/bold red] No scorecard found with identifier: {scorecard}")
            return
    else:
        # If no scorecard specified, try to find the first available scorecard for this account
        try:
            query = f"""
            query ListScorecards($accountId: String!) {{
                listScorecardByAccountId(accountId: $accountId, limit: 1) {{
                    items {{
                        id
                        name
                    }}
                }}
            }}
            """
            response = client.execute(query, {'accountId': account_id})
            scorecards = response.get('listScorecardByAccountId', {}).get('items', [])
            
            if scorecards:
                scorecard_id = scorecards[0]['id']
                console.print(f"[dim]Using first available scorecard: {scorecards[0]['name']} ({scorecard_id})[/dim]")
            else:
                console.print(f"[bold red]Error:[/bold red] No scorecards found for account {account_id}. Please specify a scorecard or create one first.")
                return
                
        except Exception as e:
            console.print(f"[bold red]Error finding scorecard:[/bold red] {str(e)}")
            return
    
    # Resolve score ID if provided, otherwise try to find one but don't fail if none exists
    if not score_id:
        try:
            query = f"""
            query ListScores($scorecardId: String!) {{
                listScores(filter: {{ scorecardId: {{ eq: $scorecardId }} }}, limit: 1) {{
                    items {{
                        id
                        name
                    }}
                }}
            }}
            """
            response = client.execute(query, {'scorecardId': scorecard_id})
            scores = response.get('listScores', {}).get('items', [])
            
            if scores:
                score_id = scores[0]['id']
                console.print(f"[dim]Using first available score: {scores[0]['name']} ({score_id})[/dim]")
            else:
                console.print(f"[dim]No scores found for scorecard {scorecard_id}. Creating a dummy score to satisfy GSI constraints.[/dim]")
                # Create a dummy score to satisfy the GSI constraints
                try:
                    # First, we need a scorecard section
                    section_query = f"""
                    query ListSections($scorecardId: String!) {{
                        listScorecardSections(filter: {{ scorecardId: {{ eq: $scorecardId }} }}, limit: 1) {{
                            items {{
                                id
                                name
                            }}
                        }}
                    }}
                    """
                    section_response = client.execute(section_query, {'scorecardId': scorecard_id})
                    sections = section_response.get('listScorecardSections', {}).get('items', [])
                    
                    section_id = None
                    if sections:
                        section_id = sections[0]['id']
                        console.print(f"[dim]Using existing section: {sections[0]['name']} ({section_id})[/dim]")
                    else:
                        # Create a dummy section first
                        console.print(f"[dim]Creating dummy section for scorecard[/dim]")
                        create_section_mutation = f"""
                        mutation CreateSection($input: CreateScorecardSectionInput!) {{
                            createScorecardSection(input: $input) {{
                                id
                                name
                            }}
                        }}
                        """
                        
                        section_input = {
                            'name': 'Test Section (DELETE ME)',
                            'order': 999,
                            'scorecardId': scorecard_id
                        }
                        
                        section_response = client.execute(create_section_mutation, {'input': section_input})
                        created_section = section_response.get('createScorecardSection')
                        
                        if created_section:
                            section_id = created_section['id']
                            console.print(f"[dim]Created dummy section: {created_section['name']} ({section_id})[/dim]")
                        else:
                            console.print(f"[yellow]Could not create dummy section, will try without scoreId anyway[/yellow]")
                    
                    # Now create a dummy score if we have a section
                    if section_id:
                        create_score_mutation = f"""
                        mutation CreateScore($input: CreateScoreInput!) {{
                            createScore(input: $input) {{
                                id
                                name
                            }}
                        }}
                        """
                        
                        score_input = {
                            'name': 'Test Score (DELETE ME)',
                            'order': 999,
                            'type': 'test',
                            'sectionId': section_id,
                            'scorecardId': scorecard_id,
                            'externalId': f'test-score-{uuid.uuid4()}'
                        }
                        
                        score_response = client.execute(create_score_mutation, {'input': score_input})
                        created_score = score_response.get('createScore')
                        
                        if created_score:
                            score_id = created_score['id']
                            console.print(f"[dim]Created dummy score: {created_score['name']} ({score_id})[/dim]")
                        else:
                            console.print(f"[yellow]Could not create dummy score[/yellow]")
                            
                except Exception as e:
                    console.print(f"[yellow]Warning: Could not create dummy score ({str(e)}). Will try without scoreId.[/yellow]")
                
        except Exception as e:
            console.print(f"[yellow]Warning: Error finding score ({str(e)}). Creating ScoreResult without scoreId.[/yellow]")
    
    # Create a test Item first if we need one
    if not item_id:
        item_id = str(uuid.uuid4())
        console.print(f"[dim]Creating test Item with ID: {item_id}[/dim]")
        
        # Create the test Item first
        try:
            create_item_mutation = f"""
            mutation CreateItem($input: CreateItemInput!) {{
                createItem(input: $input) {{
                    id
                }}
            }}
            """
            
            item_input = {
                'id': item_id,
                'accountId': account_id,
                'evaluationId': 'prediction-default',  # Required for GSI
                'isEvaluation': False,
                'createdByType': 'prediction',  # CLI-created test items are predictions
                'description': 'Test item created for error ScoreResult testing (delete when done)',
                'externalId': f'test-error-item-{item_id[:8]}',
                'createdAt': datetime.now(timezone.utc).isoformat(),
                'updatedAt': datetime.now(timezone.utc).isoformat(),
                'createdByType': 'prediction'
            }
            
            response = client.execute(create_item_mutation, {'input': item_input})
            created_item = response.get('createItem')
            
            if created_item:
                console.print(f"[dim]Created test Item: {created_item['id']}[/dim]")
            else:
                console.print(f"[bold red]Error:[/bold red] Failed to create test Item")
                return
                
        except Exception as e:
            console.print(f"[bold red]Error creating test Item:[/bold red] {str(e)}")
            return
    
    console.print(f"[bold yellow]Creating {count} error score result(s) with code {code}...[/bold yellow]")
    console.print(f"[dim]Item ID: {item_id}[/dim]")
    console.print(f"[dim]HTTP Code: {code}[/dim]")
    if score_id:
        console.print(f"[dim]Score ID: {score_id}[/dim]")
    
    # Create the error score results
    created_count = 0
    for i in range(count):
        try:
            now = datetime.now(timezone.utc).isoformat()
            
            mutation = f"""
            mutation CreateScoreResult($input: CreateScoreResultInput!) {{
                createScoreResult(input: $input) {{
                    id
                    value
                    code
                    accountId
                    scorecardId
                    itemId
                }}
            }}
            """
            
            # Create input data with all required fields
            input_data = {
                'value': f"{value}_{i+1}" if count > 1 else value,
                'code': code,  # HTTP response code (e.g., "500", "404")
                'accountId': account_id,
                'scorecardId': scorecard_id,
                'itemId': item_id,  # itemId is required
                'explanation': f"Test error score result created by CLI command for testing error detection feature",
                'confidence': 0.0,
                'correct': False,
                'type': 'test',  # CLI-created test error results
                'createdAt': now,
                'updatedAt': now
            }
            
            # Include scoreId only if we have one
            if score_id:
                input_data['scoreId'] = score_id
            
            response = client.execute(mutation, {'input': input_data})
            created_result = response.get('createScoreResult')
            
            if created_result:
                created_count += 1
                console.print(f"[green]✓ Created error score result {i+1}/{count}: {created_result['id']}[/green]")
            else:
                console.print(f"[bold red]Error:[/bold red] Failed to create score result {i+1}")
                
        except Exception as e:
            console.print(f"[bold red]Error creating score result {i+1}:[/bold red] {str(e)}")
    
    if created_count > 0:
        console.print(f"\n[bold green]Successfully created {created_count} error score result(s) with code {code}![/bold green]")
        console.print(f"[dim]These test records have code='{code}' and should trigger the error indicator in the dashboard.[/dim]")
        console.print(f"\n[bold yellow]Test records created (DELETE WHEN DONE TESTING):[/bold yellow]")
        console.print(f"[dim]• Test Item ID: {item_id}[/dim]")
        if score_id:
            console.print(f"[dim]• Test Score ID: {score_id} (if created)[/dim]")
        console.print(f"\n[bold yellow]To clean up test records:[/bold yellow]")
        console.print(f"[dim]1. Find ScoreResult IDs: plexus score-results list --limit 10[/dim]")
        console.print(f"[dim]2. Delete ScoreResults: plexus score-results delete --id <score-result-id>[/dim]")
        console.print(f"[dim]3. Delete test Item: plexus items delete --id {item_id} (if this command exists)[/dim]")
        console.print(f"[dim]4. Delete test Score/Section if created (look for 'Test Score (DELETE ME)')[/dim]")
    else:
        console.print(f"[bold red]No error score results were created.[/bold red]")

# Create all the synonym groups
@click.group()
def score_result():
    """Manage score result records in the dashboard (alias for 'score-results')"""
    pass

@click.group()
def result():
    """Manage score result records in the dashboard (alias for 'score-results')"""
    pass

@click.group()
def results():
    """Manage score result records in the dashboard (alias for 'score-results')"""
    pass

# Add all commands to each synonym group
for group in [score_result, result, results]:
    group.add_command(list)
    group.add_command(last)
    group.add_command(info)
    group.add_command(delete)
    group.add_command(create_error)
    group.add_command(audit_dependencies)

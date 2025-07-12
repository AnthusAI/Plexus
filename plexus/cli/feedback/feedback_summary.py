"""
CLI command for feedback summary analysis.
"""

import click
import json
import yaml
import asyncio
from typing import Optional, Dict, Any

from plexus.cli.console import console
from plexus.cli.client_utils import create_client
from plexus.cli.reports.utils import resolve_account_id_for_command
from plexus.cli.feedback.feedback_service import FeedbackService


def _find_scorecard_and_score(client, scorecard_name: str, score_name: str) -> tuple[str, str, str, str]:
    """
    Find scorecard and score IDs by name.
    
    Returns:
        tuple of (scorecard_id, score_id, resolved_scorecard_name, resolved_score_name)
    """
    # Query for scorecards directly using GraphQL
    scorecard_query = """
    query ListScorecards {
        listScorecards(limit: 100) {
            items {
                id
                name
            }
        }
    }
    """
    
    response = client.execute(scorecard_query)
    if 'errors' in response:
        raise ValueError(f"Error querying scorecards: {response['errors']}")
    
    scorecards = response.get('listScorecards', {}).get('items', [])
    
    scorecard_match = None
    for scorecard in scorecards:
        if scorecard.get('name') and scorecard_name.lower() in scorecard['name'].lower():
            scorecard_match = scorecard
            break
    
    if not scorecard_match:
        raise ValueError(f"Scorecard not found: {scorecard_name}")
    
    # Query for scores within the scorecard
    score_query = """
    query ListScores($scorecardId: String!) {
        listScores(filter: {scorecardId: {eq: $scorecardId}}, limit: 100) {
            items {
                id
                name
            }
        }
    }
    """
    
    response = client.execute(score_query, {'scorecardId': scorecard_match['id']})
    if 'errors' in response:
        raise ValueError(f"Error querying scores: {response['errors']}")
    
    scores = response.get('listScores', {}).get('items', [])
    
    score_match = None
    for score in scores:
        if score.get('name') and score_name.lower() in score['name'].lower():
            score_match = score
            break
    
    if not score_match:
        raise ValueError(f"Score not found in scorecard '{scorecard_match['name']}': {score_name}")
    
    return scorecard_match['id'], score_match['id'], scorecard_match['name'], score_match['name']


@click.command(name="summary")
@click.option('--scorecard', required=True, help='Scorecard name (partial match supported)')
@click.option('--score', required=True, help='Score name (partial match supported)')
@click.option('--days', default=14, help='Number of days back to analyze (default: 14)')
@click.option('--format', 'output_format', default='json', type=click.Choice(['json', 'yaml']), 
              help='Output format (default: json)')
def feedback_summary(scorecard: str, score: str, days: int, output_format: str):
    """
    Generate comprehensive feedback summary with confusion matrix, accuracy, and AC1 agreement.
    
    This command provides an overview of feedback quality and should be run BEFORE using
    the 'find' command to examine specific feedback items. The summary includes:
    
    - Overall accuracy percentage
    - Gwet's AC1 agreement coefficient  
    - Confusion matrix
    - Precision and recall metrics
    - Class distribution analysis
    - Actionable recommendations for next steps
    
    Example:
        plexus feedback summary --scorecard "SelectQuote HCS" --score "Agent Misrepresentation"
    """
    try:
        console.print(f"[cyan]Generating feedback summary for '{score}' on '{scorecard}'...[/cyan]")
        
        # Create client and resolve account
        client = create_client()
        account_id = resolve_account_id_for_command(client, None)
        
        # Find scorecard and score
        scorecard_id, score_id, scorecard_name, score_name = _find_scorecard_and_score(
            client, scorecard, score
        )
        
        console.print(f"[dim]Found: {scorecard_name} → {score_name}[/dim]")
        console.print(f"[dim]Analyzing last {days} days...[/dim]")
        
        # Generate summary using the shared service
        async def run_summary():
            return await FeedbackService.summarize_feedback(
                client=client,
                scorecard_name=scorecard_name,
                score_name=score_name,
                scorecard_id=scorecard_id,
                score_id=score_id,
                account_id=account_id,
                days=days
            )
        
        # Run the async function
        summary_result = asyncio.run(run_summary())
        
        # Convert to dictionary for output
        result_dict = FeedbackService.format_summary_result_as_dict(summary_result)
        
        # Add command context
        result_dict["command_info"] = {
            "description": "Comprehensive feedback analysis with confusion matrix and agreement metrics",
            "command": f"plexus feedback summary --scorecard \"{scorecard}\" --score \"{score}\" --days {days} --format {output_format}",
            "next_steps": result_dict["recommendation"]
        }
        
        # Output in requested format
        if output_format == 'yaml':
            # Add contextual comments for YAML
            from datetime import datetime
            yaml_comment = f"""# Feedback Summary Analysis
# Scorecard: {scorecard_name}
# Score: {score_name}
# Period: Last {days} days
# Generated: {datetime.now().isoformat()}
#
# This summary provides overview metrics that help identify which specific
# feedback segments to examine using the 'find' command. Use the confusion
# matrix to understand error patterns and the recommendation for next steps.

"""
            yaml_output = yaml.dump(result_dict, default_flow_style=False, sort_keys=False)
            console.print(yaml_comment + yaml_output)
        else:
            console.print(json.dumps(result_dict, indent=2, default=str))
            
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise click.ClickException(str(e))
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise click.ClickException(f"Failed to generate feedback summary: {e}")

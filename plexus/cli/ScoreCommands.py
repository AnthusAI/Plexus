import click
import os
from pathlib import Path
import json
from ruamel.yaml import YAML
from rich.table import Table
from rich.panel import Panel
from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from typing import Optional
import rich
import datetime
import tempfile
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, ToolMessage

# Define the main command groups that will be exported
@click.group()
def scores():
    """Commands for managing scores."""
    pass

@click.group()
def score():
    """Manage individual scores (alias for 'scores')"""
    pass

# Helper functions for resolving identifiers

def create_client() -> PlexusDashboardClient:
    """Create a client and log its configuration"""
    client = PlexusDashboardClient()
    return client

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

def resolve_score_identifier(client, identifier: str) -> Optional[str]:
    """Resolve a score identifier to its ID."""
    # First try direct ID lookup
    try:
        query = f"""
        query GetScore {{
            getScore(id: "{identifier}") {{
                id
            }}
        }}
        """
        result = client.execute(query)
        if result.get('getScore'):
            return identifier
    except:
        pass
    
    # Try lookup by key
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ key: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by name
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ name: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    # Try lookup by externalId
    try:
        query = f"""
        query ListScores {{
            listScores(filter: {{ externalId: {{ eq: "{identifier}" }} }}, limit: 1) {{
                items {{
                    id
                }}
            }}
        }}
        """
        result = client.execute(query)
        items = result.get('listScores', {}).get('items', [])
        if items and len(items) > 0:
            return items[0]['id']
    except:
        pass
    
    return None

def generate_key(name: str) -> str:
    """Generate a key from a name by converting to lowercase and replacing spaces with hyphens."""
    return name.lower().replace(' ', '-')

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard containing the score (accepts ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score to get info about (accepts ID, name, key, or external ID)')
def info(scorecard: str, score: str):
    """Get detailed information about a specific score within a scorecard."""
    client = create_client()
    
    # Resolve the scorecard ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        click.echo(f"Scorecard not found: {scorecard}")
        return
    
    # Fetch the scorecard with sections and scores
    query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                            externalId
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecard_data = result.get('getScorecard')
        
        if not scorecard_data:
            click.echo(f"Scorecard not found: {scorecard}")
            return
        
        # Find the score in the scorecard
        found_score = None
        section_name = None
        
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score_item in section.get('scores', {}).get('items', []):
                if (score_item['id'] == score or 
                    score_item['key'] == score or 
                    score_item['name'] == score or 
                    score_item.get('externalId') == score):
                    found_score = score_item
                    section_name = section['name']
                    break
            if found_score:
                break
        
        if not found_score:
            click.echo(f"Score not found: {score}")
            return
        
        # Display the score information
        panel = Panel.fit(
            f"[bold]Score ID:[/bold] {found_score['id']}\n"
            f"[bold]Name:[/bold] {found_score['name']}\n"
            f"[bold]Key:[/bold] {found_score['key']}\n"
            f"[bold]Type:[/bold] {found_score['type']}\n"
            f"[bold]Order:[/bold] {found_score['order']}\n"
            f"[bold]External ID:[/bold] {found_score.get('externalId', 'None')}\n"
            f"[bold]Section:[/bold] {section_name}\n"
            f"[bold]Description:[/bold] {found_score.get('description', 'None')}\n",
            title=f"Score: {found_score['name']}",
            border_style="blue"
        )
        console.print(panel)
        
    except Exception as e:
        console.print(f"[red]Error retrieving score information: {e}[/red]")

# Add the same command to the score group as an alias
score.add_command(info)

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard to list scores for (accepts ID, name, key, or external ID)')
@click.option('--limit', default=50, help='Maximum number of scores to return')
def list(scorecard: str, limit: int):
    """List scores in a scorecard with rich formatting."""
    client = create_client()
    
    # Resolve the scorecard ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        click.echo(f"Scorecard not found: {scorecard}")
        return
    
    # Fetch the scorecard with sections and scores
    query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            externalId
            createdAt
            updatedAt
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            description
                            type
                            order
                            externalId
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        response = client.execute(query)
        scorecard_data = response.get('getScorecard')
        
        if not scorecard_data:
            click.echo(f"Scorecard not found: {scorecard}")
            return
        
        console = rich.console.Console()
        
        # Format the scorecard panel with sections and detailed scores included
        from plexus.cli.ScorecardCommands import format_scorecard_panel
        panel = format_scorecard_panel(scorecard_data, include_sections=True, detailed_scores=True)
        
        # Override the panel title to indicate this is a scores listing
        panel.title = f"[bold magenta]Scores for {scorecard_data.get('name', 'Scorecard')}[/bold magenta]"
        
        console.print(panel)
        
    except Exception as e:
        click.echo(f"Error listing scores: {e}")

# Add an alias for the list command to the score group
score.add_command(list)

@score.command()
@click.option('--id', required=True, help='Score ID to list versions for')
def versions(id: str):
    """List all versions for a specific score."""
    client = create_client()
    
    # First, get the score details to check if it exists and get the champion version ID
    query = f"""
    query GetScore {{
        getScore(id: "{id}") {{
            id
            name
            key
            externalId
            championVersionId
            section {{
                id
                name
            }}
            versions {{
                items {{
                    id
                    createdAt
                    updatedAt
                    isFeatured
                    parentVersionId
                    note
                }}
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        score_data = result.get('getScore')
        
        if not score_data:
            console.print(f"[red]Score not found with ID: {id}[/red]")
            return
        
        score_name = score_data.get('name')
        champion_version_id = score_data.get('championVersionId')
        section_name = score_data.get('section', {}).get('name', 'Unknown Section')
        
        console.print(f"[bold]Versions for score: {score_name} (ID: {id})[/bold]")
        console.print(f"[dim]Section: {section_name}[/dim]")
        console.print(f"[yellow]Current champion version ID: {champion_version_id}[/yellow]")
        
        # Get all versions
        versions = score_data.get('versions', {}).get('items', [])
        
        if not versions:
            console.print("[yellow]No versions found for this score.[/yellow]")
            return
        
        # Sort versions by creation date (newest first)
        versions.sort(key=lambda v: v.get('createdAt', ''), reverse=True)
        
        # Create a table to display the versions
        table = Table(title=f"Score Versions ({len(versions)} total)")
        table.add_column("ID", style="cyan")
        table.add_column("Created", style="green")
        table.add_column("Updated", style="green")
        table.add_column("Parent ID", style="blue")
        table.add_column("Champion", style="magenta")
        table.add_column("Note", style="yellow")
        
        for version in versions:
            version_id = version.get('id')
            created_at = version.get('createdAt')
            updated_at = version.get('updatedAt')
            parent_id = version.get('parentVersionId', 'None')
            is_champion = "✓" if version_id == champion_version_id else ""
            note = version.get('note', '')
            
            # Truncate note if it's too long
            if note and len(note) > 40:
                note = note[:37] + "..."
            
            table.add_row(
                version_id,
                created_at,
                updated_at,
                parent_id,
                is_champion,
                note
            )
        
        console.print(table)
        
        # Check if champion version exists in the versions list
        if champion_version_id:
            champion_exists = any(v.get('id') == champion_version_id for v in versions)
            if not champion_exists:
                console.print(f"[red]WARNING: Champion version ID {champion_version_id} does not exist in the versions list![/red]")
        
    except Exception as e:
        console.print(f"[red]Error listing score versions: {e}[/red]")

score.add_command(versions)

@score.command()
@click.option('--scorecard', required=True, help='Scorecard containing the score (accepts ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score to optimize prompts for (accepts ID, name, key, or external ID)')
@click.option('--output', help='Output file path for the optimized YAML')
@click.option('--model', default="us.anthropic.claude-3-7-sonnet-20250219-v1:0", help='Bedrock model ID to use for optimization')
def optimize(scorecard: str, score: str, output: Optional[str], model: str):
    """Optimize prompts for a score using Claude AI via AWS Bedrock."""
    client = create_client()
    
    # Get the AWS account ID from the STS service
    try:
        import boto3
        sts = boto3.client('sts')
        account_id = sts.get_caller_identity()['Account']
        console.print(f"[blue]Using AWS Account: {account_id}[/blue]")
    except Exception as e:
        console.print("[yellow]Could not determine AWS account ID[/yellow]")

    # Load and display the documentation file
    try:
        doc_path = Path(__file__).parent.parent / "documentation" / "plexus-score-configuration-yaml-format.md"
        with open(doc_path) as f:
            doc_contents = f.readlines()
            
        # Print first 10 lines
        console.print("[bold]Score Configuration Format Documentation:[/bold]")
        for line in doc_contents[:10]:
            console.print(line.rstrip())
        console.print("...")
    except Exception as e:
        console.print("[yellow]Could not load documentation file[/yellow]")
        console.print(f"[red]Error: {e}[/red]")
            
    except Exception as e:
        console.print("[yellow]Could not load documentation file[/yellow]")

    console.print(f"[bold]Optimizing prompts for score: {score} in scorecard: {scorecard}[/bold]")
    
    # Resolve the scorecard ID
    scorecard_id = resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        console.print(f"[red]Scorecard not found: {scorecard}[/red]")
        return
    
    # Find the score in the scorecard
    query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            id
            name
            key
            sections {{
                items {{
                    id
                    name
                    scores {{
                        items {{
                            id
                            name
                            key
                            championVersionId
                        }}
                    }}
                }}
            }}
        }}
    }}
    """
    
    try:
        result = client.execute(query)
        scorecard_data = result.get('getScorecard')
        
        if not scorecard_data:
            console.print(f"[red]Scorecard not found: {scorecard}[/red]")
            return
        
        # Find the score in the scorecard
        found_score = None
        
        for section in scorecard_data.get('sections', {}).get('items', []):
            for score_item in section.get('scores', {}).get('items', []):
                if (score_item['id'] == score or 
                    score_item['key'] == score or 
                    score_item['name'] == score):
                    found_score = score_item
                    break
            if found_score:
                break
        
        if not found_score:
            console.print(f"[red]Score not found: {score}[/red]")
            return
        
        score_id = found_score['id']
        score_name = found_score['name']
        champion_version_id = found_score.get('championVersionId')
        
        if not champion_version_id:
            console.print(f"[red]No champion version found for score: {score_name}[/red]")
            return
        
        console.print(f"[green]Found score: {score_name} (ID: {score_id})[/green]")
        console.print(f"[green]Champion version ID: {champion_version_id}[/green]")
        
        # Get the score version content
        version_query = f"""
        query GetScoreVersion {{
            getScoreVersion(id: "{champion_version_id}") {{
                id
                configuration
                createdAt
                updatedAt
                note
            }}
        }}
        """
        
        version_result = client.execute(version_query)
        version_data = version_result.get('getScoreVersion')
        
        if not version_data or not version_data.get('configuration'):
            console.print(f"[red]No configuration found for version: {champion_version_id}[/red]")
            return
        
        # Parse the content as YAML using ruamel.yaml
        try:
            content = version_data.get('configuration')
            
            # Initialize ruamel.yaml
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.width = 4096  # Prevent line wrapping
            
            # Configure YAML formatting
            yaml.indent(mapping=2, sequence=4, offset=2)
            yaml.map_indent = 2
            yaml.sequence_indent = 4
            yaml.sequence_dash_offset = 2
            
            # Configure literal block style for system_message and user_message
            def literal_presenter(dumper, data):
                if isinstance(data, str) and "\n" in data:
                    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
                return dumper.represent_scalar('tag:yaml.org,2002:str', data)
            
            yaml.representer.add_representer(str, literal_presenter)
            
            # Parse the YAML content
            import io
            yaml_data = yaml.load(io.StringIO(content))
            
            # Create a tmp directory in the current working directory
            current_dir = os.getcwd()
            tmp_dir = os.path.join(current_dir, 'tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            
            # Create a temporary file to store the YAML in the tmp directory
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', dir=tmp_dir, delete=False) as temp_file:
                temp_path = temp_file.name
                yaml.dump(yaml_data, temp_file)
            
            console.print(f"[green]YAML content saved to temporary file: {temp_path}[/green]")
            
            # Initialize ChatBedrock
            console.print(f"[bold]Initializing ChatBedrock with model: {model}[/bold]")
            llm = ChatBedrock(
                model_id=model,
                model_kwargs={"max_tokens": 4096}  # Increase max tokens to handle larger responses
            )
            
            # Define the official Anthropic text editor tool
            tool = {
                "type": "text_editor_20250124", 
                "name": "str_replace_editor",
                "description": "A tool for editing text files and YAML content",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "enum": ["view", "str_replace", "create", "insert", "undo_edit"],
                            "description": "The command to execute"
                        },
                        "path": {
                            "type": "string",
                            "description": "The path to the file to view or edit"
                        },
                        "old_str": {
                            "type": "string",
                            "description": "The text to replace (for str_replace command)"
                        },
                        "new_str": {
                            "type": "string",
                            "description": "The new text to insert (for str_replace or insert commands)"
                        },
                        "file_text": {
                            "type": "string",
                            "description": "The content to write to the new file (for create command)"
                        },
                        "insert_line": {
                            "type": "integer",
                            "description": "The line number after which to insert text (for insert command)"
                        },
                        "view_range": {
                            "type": "array",
                            "items": {
                                "type": "integer"
                            },
                            "description": "The range of lines to view (for view command)"
                        }
                    },
                    "required": ["command", "path"]
                }
            }
            
            # Bind the tool to the LLM
            llm_with_tools = llm.bind_tools([tool])
            
            # Create the initial prompt for Claude
            prompt = f"""
            I have a YAML configuration file for a call center quality assurance score at {temp_path}. 
            The YAML contains system_message and user_message fields that are used as prompts for an LLM to evaluate call transcripts.
            
            First, please view the file using the view command.
            
            Then, please improve the prompts based on best prompt engineering practices:
            
            1. Make the prompts more clear and specific
            2. Ensure they guide the model through a structured chain of thought
            3. Improve the clarity of evaluation criteria
            4. Make sure the prompts are well-formatted and easy to understand
            5. Ensure the prompts will lead to consistent, accurate evaluations
            6. Maintain the same overall structure and purpose of the prompts
            
            Focus only on improving the system_message and user_message fields.
            
            After viewing the file, use the str_replace command to provide the improved YAML.
            """
            
            console.print("[bold]Sending request to Claude to view and optimize the YAML file...[/bold]")
            
            # Process the conversation with Claude
            try:
                # Start the conversation with just the initial prompt
                initial_messages = [HumanMessage(content=prompt)]
                response = llm_with_tools.invoke(initial_messages)
                
                # Initialize tracking variables
                optimized_yaml = None
                explanation = None
                file_edited = False
                
                # Keep track of the full conversation history for subsequent calls
                # Start with just the initial prompt and response
                conversation_messages = [HumanMessage(content=prompt), response]
                
                # Track which tool calls we've already processed to avoid duplicates
                processed_tool_ids = set()
                
                # Process the conversation until we get the optimized YAML
                max_turns = 5  # Limit the number of turns to prevent infinite loops
                current_turn = 0
                
                while current_turn < max_turns:
                    current_turn += 1
                    
                    # Check if there are tool calls in the response
                    if hasattr(response, 'tool_calls') and response.tool_calls:
                        for tool_call in response.tool_calls:
                            # Get the tool name and arguments
                            tool_name = tool_call.get('name', '')
                            tool_args = tool_call.get('args', {})
                            tool_id = tool_call.get('id', '')
                            
                            command = tool_args.get('command', '')
                            console.print(f"[green]Claude is using command: {command}[/green]")
                            
                            if command == "view":
                                # Handle view command
                                file_path = tool_args.get('path', '')
                                
                                if os.path.exists(file_path):
                                    with open(file_path, 'r') as f:
                                        file_content = f.read()
                                    
                                    # Create a tool response
                                    tool_response = {
                                        "tool_call_id": tool_id,
                                        "content": file_content
                                    }
                                    
                                    # Only add the tool response if we haven't processed this tool ID before
                                    if tool_id not in processed_tool_ids:
                                        conversation_messages.append(ToolMessage(content=tool_response["content"], tool_call_id=tool_id))
                                        processed_tool_ids.add(tool_id)
                                    
                                    # Get the next response
                                    response = llm_with_tools.invoke(conversation_messages)
                                    # Add the response to the conversation history
                                    conversation_messages.append(response)
                                else:
                                    console.print(f"[red]File not found: {file_path}[/red]")
                                    break
                            
                            elif command == "str_replace":
                                # Handle str_replace command
                                file_path = tool_args.get('path', '')
                                old_str = tool_args.get('old_str', '')
                                new_str = tool_args.get('new_str', '')
                                
                                if old_str and new_str:
                                    # Read the file content to check for matches
                                    with open(file_path, 'r') as f:
                                        content = f.read()
                                    
                                    # Check for matches
                                    match_count = content.count(old_str)
                                    if match_count == 0:
                                        error_message = "Error: No match found for replacement text"
                                        console.print(f"[red]{error_message}[/red]")
                                        
                                        # Create an error tool response
                                        tool_response = {
                                            "tool_call_id": tool_id,
                                            "content": error_message,
                                            "is_error": True
                                        }
                                        
                                        conversation_messages.append(ToolMessage(content=tool_response["content"], tool_call_id=tool_id))
                                        conversation_messages.append(HumanMessage(content="Please try again with a different approach. You can use the create command to provide the entire optimized YAML."))
                                        
                                        response = llm_with_tools.invoke(conversation_messages)
                                        conversation_messages.append(response)
                                        continue
                                    
                                    if match_count > 1:
                                        warning_message = f"Warning: Found {match_count} matches for the text to replace. This might lead to unexpected results."
                                        console.print(f"[yellow]{warning_message}[/yellow]")
                                    
                                    # Explicitly update the file content with the replacement
                                    updated_content = content.replace(old_str, new_str)
                                    with open(file_path, 'w') as f:
                                        f.write(updated_content)
                                    
                                    file_edited = True
                                    
                                    # Create a tool response
                                    tool_response = {
                                        "tool_call_id": tool_id,
                                        "content": "Successfully replaced text and updated the file"
                                    }
                                    
                                    # Only add the tool response if we haven't processed this tool ID before
                                    if tool_id not in processed_tool_ids:
                                        conversation_messages.append(ToolMessage(content=tool_response["content"], tool_call_id=tool_id))
                                        processed_tool_ids.add(tool_id)
                                    
                                    # Get the next response
                                    response = llm_with_tools.invoke(conversation_messages)
                                    # Add the response to the conversation history
                                    conversation_messages.append(response)
                                else:
                                    console.print("[red]Missing old_str or new_str for str_replace command[/red]")
                                    break
                            
                            elif command == "create":
                                # Handle create command
                                file_path = tool_args.get('path', '')
                                file_text = tool_args.get('file_text', '')
                                
                                if file_text:
                                    # The text editor tool handles file creation
                                    file_edited = True
                                    
                                    # Create a tool response
                                    tool_response = {
                                        "tool_call_id": tool_id,
                                        "content": "Successfully created file"
                                    }
                                    
                                    # # Continue the conversation with the tool response
                                    # follow_up_message = "Please explain the key improvements you made to the prompts."
                                    
                                    # Only add the tool response if we haven't processed this tool ID before
                                    if tool_id not in processed_tool_ids:
                                        conversation_messages.append(ToolMessage(content=tool_response["content"], tool_call_id=tool_id))
                                        processed_tool_ids.add(tool_id)
                                    
                                    # conversation_messages.append(HumanMessage(content=follow_up_message))
                                    
                                    # Get the explanation
                                    explanation_response = llm_with_tools.invoke(conversation_messages)
                                    explanation = explanation_response.content
                                    
                                    # We're done
                                    break
                                else:
                                    console.print("[red]Missing file_text for create command[/red]")
                                    break
                    
                    # If we have the optimized YAML, we're done
                    if optimized_yaml:
                        break
                    
                    # If we have an explanation and the file was edited, we're done
                    if explanation and file_edited:
                        break
                    
                    # If there are no tool calls, check if the response contains YAML content
                    if not hasattr(response, 'tool_calls') or not response.tool_calls:
                        # Try to extract YAML content from the response
                        response_text = response.content
                        
                        # Look for YAML content between triple backticks
                        import re
                        yaml_pattern = r"```(?:yaml)?\n(.*?)```"
                        yaml_matches = re.findall(yaml_pattern, response_text, re.DOTALL)
                        
                        if yaml_matches:
                            optimized_yaml = yaml_matches[0].strip()
                            explanation = response_text
                            break
                        else:
                            # Ask Claude to use the tools
                            # follow_up_message = "Please use the view command to see the YAML file, and then use the str_replace command to provide the improved YAML."
                            # conversation_messages.append(HumanMessage(content=follow_up_message))
                            response = llm_with_tools.invoke(conversation_messages)
                            conversation_messages.append(response)
                
                # Display the explanation if we have it
                if explanation:
                    console.print("\n[bold]Claude's explanation of improvements:[/bold]")
                    console.print(explanation)
                
                # Check if the file was edited directly by Claude using the tools
                if file_edited:
                    # The file was successfully edited by Claude using the tools
                    if output:
                        # If an output path was specified, copy the edited file to that location
                        with open(temp_path, 'r') as src, open(output, 'w') as dst:
                            dst.write(src.read())
                        console.print(f"[bold green]Optimized YAML saved to: {output}[/bold green]")
                    else:
                        # Otherwise, just inform the user where the optimized file is
                        console.print(f"[bold green]Optimized YAML is available at: {temp_path}[/bold green]")
                    
                    # Verify the YAML is valid using ruamel.yaml
                    try:
                        with open(temp_path, 'r') as f:
                            edited_content = f.read()
                        
                        yaml_verifier = YAML()
                        yaml_verifier.load(io.StringIO(edited_content))
                        console.print("[green]Optimized YAML validation successful[/green]")
                    except Exception as e:
                        console.print(f"[red]Warning: The optimized YAML may not be valid: {e}[/red]")
                
                # Save the optimized YAML if we have it (this is for the non-tool-based approach)
                elif optimized_yaml:
                    if output:
                        # Create backup if file exists
                        if os.path.exists(output):
                            backup_path = f"{output}.backup"
                            with open(output, 'r') as src, open(backup_path, 'w') as dst:
                                dst.write(src.read())
                            console.print(f"[green]Created backup at: {backup_path}[/green]")
                        
                        with open(output, 'w') as f:
                            f.write(optimized_yaml)
                        console.print(f"[bold green]Optimized YAML saved to: {output}[/bold green]")
                    else:
                        # Create a new temporary file for the optimized YAML in the tmp directory
                        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', dir=tmp_dir, delete=False) as opt_file:
                            opt_path = opt_file.name
                            opt_file.write(optimized_yaml)
                        console.print(f"[bold green]Optimized YAML saved to: {opt_path}[/bold green]")
                    
                    # Verify the YAML is valid using ruamel.yaml
                    try:
                        yaml_verifier = YAML()
                        yaml_verifier.load(io.StringIO(optimized_yaml))
                        console.print("[green]Optimized YAML validation successful[/green]")
                    except Exception as e:
                        console.print(f"[red]Warning: The optimized YAML may not be valid: {e}[/red]")
                else:
                    console.print("[red]No optimized YAML was generated. Please try again.[/red]")
            
            except Exception as e:
                console.print(f"[red]Error during optimization: {str(e)}[/red]")
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
            
            # Clean up the temporary file only if we're not using it as the output
            if output or (not file_edited and not optimized_yaml):
                try:
                    os.unlink(temp_path)
                except:
                    pass
            
        except Exception as e:
            console.print(f"[red]Error parsing YAML content: {str(e)}[/red]")
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
            
    except Exception as e:
        console.print(f"[red]Error optimizing prompts: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

score.add_command(optimize)
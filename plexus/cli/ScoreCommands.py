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
            
            # Define the text editor tool with required fields
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "view_file",
                        "description": "View the contents of a file",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "The path to the file to view"
                                }
                            },
                            "required": ["path"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "edit_file",
                        "description": "Edit a file by replacing its contents",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "path": {
                                    "type": "string",
                                    "description": "The path to the file to edit"
                                },
                                "content": {
                                    "type": "string",
                                    "description": "The new content for the file"
                                }
                            },
                            "required": ["path", "content"]
                        }
                    }
                }
            ]
            
            # Bind the tools to the LLM
            llm_with_tools = llm.bind_tools(tools)
            
            # Create the initial prompt for Claude
            prompt = f"""
            I have a YAML configuration file for a call center quality assurance score at {temp_path}. 
            The YAML contains system_message and user_message fields that are used as prompts for an LLM to evaluate call transcripts.
            
            First, please view the file using the view_file tool.
            
            Then, please improve the prompts based on best prompt engineering practices:
            
            1. Make the prompts more clear and specific
            2. Ensure they guide the model through a structured chain of thought
            3. Improve the clarity of evaluation criteria
            4. Make sure the prompts are well-formatted and easy to understand
            5. Ensure the prompts will lead to consistent, accurate evaluations
            6. Maintain the same overall structure and purpose of the prompts
            
            Focus only on improving the system_message and user_message fields.
            
            After viewing the file, use the edit_file tool to provide the improved YAML.
            """
            
            console.print("[bold]Sending request to Claude to view and optimize the YAML file...[/bold]")
            
            # Process the conversation with Claude
            try:
                # Start the conversation
                response = llm_with_tools.invoke(prompt)
                
                # Track the conversation state
                conversation_messages = [HumanMessage(content=prompt), response]
                optimized_yaml = None
                explanation = None
                
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
                            
                            console.print(f"[green]Claude is calling tool: {tool_name}[/green]")
                            
                            if tool_name == "view_file":
                                # Handle view_file tool call
                                file_path = tool_args.get('path', '')
                                
                                if os.path.exists(file_path):
                                    with open(file_path, 'r') as f:
                                        file_content = f.read()
                                    
                                    # Create a tool response
                                    tool_response = {
                                        "tool_call_id": tool_id,
                                        "content": file_content
                                    }
                                    
                                    # Continue the conversation with the tool response
                                    follow_up_message = "Now that you've seen the YAML file, please edit it to improve the prompts based on best practices. Use the edit_file tool to provide the improved YAML."
                                    
                                    # Add the tool response to the conversation
                                    conversation_messages.append({"role": "tool", **tool_response})
                                    conversation_messages.append(HumanMessage(content=follow_up_message))
                                    
                                    # Get the next response
                                    response = llm_with_tools.invoke(conversation_messages)
                                    conversation_messages.append(response)
                                else:
                                    console.print(f"[red]File not found: {file_path}[/red]")
                                    break
                            
                            elif tool_name == "edit_file":
                                # Handle edit_file tool call
                                file_path = tool_args.get('path', '')
                                new_content = tool_args.get('content', '')
                                
                                if new_content:
                                    # Store the optimized YAML
                                    optimized_yaml = new_content
                                    
                                    # Create a tool response
                                    tool_response = {
                                        "tool_call_id": tool_id,
                                        "content": "Successfully edited the file."
                                    }
                                    
                                    # Continue the conversation with the tool response
                                    follow_up_message = "Please explain the key improvements you made to the prompts."
                                    
                                    # Add the tool response to the conversation
                                    conversation_messages.append({"role": "tool", **tool_response})
                                    conversation_messages.append(HumanMessage(content=follow_up_message))
                                    
                                    # Get the explanation
                                    explanation_response = llm_with_tools.invoke(conversation_messages)
                                    explanation = explanation_response.content
                                    
                                    # We're done
                                    break
                                else:
                                    console.print("[red]No content provided for edit_file tool call[/red]")
                                    break
                    
                    # If we have the optimized YAML, we're done
                    if optimized_yaml:
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
                            follow_up_message = "Please use the view_file tool to see the YAML file, and then use the edit_file tool to provide the improved YAML."
                            conversation_messages.append(HumanMessage(content=follow_up_message))
                            response = llm_with_tools.invoke(conversation_messages)
                            conversation_messages.append(response)
                
                # Display the explanation if we have it
                if explanation:
                    console.print("\n[bold]Claude's explanation of improvements:[/bold]")
                    console.print(explanation)
                
                # Save the optimized YAML if we have it
                if optimized_yaml:
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
                    console.print("[red]No optimized YAML was generated after {current_turn} turns[/red]")
                    console.print("[yellow]Falling back to direct approach...[/yellow]")
                    
                    # Fall back to the direct approach
                    with open(temp_path, 'r') as f:
                        yaml_content = f.read()
                    
                    # Create a more direct approach that doesn't rely on tool calls
                    improved_prompt = f"""
                    I have a YAML configuration file for a call center quality assurance score. 
                    The YAML contains system_message and user_message fields that are used as prompts for an LLM to evaluate call transcripts.
                    
                    Here is the current YAML content:
                    
                    ```yaml
                    {yaml_content}
                    ```
                    
                    Please improve the prompts based on best prompt engineering practices:
                    
                    1. Make the prompts more clear and specific
                    2. Ensure they guide the model through a structured chain of thought
                    3. Improve the clarity of evaluation criteria
                    4. Make sure the prompts are well-formatted and easy to understand
                    5. Ensure the prompts will lead to consistent, accurate evaluations
                    6. Maintain the same overall structure and purpose of the prompts
                    
                    Focus only on improving the system_message and user_message fields.
                    
                    Please provide the entire improved YAML file with your changes, maintaining the exact same structure but with improved prompts.
                    After providing the improved YAML, please explain the key improvements you made.
                    """
                    
                    # Use a simpler approach without tool calls
                    console.print("[bold]Sending YAML content directly to Claude for optimization...[/bold]")
                    response = llm.invoke(improved_prompt)
                    
                    # Extract the YAML content from the response
                    response_text = response.content
                    
                    # Look for YAML content between triple backticks
                    import re
                    yaml_pattern = r"```(?:yaml)?\n(.*?)```"
                    yaml_matches = re.findall(yaml_pattern, response_text, re.DOTALL)
                    
                    if yaml_matches:
                        optimized_yaml = yaml_matches[0].strip()
                        console.print("[green]Successfully extracted optimized YAML from Claude's response[/green]")
                        
                        # Extract the explanation (text after the last YAML block)
                        last_yaml_end = response_text.rfind("```")
                        if last_yaml_end != -1:
                            explanation = response_text[last_yaml_end + 3:].strip()
                            console.print("\n[bold]Claude's explanation of improvements:[/bold]")
                            console.print(explanation)
                            
                        # Save the optimized YAML
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
                        console.print("[red]No optimized YAML was generated[/red]")
            
            except Exception as e:
                console.print(f"[red]Error during optimization: {str(e)}[/red]")
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
            
            # Clean up the temporary file
            os.unlink(temp_path)
            
        except Exception as e:
            console.print(f"[red]Error parsing YAML content: {str(e)}[/red]")
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
            
    except Exception as e:
        console.print(f"[red]Error optimizing prompts: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

score.add_command(optimize)
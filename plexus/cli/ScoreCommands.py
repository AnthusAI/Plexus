import click
import os
import json
import rich
import tempfile
import urllib3.exceptions
import requests
import sys
from pathlib import Path
from ruamel.yaml import YAML
from rich.table import Table
from rich.panel import Panel
from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.file_editor import FileEditor
from typing import Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, ToolMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import botocore.exceptions
import urllib3.exceptions
import re
import datetime
import requests
from gql import gql
from plexus.cli.file_editor import FileEditor
from plexus.cli.shared import sanitize_path_name, get_score_yaml_path
from plexus.cli.memoized_resolvers import (
    memoized_resolve_scorecard_identifier,
    memoized_resolve_score_identifier,
    clear_resolver_caches
)
from plexus.cli.score_config_fetching import fetch_and_cache_single_score

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
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
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
                            isDisabled
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
        is_disabled = found_score.get('isDisabled', False)
        status_text = "[red]Disabled[/red]" if is_disabled else "[green]Enabled[/green]"
        
        panel = Panel.fit(
            f"[bold]Score ID:[/bold] {found_score['id']}\n"
            f"[bold]Name:[/bold] {found_score['name']}\n"
            f"[bold]Key:[/bold] {found_score['key']}\n"
            f"[bold]Type:[/bold] {found_score['type']}\n"
            f"[bold]Status:[/bold] {status_text}\n"
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
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
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
                            isDisabled
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
@click.option('--model', default="claude-3-7-sonnet-20250219", help='Anthropic model ID to use for optimization')
@click.option('--debug', is_flag=True, help='Enable debug mode with more verbose output')
def optimize(scorecard: str, score: str, output: Optional[str], model: str, debug: bool = False):
    """Optimize prompts for a score using Claude AI via ChatAnthropic."""
    client = create_client()
    file_editor = FileEditor(debug=debug)
    
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
        doc_path = None

    console.print(f"[bold]Optimizing prompts for score: {score} in scorecard: {scorecard}[/bold]")
    
    # Resolve the scorecard ID
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
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
            
            # Initialize ChatAnthropic
            console.print(f"[bold]Initializing ChatAnthropic with model: {model}[/bold]")
            llm = ChatAnthropic(
                model_name=model,
                verbose=True,
                temperature=0.2,  # Lower temperature for more deterministic responses
                max_tokens=8096   # Increase max tokens to handle larger responses
            )
            
            # Define the official Anthropic text editor tool - only include type and name as required by the API
            tool = {
                "type": "text_editor_20250124", 
                "name": "str_replace_editor"
            }
            
            # Bind the tool to the LLM
            llm_with_tools = llm.bind_tools([tool])
            
            # Create the initial prompt for Claude
            doc_instructions = ""
            if doc_path and os.path.exists(doc_path):
                doc_instructions = f"""
                First, please view the documentation file at {doc_path} to understand the YAML configuration format.
                This documentation will help you understand how to structure the YAML and break it into multiple nodes if needed.
                """
            
            prompt = f"""
            I have a YAML configuration file for a call center quality assurance score at {temp_path}. 
            The YAML contains system_message and user_message fields that are used as prompts for an LLM to evaluate call transcripts.
            
            {doc_instructions}
            
            Then, please view the YAML file using the view command.
            
            After reviewing both files, please optimize the YAML configuration by:
            
            1. Improving the prompts based on best prompt engineering practices:
                - Make the prompts more clear and specific
                - Ensure they guide the model through a structured chain of thought
                - Improve the clarity of evaluation criteria
                - Make sure the prompts are well-formatted and easy to understand
                - Ensure the prompts will lead to consistent, accurate evaluations
            
            2. Breaking the YAML into multiple nodes where appropriate:
                - Identify logical sections that could be separated into different nodes
                - Use the insert and str_replace commands to restructure the YAML
                - Maintain the overall functionality while improving organization
                - Follow the structure guidelines from the documentation
            
            Use the appropriate commands (view, str_replace, insert) to make your changes to the file.
            """
            
            console.print("[bold]Sending request to Claude to view and optimize the YAML file...[/bold]")
            
            # Process the conversation with Claude
            try:
                # Start the conversation with just the initial prompt
                conversation_messages = [HumanMessage(content=prompt)]
                
                # Initialize tracking variables
                file_edited = False
                
                # Process tool calls
                max_turns = 20  # Allow more turns
                current_turn = 0
                
                while current_turn < max_turns:
                    current_turn += 1
                    console.print(f"[cyan]Processing turn {current_turn}/{max_turns}[/cyan]")
                    
                    # Get response from Claude
                    response = invoke_with_retry(llm_with_tools, conversation_messages)
                    
                    # Debug: Print the full response structure
                    if debug:
                        console.print("[magenta]Full response structure:[/magenta]")
                        console.print(f"[magenta]{response}[/magenta]")
                        if hasattr(response, 'content'):
                            console.print("[magenta]Response content:[/magenta]")
                            console.print(f"[magenta]{response.content}[/magenta]")
                        
                        # Check if response was truncated
                        if hasattr(response, 'response_metadata') and response.response_metadata.get('stop_reason') == 'max_tokens':
                            console.print("[yellow]Warning: Response was truncated due to max_tokens limit[/yellow]")
                    
                    # Check if there's a tool use in the response
                    tool_use_found = False
                    
                    # Process the response content
                    if hasattr(response, 'content') and isinstance(response.content, type([])):
                        for content_item in response.content:
                            if isinstance(content_item, type({})) and content_item.get('type') == 'tool_use':
                                tool_use_found = True
                                
                                # Extract tool information
                                tool_name = content_item.get('name', '')
                                tool_id = content_item.get('id', '')
                                tool_input = content_item.get('input', {})
                                command = tool_input.get('command', '')
                                
                                console.print(f"[green]Claude is using command: {command}[/green]")
                                
                                # Debug: Print the full tool input
                                if debug:
                                    console.print(f"[magenta]Tool input: {json.dumps(tool_input, indent=2)}[/magenta]")
                                
                                # Process the command
                                tool_result_content = None
                                
                                if command == "view":
                                    file_path = tool_input.get('path', '')
                                    try:
                                        tool_result_content = file_editor.view(file_path)
                                    except FileNotFoundError:
                                        tool_result_content = f"Error: File not found: {file_path}"
                                
                                elif command == "str_replace":
                                    file_path = tool_input.get('path', '')
                                    old_str = tool_input.get('old_str', '')
                                    new_str = tool_input.get('new_str', '')
                                    
                                    console.print(f"[blue]str_replace: path={file_path}[/blue]")
                                    if debug:
                                        console.print(f"[blue]old_str length: {len(old_str) if old_str else 0} chars[/blue]")
                                        console.print(f"[blue]new_str length: {len(new_str) if new_str else 0} chars[/blue]")
                                    
                                    tool_result_content = file_editor.str_replace(file_path, old_str, new_str)
                                    
                                    if tool_result_content.startswith("Error: No match found"):
                                        console.print(f"[red]{tool_result_content}[/red]")
                                        # Print a snippet of the old_str to help debug
                                        if debug and old_str and len(old_str) > 50:
                                            console.print(f"[red]First 50 chars of old_str: {old_str[:50]}...[/red]")
                                            # Also print a snippet of the file content
                                            try:
                                                content = file_editor.view(file_path)
                                                if content and len(content) > 100:
                                                    console.print(f"[red]First 100 chars of file content: {content[:100]}...[/red]")
                                                
                                                # Save the problematic inputs to files for inspection
                                                debug_dir = os.path.join(os.path.dirname(file_path), "debug")
                                                os.makedirs(debug_dir, exist_ok=True)
                                                
                                                # Save old_str
                                                with open(os.path.join(debug_dir, "old_str.txt"), 'w') as f:
                                                    f.write(old_str)
                                                console.print(f"[yellow]Saved old_str to {os.path.join(debug_dir, 'old_str.txt')}[/yellow]")
                                                
                                                # Save file content
                                                with open(os.path.join(debug_dir, "file_content.txt"), 'w') as f:
                                                    f.write(content)
                                                console.print(f"[yellow]Saved file content to {os.path.join(debug_dir, 'file_content.txt')}[/yellow]")
                                            except FileNotFoundError:
                                                pass
                                    elif tool_result_content.startswith("Successfully"):
                                        console.print(f"[green]{tool_result_content}[/green]")
                                        file_edited = True
                                    else:
                                        console.print(f"[red]{tool_result_content}[/red]")
                                
                                elif command == "undo_edit":
                                    file_path = tool_input.get('path', '')
                                    console.print(f"[blue]undo_edit: path={file_path}[/blue]")
                                    
                                    tool_result_content = file_editor.undo_edit(file_path)
                                    
                                    if tool_result_content.startswith("Successfully"):
                                        console.print(f"[green]{tool_result_content}[/green]")
                                        file_edited = True
                                    else:
                                        console.print(f"[red]{tool_result_content}[/red]")
                                
                                elif command == "insert":
                                    file_path = tool_input.get('path', '')
                                    insert_line = tool_input.get('insert_line', 0)
                                    new_str = tool_input.get('new_str', '')
                                    
                                    console.print(f"[blue]insert: path={file_path}, line={insert_line}[/blue]")
                                    
                                    tool_result_content = file_editor.insert(file_path, insert_line, new_str)
                                    
                                    if tool_result_content.startswith("Successfully"):
                                        console.print(f"[green]{tool_result_content}[/green]")
                                        file_edited = True
                                    else:
                                        console.print(f"[red]{tool_result_content}[/red]")
                                
                                elif command == "create":
                                    file_path = tool_input.get('path', '')
                                    file_text = tool_input.get('file_text', '')
                                    
                                    console.print(f"[blue]create: path={file_path}[/blue]")
                                    tool_result_content = file_editor.create(file_path, file_text)
                                    
                                    if tool_result_content.startswith("Successfully"):
                                        console.print(f"[green]{tool_result_content}[/green]")
                                        file_edited = True
                                    else:
                                        console.print(f"[red]{tool_result_content}[/red]")
                                
                                # Create a tool result message and add it to the conversation
                                if tool_result_content is not None:
                                    tool_result = ToolMessage(
                                        content=tool_result_content,
                                        tool_call_id=tool_id,
                                        name=tool_name
                                    )
                                    
                                    # Add the response to the conversation
                                    conversation_messages.append(response)
                                    conversation_messages.append(tool_result)
                                    break  # Process one tool use at a time
                    
                    if not tool_use_found:
                        # No tool use found, add the response to the conversation and check if we're done
                        conversation_messages.append(response)
                        
                        if file_edited:
                            # If we've edited the file and Claude is now just providing text, we're done
                            console.print("[green]File editing complete[/green]")
                            break
                        else:
                            # Ask Claude to use the tools
                            follow_up = "Please use the text editor tool to make your changes to the YAML file. Start with the view command to see the file contents."
                            conversation_messages.append(HumanMessage(content=follow_up))
            
            except Exception as e:
                console.print(f"[red]Error during optimization: {str(e)}[/red]")
                import traceback
                console.print(f"[red]{traceback.format_exc()}[/red]")
            
            # Clean up the temporary file only if we're not using it as the output
            if output or not file_edited:
                try:
                    os.unlink(temp_path)
                except:
                    pass
            
            # Check if the file was edited
            if file_edited:
                console.print("[green]File editing completed successfully[/green]")
                
                # The file was successfully edited by Claude
                if output:
                    # If an output path was specified, copy the edited file to that location
                    with open(temp_path, 'r') as src, open(output, 'w') as dst:
                        dst.write(src.read())
                    console.print(f"[bold green]Optimized YAML saved to: {output}[/bold green]")
                else:
                    # Otherwise, just inform the user where the optimized file is
                    console.print(f"[bold green]Optimized YAML is available at: {temp_path}[/bold green]")
                
                # Verify the YAML is valid
                try:
                    with open(temp_path, 'r') as f:
                        edited_content = f.read()
                    
                    yaml_verifier = YAML()
                    yaml_verifier.load(io.StringIO(edited_content))
                    console.print("[green]Optimized YAML validation successful[/green]")
                except Exception as e:
                    console.print(f"[red]Warning: The optimized YAML may not be valid: {e}[/red]")
            else:
                console.print("[red]No changes were made to the file. The optimization process did not result in any edits.[/red]")
                console.print("[yellow]Try running with --debug flag for more detailed information.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error parsing YAML content: {str(e)}[/red]")
            import traceback
            console.print(f"[red]{traceback.format_exc()}[/red]")
            
    except Exception as e:
        console.print(f"[red]Error optimizing prompts: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

score.add_command(optimize)

@score.command()
@click.option('--scorecard', required=True, help='Scorecard containing the score (accepts ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score to pull (accepts ID, name, key, or external ID)')
@click.option('--use-cache', is_flag=True, help='Use cached file if available (default: always fetch fresh from API)')
@click.option('--verbose', is_flag=True, help='Show detailed progress and caching information')
def pull(scorecard: str, score: str, use_cache: bool = False, verbose: bool = False):
    """Pull a score's current champion version as a YAML file."""
    try:
        client = create_client()
        
        # Show welcome message
        console.print(f"[bold]Pulling score '{score}' from scorecard '{scorecard}'...[/bold]")
        if use_cache:
            console.print("[blue]Using cached version if available (--use-cache flag is set)[/blue]")
        
        # Fetch and cache the score configuration
        config, yaml_path, from_cache = fetch_and_cache_single_score(
            client=client,
            scorecard_identifier=scorecard,
            score_identifier=score,
            use_cache=use_cache,
            verbose=verbose
        )
        
        # Display success message with the same format as the original implementation
        if from_cache:
            console.print(f"[green]Loaded score configuration from cache: {yaml_path}[/green]")
        else:
            # Extract some details for display
            score_name = config.get('name', 'Unknown')
            score_id = config.get('id', 'Unknown')
            version_id = config.get('version', 'Unknown')
            
            console.print(f"[green]Found score: {score_name} (ID: {score_id})[/green]")
            console.print(f"[green]Champion version ID: {version_id}[/green]")
            console.print(f"[green]Saved score configuration to: {yaml_path}[/green]")
            
    except ValueError as e:
        # Handle expected errors with user-friendly messages
        console.print(f"[red]{str(e)}[/red]")
    except Exception as e:
        # Handle unexpected errors with traceback
        console.print(f"[red]Error during pull operation: {str(e)}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")

@scores.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score identifier (ID, name, key, or external ID)')
def push(scorecard: str, score: str):
    """Push a score's YAML configuration to the server.
    
    This command reads the local YAML file for a score, compares it with the cloud version,
    and only pushes a new version if actual changes are detected.
    """
    client = create_client()
    
    # Resolve scorecard ID
    scorecard_id = memoized_resolve_scorecard_identifier(client, scorecard)
    if not scorecard_id:
        console.print(f"[red]Unable to find scorecard: {scorecard}[/red]")
        return
    
    # Resolve score ID
    score_id = memoized_resolve_score_identifier(client, scorecard_id, score)
    if not score_id:
        console.print(f"[red]Unable to find score: {score} in scorecard: {scorecard}[/red]")
        return
    
    # Get score details including name
    query = f"""
    query GetScore {{
        getScore(id: "{score_id}") {{
            id
            name
        }}
    }}
    """
    
    try:
        with client as session:
            result = session.execute(gql(query))
        score_name = result.get('getScore', {}).get('name', 'Unknown')
    except Exception as e:
        console.print(f"[red]Error fetching score details: {e}[/red]")
        return
    
    # Get scorecard name for proper file path
    scorecard_query = f"""
    query GetScorecard {{
        getScorecard(id: "{scorecard_id}") {{
            name
        }}
    }}
    """
    
    try:
        with client as session:
            result = session.execute(gql(scorecard_query))
        scorecard_name = result.get('getScorecard', {}).get('name', 'Unknown')
    except Exception as e:
        console.print(f"[red]Error fetching scorecard details: {e}[/red]")
        return
    
    # Get the local YAML file path using the utility function
    yaml_path = get_score_yaml_path(scorecard_name, score_name)
    
    if not os.path.exists(yaml_path):
        console.print(f"[red]YAML file not found: {yaml_path}[/red]")
        return
    
    # Read the YAML file
    with open(yaml_path, 'r') as f:
        yaml_content = f.read()
    
    # Extract version information from the YAML
    version_match = re.search(r'^version:\s*["\']?([^"\'\n]+)["\']?', yaml_content, re.MULTILINE)
    parent_match = re.search(r'^parent:\s*["\']?([^"\'\n]+)["\']?', yaml_content, re.MULTILINE)
    
    current_version_id = version_match.group(1) if version_match else None
    parent_version_id = parent_match.group(1) if parent_match else None
    
    # If no current version is found, try to get the champion version from the API
    if not current_version_id:
        query = f"""
        query GetScore {{
            getScore(id: "{score_id}") {{
                championVersionId
            }}
        }}
        """
        result = client.execute(query)
        current_version_id = result.get('getScore', {}).get('championVersionId')
        parent_version_id = current_version_id  # Use current as parent if creating a new version
        
        console.print(f"[blue]No version ID found in YAML, using champion version: {current_version_id}[/blue]")
    
    if not current_version_id:
        console.print(f"[yellow]No version ID found in YAML and no champion version exists. Creating initial version.[/yellow]")
        parent_version_id = None
    else:
        console.print(f"[blue]Current version ID: {current_version_id}[/blue]")
        console.print(f"[blue]Parent version ID: {parent_version_id}[/blue]")
    
    # Clean the YAML content for comparison
    # Remove version and parent lines
    cleaned_yaml_content = re.sub(
        r'^version:\s*["\']?[^"\'\n]+["\']?(\s*parent:\s*["\']?[^"\'\n]+["\']?)?', 
        '', 
        yaml_content, 
        flags=re.MULTILINE
    )
    cleaned_yaml_content = re.sub(
        r'^parent:\s*["\']?[^"\'\n]+["\']?', 
        '', 
        cleaned_yaml_content, 
        flags=re.MULTILINE
    )
    
    # Normalize newlines to avoid false positives due to whitespace
    cleaned_yaml_content = re.sub(r'\n\n+', '\n', cleaned_yaml_content)
    
    # Get the current version from the API to compare
    if current_version_id:
        query = f"""
        query GetScoreVersion {{
            getScoreVersion(id: "{current_version_id}") {{
                configuration
            }}
        }}
        """
        with client as session:
            result = session.execute(gql(query))
        cloud_yaml = result.get('getScoreVersion', {}).get('configuration', '')
        
        # Clean the cloud YAML content for comparison
        cleaned_cloud_yaml = re.sub(
            r'^version:\s*["\']?[^"\'\n]+["\']?(\s*parent:\s*["\']?[^"\'\n]+["\']?)?', 
            '', 
            cloud_yaml, 
            flags=re.MULTILINE
        )
        cleaned_cloud_yaml = re.sub(
            r'^parent:\s*["\']?[^"\'\n]+["\']?', 
            '', 
            cleaned_cloud_yaml, 
            flags=re.MULTILINE
        )
        
        # Normalize newlines
        cleaned_cloud_yaml = re.sub(r'\n\n+', '\n', cleaned_cloud_yaml)
        
        # Compare the cleaned YAML content with the cloud version
        if cleaned_yaml_content.strip() == cleaned_cloud_yaml.strip():
            console.print("[yellow]No changes detected in the YAML configuration. Skipping push.[/yellow]")
            return
        else:
            console.print("[blue]Changes detected in the YAML configuration. Creating new version.[/blue]")
    
    # Create a new version with the cleaned configuration
    mutation = """
    mutation CreateScoreVersion($input: CreateScoreVersionInput!) {
        createScoreVersion(input: $input) {
            id
            configuration
            createdAt
            updatedAt
            note
            score {
                id
                name
                championVersionId
            }
        }
    }
    """
    
    try:
        mutation_input = {
            'input': {
                'scoreId': score_id,
                'configuration': cleaned_yaml_content,
                'parentVersionId': parent_version_id,
                'note': 'Updated via CLI push command',
                'isFeatured': True
            }
        }
        
        with client as session:
            result = session.execute(gql(mutation), mutation_input)
        
        if result.get('createScoreVersion'):
            new_version_id = result['createScoreVersion']['id']
            console.print(f"[green]Successfully created new version for score: {score_name}[/green]")
            console.print(f"[green]New version ID: {new_version_id}[/green]")
            
            # Update the local YAML file with the new version information
            name_match = re.search(r'^name:\s*[^\n]+\n', yaml_content, re.MULTILINE)
            id_match = re.search(r'^id:\s*[^\n]+\n', yaml_content, re.MULTILINE)
            key_match = re.search(r'^key:\s*[^\n]+\n', yaml_content, re.MULTILINE)
            
            # Prioritize insertion after name, then id, then key
            insertion_point = None
            if name_match:
                insertion_point = name_match.end()
            elif id_match:
                insertion_point = id_match.end()
            elif key_match:
                insertion_point = key_match.end()
            
            if insertion_point is not None:
                # First remove any existing version/parent lines to avoid duplication
                cleaned_yaml = re.sub(
                    r'^version:\s*["\']?[^"\'\n]+["\']?(\s*parent:\s*["\']?[^"\'\n]+["\']?)?', 
                    '', 
                    yaml_content, 
                    flags=re.MULTILINE
                )
                cleaned_yaml = re.sub(
                    r'^parent:\s*["\']?[^"\'\n]+["\']?', 
                    '', 
                    cleaned_yaml, 
                    flags=re.MULTILINE
                )
                
                # Normalize newlines to prepare for insertion
                cleaned_yaml = re.sub(r'\n\n+', '\n', cleaned_yaml)
                
                # Update the YAML content with new version and parent information
                updated_yaml = (
                    cleaned_yaml[:insertion_point] + 
                    f"version: {new_version_id}\n" + 
                    f"parent: {parent_version_id}\n" + 
                    cleaned_yaml[insertion_point:]
                )
                
                # Write the updated YAML back to the file
                with open(yaml_path, 'w') as f:
                    f.write(updated_yaml)
                
                console.print(f"[green]Updated local YAML file with new version information[/green]")
            else:
                console.print(f"[yellow]Could not locate proper position to insert version information in the YAML file[/yellow]")
        else:
            console.print("[red]Error creating new version[/red]")
            
    except Exception as e:
        console.print(f"[red]Error pushing score configuration: {e}[/red]")

# Add the push command to the score group as an alias
score.add_command(push)

# Define retry decorator for API calls
@retry(
    retry=retry_if_exception_type((
        urllib3.exceptions.ReadTimeoutError,  # General HTTP timeout
        urllib3.exceptions.ConnectTimeoutError,  # Connection timeout
        urllib3.exceptions.MaxRetryError,  # Max retries exceeded
        requests.exceptions.Timeout,  # General requests timeout
        requests.exceptions.ConnectionError,  # Connection error
        requests.exceptions.RequestException,  # General requests exception
        # Add any Anthropic-specific exceptions here if they exist
    )),
    wait=wait_exponential(multiplier=1, min=4, max=60),
    stop=stop_after_attempt(5),
    reraise=True,
    before_sleep=lambda retry_state: console.print(f"[yellow]API timeout, retrying (attempt {retry_state.attempt_number}/5)...[/yellow]")
)
def invoke_with_retry(llm, messages):
    """Invoke the LLM with retry logic for handling timeouts and connection errors."""
    return llm.invoke(messages)

# Note: The chat command has been moved to ScoreChatCommands.py
# and is now available as "plexus score-chat repl"
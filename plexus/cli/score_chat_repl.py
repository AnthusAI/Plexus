"""
Implementation of a Rich-based REPL for the Plexus score chat command.

This module provides an interactive REPL interface for working with Plexus scores,
using Rich for beautiful terminal output and command history.
"""

from typing import Optional, List, Dict, Any
import os
import json
from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich import pretty
from rich.prompt import Confirm
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult
import asyncio
from plexus.cli.console import console
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.file_editor import FileEditor
from plexus.cli.shared import get_score_yaml_path
from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
import logging
import time

from plexus.cli.plexus_tool import PlexusTool

class StreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming LLM responses."""
    def __init__(self, console: Console):
        self.console = console
        self.current_text = ""
        self.live = None
        self.first_token = True
        self.current_tool_call = None
        self.current_response = ""
        self.tool_calls = []
        self.streaming_active = False
        self.buffer = ""  # Add a buffer to collect tool call JSON data

    def on_llm_start(self, *args, **kwargs):
        """Called when the LLM starts generating."""
        self.current_text = ""
        self.current_response = ""
        self.live = Live(self.current_text, console=self.console, refresh_per_second=4)
        self.live.start()
        self.first_token = True
        self.current_tool_call = None
        self.streaming_active = True
        self.buffer = ""  # Clear the buffer

    def on_llm_new_token(self, token: str, *args, **kwargs):
        """Called when a new token is generated."""
        # Handle both string and list tokens
        if isinstance(token, list):
            # Enhanced debugging for list tokens
            self.console.print(f"[dim]DEBUG: Received list token: {token}[/dim]")
            # Log the full token data to a file for inspection
            with open("streaming_tokens.log", "a") as f:
                f.write(f"LIST TOKEN: {token}\n{'='*50}\n")
            # Skip tool calls in the streaming display
            return
        
        # Enhanced logging for all tokens
        with open("streaming_tokens.log", "a") as f:
            f.write(f"TOKEN: {token[:100]}{'...' if len(token) > 100 else ''}\n")
            if any(marker in token for marker in ['toolu_', '"command":', '"input":', 'tool_use', '"new_str":', '"old_str":', '{']):
                f.write(f"TOOL DATA DETECTED - FULL TOKEN: {token}\n{'='*50}\n")
        
        # Don't skip tokens that look like tool call data - collect them instead
        if self.first_token and token.strip().startswith('{'):
            self.console.print(f"[dim]DEBUG: First token looks like tool call data, buffering: {token[:20]}...[/dim]")
            self.buffer += token
            return
            
        # Log possible tool call data for debugging
        if any(marker in token for marker in ['toolu_', '"command":', '"input":', 'tool_use', '"new_str":', '"old_str":']):
            self.console.print(f"[dim]DEBUG: Found potential tool call data, buffering: {token[:50]}...[/dim]")
            self.buffer += token
            return
        
        if self.first_token:
            self.current_text = "[bold magenta1]Plexus[/bold magenta1] " + token
            self.first_token = False
        else:
            # Don't filter out token parts that might be tool call data
            self.current_text += token
            
        self.current_response += token
        
        # Always update if streaming is active
        if self.streaming_active and self.live:
            self.live.update(self.current_text)

    def on_llm_end(self, *args, **kwargs):
        """Called when the LLM finishes generating."""
        if self.live:
            self.live.stop()
            self.streaming_active = False
            self.console.print()  # Add blank line after response
            
            # Process any buffered tool call data
            if self.buffer:
                self.console.print(f"[dim]DEBUG: Processing buffered tool call data: {self.buffer[:100]}...[/dim]")
                try:
                    # Attempt to parse the buffer as JSON
                    import json
                    data = json.loads(self.buffer.replace("'", '"'))
                    self.console.print(f"[green]Successfully parsed buffered tool call data[/green]")
                    
                    # Record this data for potential tool call processing
                    if isinstance(data, dict) and 'name' in data:
                        self.current_tool_call = {
                            'name': data.get('name', ''),
                            'input': data.get('input', {}),
                            'output': None
                        }
                        self.tool_calls.append(self.current_tool_call.copy())
                except Exception as e:
                    self.console.print(f"[yellow]Failed to parse buffered tool call data: {str(e)}[/yellow]")
            
            # Show tool call details after the response
            if self.tool_calls:
                # Create a header for tool calls section
                self.console.print(Panel("[bold green]Tool Calls[/bold green]", border_style="green"))
                
                # Display each tool call in a dedicated panel
                for i, tool_call in enumerate(self.tool_calls):
                    # Get the actual input data from the tool call
                    input_data = tool_call.get('input', {})
                    
                    # Format the input data nicely
                    if isinstance(input_data, dict):
                        # For dictionary inputs, format as key-value pairs
                        input_str = "\n".join(f"  {k}: {v}" for k, v in input_data.items())
                    else:
                        # Try to parse input_str as JSON if it's a string that looks like a dict
                        try:
                            if isinstance(input_data, str) and '{' in input_data and '}' in input_data:
                                parsed_input = json.loads(input_data.replace("'", '"'))
                                input_str = "\n".join(f"  {k}: {v}" for k, v in parsed_input.items())
                            else:
                                input_str = str(input_data)
                        except:
                            input_str = str(input_data)
                    
                    # Format the output nicely
                    output = tool_call.get('output', '')
                    if output and len(output) > 500:
                        # For long outputs (like file contents), truncate with ellipsis
                        output_str = output[:500] + "...\n[dim](output truncated)[/dim]"
                    else:
                        output_str = output
                    
                    # Create a panel for the tool call
                    tool_panel = Panel(
                        f"[bold blue]Tool:[/bold blue] {tool_call['name']}\n\n"
                        f"[bold blue]Input:[/bold blue]\n{input_str}\n\n"
                        f"[bold blue]Output:[/bold blue]\n{output_str}",
                        title=f"Tool Call {i+1}",
                        border_style="blue",
                        width=self.console.width  # Make panel full width
                    )
                    self.console.print(tool_panel)
                
                # Clear the tool calls after displaying them
                self.tool_calls = []

    def on_llm_error(self, error: Exception, *args, **kwargs):
        """Called when the LLM encounters an error."""
        if self.live:
            self.live.stop()
            self.streaming_active = False
        self.console.print(f"[red]Error: {str(error)}[/red]")
        self.console.print()  # Add blank line after error

    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> None:
        """Called when a tool starts being used."""
        # Create a new tool call
        try:
            # Enhanced debugging of raw input
            self.console.print(f"[magenta]DEBUG: on_tool_start received input_str type: {type(input_str)}[/magenta]")
            if isinstance(input_str, str):
                self.console.print(f"[magenta]DEBUG: on_tool_start input_str (first 100 chars): {input_str[:100]}...[/magenta]")
                # Log the full input string for debugging large strings
                with open("debug_tool_input.log", "w") as f:
                    f.write(f"Full input_str for {serialized['name']}:\n{input_str}")
                self.console.print(f"[magenta]DEBUG: Full input string logged to debug_tool_input.log[/magenta]")
            else:
                self.console.print(f"[magenta]DEBUG: on_tool_start input_str (non-string): {input_str}[/magenta]")
                
            # Handle different input formats more robustly
            input_data = input_str
            
            # For string inputs, try parsing as JSON if applicable
            if isinstance(input_str, str):
                # If it looks like JSON, try to parse it
                if (input_str.strip().startswith('{') and (input_str.strip().endswith('}') or '}' in input_str)) or \
                   (input_str.strip().startswith('[') and (input_str.strip().endswith(']') or ']' in input_str)):
                    try:
                        self.console.print(f"[magenta]DEBUG: Attempting to parse JSON from input_str[/magenta]")
                        input_data = json.loads(input_str.replace("'", '"'))
                        self.console.print(f"[magenta]DEBUG: Successfully parsed JSON[/magenta]")
                    except json.JSONDecodeError as parse_error:
                        self.console.print(f"[magenta]DEBUG: Error parsing JSON: {str(parse_error)}[/magenta]")
                        
                        # Attempt to fix truncated JSON
                        self.console.print(f"[magenta]DEBUG: Attempting to fix potentially truncated JSON[/magenta]")
                        try:
                            # If it's truncated, try to extract all key-value pairs that are complete
                            import re
                            # Match complete key-value pairs (handling string, number, boolean, null)
                            pattern = r'"([^"]+)"\s*:\s*(?:(?:"([^"]*)")|(?:(\d+(?:\.\d+)?|true|false|null)))'
                            matches = re.findall(pattern, input_str)
                            
                            if matches:
                                # Reconstruct a valid JSON object from the matches
                                reconstructed = {}
                                for match in matches:
                                    key = match[0]
                                    # Use the string value if present, otherwise use the non-string value
                                    value = match[1] if match[1] else match[2]
                                    
                                    # Convert non-string values to appropriate types
                                    if not match[1]:  # This is a non-string value
                                        if value.lower() == 'true':
                                            value = True
                                        elif value.lower() == 'false':
                                            value = False
                                        elif value.lower() == 'null':
                                            value = None
                                        elif '.' in value:
                                            try:
                                                value = float(value)
                                            except:
                                                pass
                                        else:
                                            try:
                                                value = int(value)
                                            except:
                                                pass
                                    
                                    reconstructed[key] = value
                                
                                # Check if we have enough data for a str_replace operation
                                if ('command' in reconstructed and reconstructed['command'] == 'str_replace' and
                                    'path' in reconstructed and 'old_str' in reconstructed):
                                    if 'new_str' not in reconstructed:
                                        # Attempt to find new_str separately since it might be large
                                        new_str_match = re.search(r'"new_str"\s*:\s*"([^"]*)"', input_str)
                                        if new_str_match:
                                            reconstructed['new_str'] = new_str_match.group(1)
                                            self.console.print(f"[green]DEBUG: Successfully recovered new_str with length {len(reconstructed['new_str'])}[/green]")
                                
                                self.console.print(f"[green]DEBUG: Reconstructed JSON with keys: {list(reconstructed.keys())}[/green]")
                                input_data = reconstructed
                            else:
                                # Keep the original string if recovery fails
                                self.console.print(f"[yellow]DEBUG: Could not extract key-value pairs from truncated JSON[/yellow]")
                                input_data = input_str
                        except Exception as recovery_error:
                            self.console.print(f"[red]DEBUG: Error during JSON recovery: {str(recovery_error)}[/red]")
                            # Keep the original string if parsing fails
                            input_data = input_str
            
            # Also check if input_data is a string serialized as a string (double-serialized JSON)
            if isinstance(input_data, str) and input_data.strip().startswith('"') and input_data.strip().endswith('"'):
                try:
                    # This might be a JSON string that was serialized again
                    inner_str = json.loads(input_data)
                    if isinstance(inner_str, str) and inner_str.strip().startswith('{') and inner_str.strip().endswith('}'):
                        self.console.print(f"[magenta]DEBUG: Found double-serialized JSON, attempting to parse inner string[/magenta]")
                        inner_data = json.loads(inner_str.replace("'", '"'))
                        self.console.print(f"[magenta]DEBUG: Successfully parsed inner JSON[/magenta]")
                        input_data = inner_data
                except Exception as e:
                    self.console.print(f"[magenta]DEBUG: Error parsing double-serialized JSON: {str(e)}[/magenta]")
            
            # Debug parsed input data
            if isinstance(input_data, dict):
                self.console.print(f"[magenta]DEBUG: Parsed input keys: {list(input_data.keys())}[/magenta]")
                # Log sizes of large fields
                for key, value in input_data.items():
                    if isinstance(value, str) and len(value) > 100:
                        self.console.print(f"[magenta]DEBUG: Field '{key}' has length: {len(value)}[/magenta]")
            
            # Create a new tool call entry
            self.current_tool_call = {
                'name': serialized['name'],
                'input': input_data,
                'output': None
            }
            
            # Add to the list of tool calls
            self.tool_calls.append(self.current_tool_call.copy())
            
            # Display a subtle indicator that a tool is being used
            self.console.print("[dim]Processing...[/dim]", end="\r")
            
        except Exception as e:
            # Log the full error for debugging
            import traceback
            self.console.print(f"[red]Error in on_tool_start: {str(e)}[/red]")
            self.console.print(f"[red]{traceback.format_exc()}[/red]")
            
            # Still create a tool call entry for tracking
            self.current_tool_call = {
                'name': serialized.get('name', 'unknown'),
                'input': f"Error parsing input: {str(e)}",
                'output': None
            }
            self.tool_calls.append(self.current_tool_call.copy())

    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """Called when a tool finishes being used."""
        if self.current_tool_call:
            # Format the output to be more concise for certain cases
            # But preserve the actual file contents for view commands
            if isinstance(self.current_tool_call['input'], dict):
                command = self.current_tool_call['input'].get('command', '')
                if command == 'view':
                    # For view commands, preserve the actual file contents
                    self.current_tool_call['output'] = output
                elif output.startswith("Successfully"):
                    self.current_tool_call['output'] = output
                elif output.startswith("Error:"):
                    self.current_tool_call['output'] = output
                else:
                    # For other outputs (not view commands), just show a success message
                    self.current_tool_call['output'] = "Operation completed successfully"
            else:
                # If we don't have command info, preserve the output
                self.current_tool_call['output'] = output
            
            # Update the tool call in the list with the final input and output
            for tool_call in self.tool_calls:
                if tool_call['name'] == self.current_tool_call['name'] and tool_call['output'] is None:
                    tool_call['input'] = self.current_tool_call['input']
                    tool_call['output'] = self.current_tool_call['output']
                    break
            
            # Clear the current tool call
            self.current_tool_call = None

class ScoreChatREPL:
    """Interactive REPL for working with Plexus scores."""
    
    def __init__(self, scorecard: Optional[str] = None, score: Optional[str] = None):
        self.client = PlexusDashboardClient()
        self.file_editor = FileEditor()
        self.console = console
        self.scorecard = scorecard
        self.score = score
        self.chat_history = []
        self.current_scorecard = None
        self.current_score = None
        
        # Initialize the PlexusTool for score management
        self.plexus_tool = PlexusTool()
        
        # Temporarily disable logging for the chat session
        self.original_handlers = logging.getLogger().handlers[:]
        logging.getLogger().handlers = []
        
        # Initialize Claude with streaming callback
        self.callback_handler = StreamingCallbackHandler(self.console)
        
        # Create base LLM with streaming
        self.llm = ChatAnthropic(
            model_name="claude-3-7-sonnet-20250219",
            temperature=0.7,
            streaming=True,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
            callbacks=[self.callback_handler]
        )
        
        # Create LLM with tools that also has streaming enabled
        self.llm_with_tools = ChatAnthropic(
            model_name="claude-3-7-sonnet-20250219",
            temperature=0.7,
            streaming=True,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
            callbacks=[self.callback_handler]
        ).bind_tools([{
            "type": "text_editor_20250124",
            "name": "str_replace_editor"
        }])
        
        # Base system message template
        self.system_message_template = """
You are a helpful AI coding assistant that specializes in the Plexus YAML declarative programming language for configuring scorecard score configurations for call center QA.  You are a product called Plexus.  You do not claim to be a person named that.

Please do not use Markdown formatting in your responses.  Just use plain text.

Your job will be to work with the user on the question called {question_name} on the scorecard called {scorecard_name}.

The file is stored at {file_path} for you to edit.

The current contents of that YAML file are:
```
{file_contents}
```

Here is documentation on the Plexus scorecard configuration declarative YAML language:
<documentation>
{documentation_contents}
</documentation>

IMPORTANT: When using the str_replace_editor tool, you MUST always include the new_str parameter. If the new_str is very large:
1. First use a "view" command to get the current file contents
2. Then make your changes locally to the full text
3. When sending the str_replace, ensure both old_str and new_str are complete
4. If you encounter any errors with large replacements, try breaking your changes into smaller, incremental edits

Start the session by introducing yourself as Plexus, an AI assistant that specializes in configuring scorecard scores.  Don't talk about YAML with this user, it might intimidate them.  You can show them YAML if they ask, if they're curious, but otherwise you should talk with them in high-level terms about the scorecard and the score.

Then summarize the current score configuration in a short paragraph describing what you see.  Note the type/class of score it uses, and if it uses an LLM then note which model it's configured to use.  If it's a LangGraphScore then briefly describe the nodes that you see configured.

Then ask the user what they would like to change about the scorecard."""

        # Load documentation
        try:
            doc_path = Path(__file__).parent.parent / "documentation" / "plexus-score-configuration-yaml-format.md"
            with open(doc_path) as f:
                self.documentation = f.read()
        except Exception as e:
            self.console.print(f"[yellow]Warning: Could not load documentation: {e}[/yellow]")
            self.documentation = "Documentation not available"

        # If scorecard and score were provided, initialize the system message
        if self.scorecard and self.score:
            self.initialize_system_message()

    def initialize_system_message(self):
        """Initialize the system message with the current score's information."""
        try:
            # Resolve scorecard ID and get its name
            scorecard_id = resolve_scorecard_identifier(self.client, self.scorecard)
            if not scorecard_id:
                self.console.print(f"[red]Scorecard not found: {self.scorecard}[/red]")
                return
            
            # Get scorecard details
            query = f"""
            query GetScorecard {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                    key
                }}
            }}
            """
            result = self.client.execute(query)
            scorecard_data = result.get('getScorecard')
            if not scorecard_data:
                self.console.print(f"[red]Error retrieving scorecard: {self.scorecard}[/red]")
                return
            scorecard_name = scorecard_data['name']
            
            # Resolve score ID and get its name
            score_id = resolve_score_identifier(self.client, scorecard_id, self.score)
            if not score_id:
                self.console.print(f"[red]Score not found: {self.score}[/red]")
                return
            
            # Get score details
            query = f"""
            query GetScore {{
                getScore(id: "{score_id}") {{
                    id
                    name
                    key
                }}
            }}
            """
            result = self.client.execute(query)
            score_data = result.get('getScore')
            if not score_data:
                self.console.print(f"[red]Error retrieving score: {self.score}[/red]")
                return
            score_name = score_data['name']
            
            # Get the YAML file path
            yaml_path = get_score_yaml_path(scorecard_name, score_name)
            
            # Read the YAML file contents
            if yaml_path.exists():
                with open(yaml_path, 'r') as f:
                    file_contents = f.read()
            else:
                file_contents = "File not found"
            
            # Create the system message
            system_message = self.system_message_template.format(
                question_name=score_name,
                scorecard_name=scorecard_name,
                file_path=str(yaml_path),
                file_contents=file_contents,
                documentation_contents=self.documentation
            )
            
            # If DEBUG is set, show the system message in a panel
            if os.environ.get('DEBUG'):
                self.console.print(Panel.fit(
                    system_message,
                    title="System Message",
                    border_style="blue"
                ))
            
            # Add the system message to chat history
            self.chat_history = [SystemMessage(content=system_message)]
            
        except Exception as e:
            self.console.print(f"[red]Error initializing system message: {e}[/red]")
            # Fall back to a basic system message
            self.chat_history = [SystemMessage(content=self.system_message_template)]

    def run(self):
        """Run the REPL."""
        try:
            # If scorecard and score were provided, load them and get initial response
            if self.scorecard and self.score:
                self.load_score(self.scorecard, self.score)
                # Initialize system message with the loaded score
                self.initialize_system_message()
                # Add a human message to trigger the initial analysis
                self.chat_history.append(HumanMessage(content="Please analyze this score configuration and tell me what you see."))
                # Get initial response from Claude
                try:
                    # Use the streaming LLM for the initial response
                    response = self.llm.invoke(self.chat_history)
                    self.chat_history.append(response)
                    self.console.print()  # Add blank line after response
                except Exception as e:
                    self.console.print(f"[red]Error getting initial response: {str(e)}[/red]")
            
            while True:
                try:
                    # Get user input with a simple prompt
                    self.console.print("[bold dodger_blue1]>[/bold dodger_blue1] ", end="")
                    user_input = input()
                    self.console.print()  # Add blank line after user input
                    
                    # Check if it's a command (with or without slash)
                    if user_input.startswith("/"):
                        # Handle slash-prefixed command
                        self.handle_command(user_input[1:])
                    else:
                        # Check if it's exit/quit/help without slash
                        parts = user_input.split()
                        cmd = parts[0].lower()
                        
                        if cmd in ["exit", "quit"]:
                            self.console.print("[yellow]Goodbye![/yellow]")
                            exit(0)
                        elif cmd == "help":
                            self.show_help()
                        else:
                            # Handle as natural language input
                            self.handle_natural_language(user_input)
                        
                except KeyboardInterrupt:
                    self.console.print("\n[yellow]Goodbye![/yellow]")
                    break
                except Exception as e:
                    self.console.print(f"[red]Error: {str(e)}[/red]")
        finally:
            # Restore original logging handlers
            logging.getLogger().handlers = self.original_handlers

    def handle_command(self, command: str):
        """Handle explicit commands."""
        parts = command.split()
        cmd = parts[0]
        args = parts[1:]
        
        if cmd == "help":
            self.show_help()
        elif cmd == "list":
            self.list_scorecards()
        elif cmd == "pull":
            if len(args) < 2:
                self.console.print("[red]Usage: /pull <scorecard> <score>[/red]")
                return
            self.pull_score(args[0], args[1])
        elif cmd == "push":
            if len(args) < 2:
                self.console.print("[red]Usage: /push <scorecard> <score>[/red]")
                return
            self.push_score(args[0], args[1])
        elif cmd == "exit":
            self.console.print("[yellow]Goodbye![/yellow]")
            exit(0)
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")

    def handle_natural_language(self, user_input: str):
        """Handle natural language input from the user."""
        try:
            # Clear log file for this session
            with open("tool_calls.log", "w") as f:
                f.write(f"=== NEW SESSION {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n\n")
                
            # Append the new user input to existing chat history
            self.chat_history.append(HumanMessage(content=user_input))
            
            # Process messages with a proper tool calling loop
            finished = False
            while not finished:
                try:
                    # Get response from Claude - invoke, not stream
                    ai_msg = self.llm_with_tools.invoke(self.chat_history)
                    
                    # Add the model response to chat history
                    self.chat_history.append(ai_msg)
                    
                    # First, stream the AI's text response, even if it contains tool calls
                    if ai_msg.content:
                        # Detect and clean up the content if it contains tool calls
                        clean_content = ""
                        
                        # Handle different content formats
                        if isinstance(ai_msg.content, list):
                            # For list responses, extract only text content items
                            for item in ai_msg.content:
                                if isinstance(item, dict):
                                    if 'text' in item:
                                        clean_content += item['text']
                                    # Skip tool call items
                                    elif 'type' in item and item.get('type') == 'tool_use':
                                        continue
                                else:
                                    clean_content += str(item)
                        elif isinstance(ai_msg.content, dict) and 'text' in ai_msg.content:
                            # Handle dictionary with text key
                            clean_content = ai_msg.content['text']
                        else:
                            # For string content (the normal case)
                            clean_content = ai_msg.content
                            # Check for tool call metadata in string content
                            if isinstance(clean_content, str):
                                # Find where any tool call data begins (look for patterns like ":{" or ":[")
                                for pattern in [':{', ':[', ': {', ': [']:
                                    split_pos = clean_content.find(pattern)
                                    if split_pos > 0:
                                        # Only keep content before the tool call data
                                        clean_content = clean_content[:split_pos]
                                        break
                        
                        # Stream the cleaned content
                        if clean_content:
                            self.callback_handler.on_llm_start()
                            for chunk in clean_content:
                                self.callback_handler.on_llm_new_token(chunk)
                            self.callback_handler.on_llm_end()
                    
                    # Check if the response has tool calls
                    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        # Enhanced logging for all tool calls
                        self.console.print(f"[blue]DEBUG: Found {len(ai_msg.tool_calls)} tool calls[/blue]")
                        
                        # Log all tool calls to file for analysis
                        with open("tool_calls.log", "a") as f:
                            f.write(f"Found {len(ai_msg.tool_calls)} tool calls\n")
                            for i, tc in enumerate(ai_msg.tool_calls):
                                f.write(f"TOOL CALL #{i+1}:\n")
                                f.write(f"  ID: {tc.get('id', 'unknown')}\n")
                                f.write(f"  Name: {tc.get('name', 'unknown')}\n")
                                f.write(f"  Type: {tc.get('type', 'unknown')}\n")
                                f.write(f"  Content: {str(ai_msg.content)[:500]}...\n")
                                
                                # If it's a str_replace, do special logging
                                args = tc.get('args', {})
                                if isinstance(args, dict) and args.get('command') == 'str_replace':
                                    f.write("  STR_REPLACE DETECTED!\n")
                                    f.write(f"  Path: {args.get('path', 'missing')}\n")
                                    if 'old_str' in args:
                                        f.write(f"  old_str length: {len(args['old_str'])}\n")
                                        f.write(f"  old_str preview: {args['old_str'][:50]}...{args['old_str'][-50:]}\n")
                                    else:
                                        f.write("  old_str: MISSING\n")
                                        
                                    if 'new_str' in args:
                                        f.write(f"  new_str length: {len(args['new_str'])}\n")
                                        f.write(f"  new_str preview: {args['new_str'][:50]}...{args['new_str'][-50:]}\n")
                                    else:
                                        f.write("  new_str: MISSING\n")
                                
                                f.write("\n")
                        
                        # Process each tool call
                        for tool_call in ai_msg.tool_calls:
                            # Debug output for tool call
                            self.console.print(f"[blue]DEBUG: Tool Call Information[/blue]")
                            self.console.print(f"[blue]DEBUG: Tool type: {tool_call.get('type', 'unknown')}[/blue]")
                            self.console.print(f"[blue]DEBUG: Tool name: {tool_call.get('name', 'unknown')}[/blue]")
                            self.console.print(f"[blue]DEBUG: Tool ID: {tool_call.get('id', 'unknown')}[/blue]")
                            self.console.print(f"[blue]DEBUG: Tool call keys: {list(tool_call.keys())}[/blue]")
                            
                            # Extract the tool input more carefully
                            tool_input = {}
                            
                            # First check the 'args' field (standard format)
                            if 'args' in tool_call:
                                tool_input = tool_call['args']
                                self.console.print(f"[blue]DEBUG: Found tool input in 'args' field[/blue]")
                            # Fallback to 'input' field
                            elif 'input' in tool_call:
                                tool_input = tool_call['input']
                                self.console.print(f"[blue]DEBUG: Found tool input in 'input' field[/blue]")
                            # Fallback to scanning all fields for expected command parameters
                            else:
                                self.console.print(f"[yellow]WARNING: Could not find standard tool input fields. Scanning all fields...[/yellow]")
                                for key, value in tool_call.items():
                                    if isinstance(value, dict) and any(param in value for param in ['command', 'path', 'old_str', 'new_str']):
                                        tool_input = value
                                        self.console.print(f"[blue]DEBUG: Found likely tool input in '{key}' field[/blue]")
                                        break
                            
                            # Create a dictionary representation for the callback handler
                            current_tool_call = {
                                'id': tool_call.get('id', ''),
                                'name': tool_call.get('name', ''),
                                'input': tool_input,
                                'output': None
                            }
                            
                            # Notify callback of tool start
                            self.callback_handler.on_tool_start(
                                {'name': tool_call.get('name', ''), 'id': tool_call.get('id', '')},
                                json.dumps(tool_input) if isinstance(tool_input, dict) else str(tool_input)
                            )
                            
                            # Process the command
                            command = tool_input.get('command', '')
                            tool_result_content = None
                            
                            if command == "view":
                                file_path = tool_input.get('path', '').lstrip('/')
                                try:
                                    tool_result_content = self.file_editor.view(file_path)
                                except FileNotFoundError:
                                    tool_result_content = f"Error: File not found: {file_path}"
                                
                            elif command == "str_replace":
                                file_path = tool_input.get('path', '').lstrip('/')
                                old_str = tool_input.get('old_str', '')
                                new_str = tool_input.get('new_str', '')
                                
                                # Enhanced debugging
                                self.console.print("[cyan]===== STR_REPLACE EXECUTION =====")
                                self.console.print(f"[cyan]File path: {file_path}")
                                self.console.print(f"[cyan]Old string length: {len(old_str) if old_str else 0}")
                                self.console.print(f"[cyan]New string length: {len(new_str) if new_str else 0}")
                                
                                # Verify all parameters are present
                                if not file_path:
                                    tool_result_content = "Error: Missing file path parameter"
                                elif not old_str:
                                    tool_result_content = "Error: Missing old_str parameter"
                                elif not new_str and 'new_str' not in tool_input:
                                    tool_result_content = "Error: Missing new_str parameter (key not found in input)"
                                else:
                                    # Execute the str_replace operation
                                    tool_result_content = self.file_editor.str_replace(file_path, old_str, new_str)
                                
                            elif command == "undo_edit":
                                file_path = tool_input.get('path', '').lstrip('/')
                                tool_result_content = self.file_editor.undo_edit(file_path)
                                
                            elif command == "insert":
                                file_path = tool_input.get('path', '').lstrip('/')
                                insert_line = tool_input.get('insert_line', 0)
                                new_str = tool_input.get('new_str', '')
                                tool_result_content = self.file_editor.insert(file_path, insert_line, new_str)
                                
                            elif command == "create":
                                file_path = tool_input.get('path', '').lstrip('/')
                                content = tool_input.get('file_text', '')
                                tool_result_content = self.file_editor.create(file_path, content)
                            
                            # Update the tool call with result and notify callback
                            if tool_result_content is not None:
                                current_tool_call['output'] = tool_result_content
                                self.callback_handler.on_tool_end(tool_result_content)
                                
                                # Create a ToolMessage to send back to the model
                                tool_msg = ToolMessage(
                                    content=tool_result_content,
                                    tool_call_id=tool_call.get('id', ''),
                                    name=tool_call.get('name', '')
                                )
                                
                                # Add the tool message to chat history
                                self.chat_history.append(tool_msg)
                    else:
                        # No tool calls, this is a final response
                        finished = True
                
                except Exception as e:
                    self.console.print(f"[red]Error during model interaction: {str(e)}[/red]")
                    import traceback
                    self.console.print(f"[red]{traceback.format_exc()}[/red]")
                    # Try recovery if there's an issue
                    self.recover_and_continue()
                    finished = True
            
        except Exception as e:
            self.console.print(f"[red]Error processing user input: {str(e)}[/red]")
            import traceback
            self.console.print(f"[red]{traceback.format_exc()}[/red]")

    def recover_and_continue(self):
        """Recover from an error by creating a simplified chat history and continuing the conversation."""
        try:
            # Create a simplified history with the system message and the last human message
            simplified_history = []
            
            # Keep the system message
            for msg in self.chat_history:
                if isinstance(msg, SystemMessage):
                    simplified_history.append(msg)
                    break
            
            # Find the last real content from model (not tool calls)
            last_content = ""
            for i in range(len(self.chat_history) - 1, -1, -1):
                msg = self.chat_history[i]
                if isinstance(msg, AIMessage) and msg.content and not msg.additional_kwargs.get('tool_calls'):
                    last_content = msg.content
                    break
            
            # Add a summary message with what happened so far
            # Extract input from the last tool call
            last_tool_command = ""
            last_tool_path = ""
            for i in range(len(self.chat_history) - 1, -1, -1):
                msg = self.chat_history[i]
                if isinstance(msg, AIMessage) and msg.additional_kwargs.get('tool_calls'):
                    tool_calls = msg.additional_kwargs.get('tool_calls', [])
                    if tool_calls and 'input' in tool_calls[0]:
                        input_data = tool_calls[0].get('input', {})
                        if isinstance(input_data, dict):
                            last_tool_command = input_data.get('command', '')
                            last_tool_path = input_data.get('path', '')
                    break
            
            # Add the last human message
            last_human_msg = None
            for i in range(len(self.chat_history) - 1, -1, -1):
                if isinstance(self.chat_history[i], HumanMessage):
                    last_human_msg = self.chat_history[i]
                    break
            
            if last_human_msg:
                # If we found a tool call, mention it in the summary
                if last_tool_command:
                    summary = f"I previously processed a {last_tool_command} command on {last_tool_path}. The user would like: {last_human_msg.content}"
                    summary_msg = AIMessage(content=summary)
                    simplified_history.append(summary_msg)
                
                # Add the human message
                simplified_history.append(last_human_msg)
                
                # Try again with the simplified history
                self.console.print("[yellow]Retrying with simplified chat history...[/yellow]")
                
                # Create a new instance of the LLM to avoid any lingering state issues
                recovery_llm = ChatAnthropic(
                    model_name="claude-3-7-sonnet-20250219",
                    temperature=0.7,
                    streaming=True,
                    anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                    max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
                    callbacks=[self.callback_handler]
                ).bind_tools([{
                    "type": "text_editor_20250124",
                    "name": "str_replace_editor"
                }])
                
                # Get a new response with the simplified history
                response = recovery_llm.invoke(simplified_history)
                
                # Add the response to the chat history
                self.chat_history.append(response)
                self.console.print()  # Add blank line after response
                
                # Print helpful message to the user
                self.console.print("[green]Recovered from error and continued the conversation.[/green]")
        
        except Exception as e:
            self.console.print(f"[red]Error during recovery: {str(e)}[/red]")
            import traceback
            self.console.print(f"[red]{traceback.format_exc()}[/red]")

    def show_help(self):
        """Show available commands."""
        help_text = """
[bold]Available Commands:[/bold]
/help             - Show this help message

/list             - List available scorecards

/pull <s> <s>     - Pull a score's current version

/push <s> <s>     - Push a score's updated version

exit              - Exit the REPL (no slash needed)
quit              - Same as exit (no slash needed)

[bold]Natural Language:[/bold]
You can also just ask me questions or tell me what you'd like to do in plain English.
"""
        self.console.print(Panel.fit(help_text, title="Help", border_style="blue"))

    def list_scorecards(self):
        """List available scorecards."""
        query = """
        query ListScorecards {
            listScorecards {
                items {
                    id
                    name
                    key
                    sections {
                        items {
                            id
                            name
                            scores {
                                items {
                                    id
                                    name
                                    key
                                }
                            }
                        }
                    }
                }
            }
        }
        """
        
        try:
            result = self.client.execute(query)
            scorecards = result.get('listScorecards', {}).get('items', [])
            
            if not scorecards:
                self.console.print("[yellow]No scorecards found.[/yellow]")
                return
            
            table = Table(title="Available Scorecards")
            table.add_column("Name", style="cyan")
            table.add_column("Key", style="green")
            table.add_column("Scores", style="magenta")
            
            for scorecard in scorecards:
                scores = []
                for section in scorecard.get('sections', {}).get('items', []):
                    for score in section.get('scores', {}).get('items', []):
                        scores.append(score['name'])
                
                table.add_row(
                    scorecard['name'],
                    scorecard['key'],
                    "\n".join(scores)
                )
            
            self.console.print(table)
            
        except Exception as e:
            self.console.print(f"[red]Error listing scorecards: {str(e)}[/red]")

    def pull_score(self, scorecard: str, score: str):
        """Pull a score's current version."""
        # Resolve identifiers
        scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
        if not scorecard_id:
            self.console.print(f"[red]Scorecard not found: {scorecard}[/red]")
            return
        
        # Get scorecard details to get its name
        scorecard_query = f"""
        query GetScorecard {{
            getScorecard(id: "{scorecard_id}") {{
                id
                name
            }}
        }}
        """
        scorecard_result = self.client.execute(scorecard_query)
        scorecard_data = scorecard_result.get('getScorecard')
        if not scorecard_data:
            self.console.print(f"[red]Error retrieving scorecard: {scorecard}[/red]")
            return
        scorecard_name = scorecard_data['name']
        
        score_id = resolve_score_identifier(self.client, scorecard_id, score)
        if not score_id:
            self.console.print(f"[red]Score not found: {score}[/red]")
            return
        
        # Get score details
        query = f"""
        query GetScore {{
            getScore(id: "{score_id}") {{
                id
                name
                championVersionId
            }}
        }}
        """
        
        try:
            result = self.client.execute(query)
            score_data = result.get('getScore')
            if not score_data:
                self.console.print(f"[red]Error retrieving score: {score}[/red]")
                return
            
            champion_version_id = score_data.get('championVersionId')
            if not champion_version_id:
                self.console.print(f"[red]No champion version found for score: {score}[/red]")
                return
            
            # Get version content
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
            
            version_result = self.client.execute(version_query)
            version_data = version_result.get('getScoreVersion')
            
            if not version_data or not version_data.get('configuration'):
                self.console.print(f"[red]No configuration found for version: {champion_version_id}[/red]")
                return
            
            # Get the YAML file path using the scorecard name
            yaml_path = get_score_yaml_path(scorecard_name, score_data['name'])
            
            # Write to file
            with open(yaml_path, 'w') as f:
                f.write(version_data['configuration'])
            
            self.console.print(f"[green]Saved score configuration to: {yaml_path}[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Error pulling score: {str(e)}[/red]")

    def push_score(self, scorecard: str, score: str):
        """Push a score's updated version."""
        # Resolve identifiers
        scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
        if not scorecard_id:
            self.console.print(f"[red]Scorecard not found: {scorecard}[/red]")
            return
        
        score_id = resolve_score_identifier(self.client, scorecard_id, score)
        if not score_id:
            self.console.print(f"[red]Score not found: {score}[/red]")
            return
        
        # Get score details
        query = f"""
        query GetScore {{
            getScore(id: "{score_id}") {{
                id
                name
                championVersionId
            }}
        }}
        """
        
        try:
            result = self.client.execute(query)
            score_data = result.get('getScore')
            if not score_data:
                self.console.print(f"[red]Error retrieving score: {score}[/red]")
                return
            
            # Get the YAML file path
            yaml_path = get_score_yaml_path(scorecard, score_data['name'])
            
            if not yaml_path.exists():
                self.console.print(f"[red]YAML file not found at: {yaml_path}[/red]")
                return
            
            # Read the YAML file
            with open(yaml_path, 'r') as f:
                yaml_content = f.read()
            
            # Create new version
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
            
            result = self.client.execute(mutation, {
                'input': {
                    'scoreId': score_id,
                    'configuration': yaml_content,
                    'parentVersionId': score_data.get('championVersionId'),
                    'note': 'Updated via CLI push command',
                    'isFeatured': True
                }
            })
            
            if result.get('createScoreVersion'):
                self.console.print(f"[green]Successfully created new version for score: {score_data['name']}[/green]")
                self.console.print(f"[green]New version ID: {result['createScoreVersion']['id']}[/green]")
            else:
                self.console.print("[red]Error creating new version[/red]")
            
        except Exception as e:
            self.console.print(f"[red]Error pushing score: {str(e)}[/red]")

    def load_score(self, scorecard: str, score: str):
        """Load a score's configuration."""
        try:
            # First pull the score
            self.pull_score(scorecard, score)
            
            # Get scorecard details to get its name
            scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
            if not scorecard_id:
                self.console.print(f"[red]Scorecard not found: {scorecard}[/red]")
                return
            
            scorecard_query = f"""
            query GetScorecard {{
                getScorecard(id: "{scorecard_id}") {{
                    id
                    name
                }}
            }}
            """
            scorecard_result = self.client.execute(scorecard_query)
            scorecard_data = scorecard_result.get('getScorecard')
            if not scorecard_data:
                self.console.print(f"[red]Error retrieving scorecard: {scorecard}[/red]")
                return
            scorecard_name = scorecard_data['name']
            
            # Get score details to get its name
            score_id = resolve_score_identifier(self.client, scorecard_id, score)
            if not score_id:
                self.console.print(f"[red]Score not found: {score}[/red]")
                return
            
            score_query = f"""
            query GetScore {{
                getScore(id: "{score_id}") {{
                    id
                    name
                }}
            }}
            """
            score_result = self.client.execute(score_query)
            score_data = score_result.get('getScore')
            if not score_data:
                self.console.print(f"[red]Error retrieving score: {score}[/red]")
                return
            
            # Get the YAML file path using the correct names
            yaml_path = get_score_yaml_path(scorecard_name, score_data['name'])
            
            if not yaml_path.exists():
                self.console.print(f"[red]YAML file not found at: {yaml_path}[/red]")
                return
            
            self.current_scorecard = scorecard
            self.current_score = score
            
        except Exception as e:
            self.console.print(f"[red]Error loading score: {str(e)}[/red]") 
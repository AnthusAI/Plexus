"""
Implementation of a Rich-based REPL for the Plexus score chat command.

This module provides an interactive REPL interface for working with Plexus scores,
using Rich for beautiful terminal output and command history.
It also provides a Textual-based UI alternative for a more modern interface with
real-time streaming output capabilities.

This module can be used directly via:
    python -m plexus.cli.score_chat_repl [options]

Or through the Plexus CLI via:
    plexus score chat [options]

The recommended approach is to use the Plexus CLI command.
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

# Add Textual imports
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer, Vertical
from textual.widgets import Header, Footer, Input, Static, Label, Button, LoadingIndicator
from textual.reactive import reactive
from textual import work

from plexus.cli.plexus_tool import PlexusTool

# Import our custom components
from plexus.cli.components.response_status import ResponseStatus
from plexus.cli.components.chat_container import ChatContainer
from plexus.cli.components.chat_input import ChatInput
from plexus.cli.components.tool_output import ToolOutput

# Import Textual components
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Button, Input, TextArea, Static, Label
from textual.worker import Worker, WorkerState

# Instead of using non-existent logging tracer, just use standard callback handlers
# from langchain_core.tracers.logging import LoggingCallbackHandler
# from langchain_core.tracers.stdout import ConsoleCallbackHandler
import copy
from io import StringIO

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

class TextualStreamingCallbackHandler(BaseCallbackHandler):
    """Callback handler for streaming LLM responses to a Textual UI."""
    
    def __init__(self, app):
        """Initialize with the Textual app instance.
        
        Args:
            app: The TextualScoreChatApp instance
        """
        self.app = app
        self.current_token_buffer = ""
        
    def on_llm_start(self, *args, **kwargs):
        """Called when LLM starts processing."""
        self.app.call_from_thread(self.app.response_status.show_responding)
    
    def on_llm_end(self, *args, **kwargs):
        """Called when LLM finishes processing."""
        self.app.call_from_thread(self.app.response_status.hide_responding)
        # If there's any buffered content, make sure it's added
        if self.current_token_buffer:
            self.app.call_from_thread(self.app.add_ai_response, self.current_token_buffer)
            self.current_token_buffer = ""
    
    def on_llm_new_token(self, token: str, **kwargs):
        """Called on each new token from streaming."""
        self.current_token_buffer += token
        if token.endswith(("\n", ".", "!", "?")) or len(self.current_token_buffer) > 40:
            # Send the buffered content to be displayed
            buffered = self.current_token_buffer
            self.app.call_from_thread(self.app.update_ai_response, buffered)
            self.current_token_buffer = ""
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts execution."""
        tool_name = serialized.get("name", "Tool")
        self.app.call_from_thread(self.app.add_tool_start, tool_name, input_str)
    
    def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes execution."""
        self.app.call_from_thread(self.app.add_tool_end, output)

class TextualScoreChatApp(App):
    """Textual UI implementation of the Score Chat REPL."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    /* Chat container */
    #chat-container {
        width: 100%;
        height: 1fr;
        min-height: 20;
        scrollbar-color: #5521b5;
        scrollbar-background: #272820;
        scrollbar-corner-color: #5521b5;
    }
    
    /* Custom scrollbar for all scrollable elements */
    ScrollableContainer {
        scrollbar-color: #5521b5;
        scrollbar-background: #272820;
        scrollbar-corner-color: #5521b5;
    }
    
    #message-list {
        width: 100%;
        height: auto;
        padding: 1 2;
    }
    
    /* Input container above footer */
    #input-container {
        width: 100%;
        height: auto;
        min-height: 3;
        margin-bottom: 1;
        padding: 1;
        background: $background;
    }
    
    /* Chat messages */
    .assistant-message {
        margin-bottom: 1;
        padding: 1 2;
        width: 100%;
        height: auto;
    }
    
    .user-message {
        margin-bottom: 1;
        padding: 1 2;
        width: 100%;
        height: auto;
    }
    
    .message-content {
        padding: 2 3;
        min-height: 2;
        height: auto;
        overflow-x: auto;
        overflow-y: auto;
    }
    
    .sender-label {
        color: #888888;
        height: 1;
    }
    
    .assistant-message .message-content {
        background: #5521b5;
        border: solid #ffffff;
        color: white;
        height: auto;
        min-height: 2;
    }
    
    .user-message .message-content {
        background: #272820;
        color: white;
        border: solid #ffffff;
        height: auto;
        min-height: 2;
    }
    
    /* Response status */
    .response-status {
        width: 100%;
        height: auto;
        padding: 0 2;
        align-horizontal: center;
        background: transparent;
    }
    
    .status-text {
        margin-left: 1;
        color: #888888;
    }
    
    /* Chat input */
    .chat-input {
        width: 100%;
        height: auto;
        padding: 0 2;
    }
    
    .message-input {
        height: 3;
        width: 9fr;
        margin-right: 1;
    }
    
    #send-button {
        width: 1fr;
        background: #5521b5;
        color: white;
    }
    
    /* Tool output */
    .tool-output {
        margin: 1;
        width: 90%;
    }
    
    .tool-output-header {
        background: #333333;
        color: white;
        padding: 0 1;
    }
    
    .tool-output-content {
        background: #222222;
        color: #888888;
        padding: 1;
        height: auto;
        overflow: auto;
    }
    """
    
    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+d", "toggle_dark", "Toggle Dark Mode"),
        ("ctrl+s", "screenshot", "Screenshot")
    ]
    
    def __init__(
        self, 
        scorecard: Optional[Any] = None, 
        score: Optional[Any] = None,
        repl: Optional["ScoreChatREPL"] = None
    ):
        """Initialize the Textual UI app.
        
        Args:
            scorecard: The scorecard to use
            score: The score to use
            repl: An existing ScoreChatREPL instance
        """
        super().__init__()
        self.scorecard = scorecard
        self.score = score
        self.repl = repl
        self.chat_history = []
        self.current_ai_message = None
        self.current_tool_output = None
        self.is_processing = False
    
    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        # Chat container (takes up most of the space)
        with ScrollableContainer(id="chat-container"):
            yield ChatContainer()
        
        # Input container
        with Container(id="input-container"):
            yield ChatInput()
        
        # Footer
        yield Footer()
    
    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.title = "Plexus Score Chat REPL"
        
        # Store references to components
        self.chat_container = self.query_one(ChatContainer)
        self.chat_input = self.query_one(ChatInput)
        self.response_status = self.query_one(ResponseStatus)
        
        # Initialize the REPL if not already provided
        if self.repl is None:
            self.repl = ScoreChatREPL(
                callbacks=[TextualStreamingCallbackHandler(self)],
                scorecard=self.scorecard,
                score=self.score
            )
            # If scorecard and score were provided, initialize the system message
            if self.scorecard and self.score:
                self.repl.initialize_system_message()
                
        # Display initial welcome message and trigger analysis
        if self.scorecard and self.score:
            # Use a worker to run the async function
            self.run_worker(self.get_initial_analysis)
    
    async def on_chat_input_submit_message(self, message: ChatInput.SubmitMessage) -> None:
        """Handle submit message events from the chat input."""
        if self.is_processing:
            return
        
        user_message = message.message.strip()
        if not user_message:
            return
        
        # Add user message to chat
        self.chat_container.add_message("You", user_message, is_user=True)
        
        # Ensure the user message is visible
        self.force_scroll()
        
        # Schedule another scroll after a short delay to make sure it's visible
        self.set_timer(0.1, self.force_scroll)
        
        # Process user input in a worker to keep UI responsive
        self.is_processing = True
        worker = self.run_worker(self.process_user_input(user_message))
    
    async def process_user_input(self, user_message: str) -> None:
        """Process user input and get response from REPL.
        
        Args:
            user_message: The user message to process
        """
        try:
            # Show we're processing
            self.response_status.show_responding()
            
            # Add the user input to chat history
            self.repl.chat_history.append(HumanMessage(content=user_message))
            
            # Start processing loop for handling tool calls and responses
            finished = False
            while not finished:
                try:
                    # Get response from LLM with tools
                    ai_msg = await asyncio.to_thread(
                        lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
                    )
                    
                    # Add the model response to chat history
                    self.repl.chat_history.append(ai_msg)
                    
                    # Check if the response has tool calls
                    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        # Process each tool call
                        for tool_call in ai_msg.tool_calls:
                            # Extract the tool input
                            tool_input = {}
                            if 'args' in tool_call:
                                tool_input = tool_call['args']
                            elif 'input' in tool_call:
                                tool_input = tool_call['input']
                            
                            # Update tool output widget
                            tool_name = tool_call.get('name', 'unknown')
                            self.add_tool_start(tool_name, tool_input)
                            # Force scrolling to bottom after tool start
                            self.force_scroll()
                            
                            # Process the command
                            command = tool_input.get('command', '')
                            tool_result = None
                            
                            if command == "view":
                                file_path = tool_input.get('path', '').lstrip('/')
                                try:
                                    tool_result = await asyncio.to_thread(
                                        self.repl.file_editor.view, file_path
                                    )
                                except FileNotFoundError:
                                    tool_result = f"Error: File not found: {file_path}"
                                
                            elif command == "str_replace":
                                file_path = tool_input.get('path', '').lstrip('/')
                                old_str = tool_input.get('old_str', '')
                                new_str = tool_input.get('new_str', '')
                                
                                if not file_path or not old_str or 'new_str' not in tool_input:
                                    tool_result = "Error: Missing required parameters"
                                else:
                                    tool_result = await asyncio.to_thread(
                                        self.repl.file_editor.str_replace, file_path, old_str, new_str
                                    )
                                
                            elif command == "undo_edit":
                                file_path = tool_input.get('path', '').lstrip('/')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.undo_edit, file_path
                                )
                                
                            elif command == "insert":
                                file_path = tool_input.get('path', '').lstrip('/')
                                insert_line = tool_input.get('insert_line', 0)
                                new_str = tool_input.get('new_str', '')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.insert, file_path, insert_line, new_str
                                )
                                
                            elif command == "create":
                                file_path = tool_input.get('path', '').lstrip('/')
                                content = tool_input.get('content', '')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.create, file_path, content
                                )
                            
                            # Update tool output with result
                            if tool_result is not None:
                                # Update UI
                                self.add_tool_end(tool_result)
                                # Force scrolling to bottom after tool result
                                self.force_scroll()
                                
                                # Create a ToolMessage to send back to the model
                                tool_msg = ToolMessage(
                                    content=tool_result,
                                    tool_call_id=tool_call.get('id', ''),
                                    name=tool_name
                                )
                                
                                # Add the tool message to chat history
                                self.repl.chat_history.append(tool_msg)
                    else:
                        # No tool calls, add the AI response to the UI
                        content = ai_msg.content if hasattr(ai_msg, 'content') else ""
                        
                        if content:
                            if isinstance(content, str):
                                self.add_ai_response(content)
                            elif isinstance(content, list):
                                content_text = ""
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        content_text += item["text"]
                                    elif isinstance(item, str):
                                        content_text += item
                                if content_text:
                                    self.add_ai_response(content_text)
                        
                        # Force scrolling to bottom after AI response
                        self.force_scroll()
                        
                        # We're done processing
                        finished = True
                
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # Display the error in chat
                    self.chat_container.add_message("Plexus", f"**Error:** {str(e)}", is_user=False)
                    
                    # Force scrolling to bottom for error message
                    self.force_scroll()
                    
                    finished = True
        
        finally:
            self.response_status.hide_responding()
            self.is_processing = False

    def force_scroll(self) -> None:
        """Force the chat container to scroll to the bottom."""
        # Call the force_scroll method on the chat container
        self.chat_container.force_scroll()
        
        # Schedule another scroll after a brief delay
        self.set_timer(0.2, self._delayed_scroll)
    
    def _delayed_scroll(self) -> None:
        """Called after a delay to ensure scrolling works."""
        self.chat_container.force_scroll()
    
    def add_ai_response(self, text: str) -> None:
        """Add an AI response to the chat.
        
        Args:
            text: The text of the AI response
        """
        self.chat_container.add_message("Plexus", text, is_user=False)
        self.current_ai_message = None
        # Force scrolling to the bottom
        self.force_scroll()
    
    def update_ai_response(self, text: str) -> None:
        """Update the current AI response with new text.
        
        Args:
            text: The updated text for the AI response
        """
        if self.current_ai_message is None:
            self.current_ai_message = text
            self.chat_container.add_message("Plexus", text, is_user=False)
        else:
            self.current_ai_message += text
            # This would typically update the existing message, but for now
            # we'll just add a new message with the complete text
            self.chat_container.add_message("Plexus", self.current_ai_message, is_user=False)
        
        # Force scrolling to the bottom
        self.force_scroll()
    
    def add_tool_start(self, tool_name: str, input_str: str) -> None:
        """Add a tool start notification to the chat.
        
        Args:
            tool_name: The name of the tool
            input_str: The input to the tool
        """
        # Create a new tool output widget
        tool_output = ToolOutput()
        self.current_tool_output = tool_output
        
        # Update the tool output with the input information
        tool_output.update_output(tool_name, input_str)
        
        # Add it to the chat container
        self.chat_container.query_one("#message-list").mount(tool_output)
        self.chat_container.scroll_end(animate=False)
    
    def add_tool_end(self, output: str) -> None:
        """Add a tool end notification with the output.
        
        Args:
            output: The output from the tool
        """
        if self.current_tool_output:
            self.current_tool_output.set_output(output)
            self.current_tool_output = None
            self.chat_container.scroll_end(animate=False)
    
    def action_quit(self) -> None:
        """Quit the application."""
        self.exit()

    async def get_initial_analysis(self):
        """Get the initial analysis for the loaded score."""
        # Add the initial welcome message
        self.chat_container.add_message("Plexus", "Welcome! I'm Plexus, your AI assistant for score configuration. I'll analyze this score configuration and tell you what I see.", is_user=False)
        # Force scrolling to make welcome message visible
        self.force_scroll()
        
        # Show we're processing
        self.response_status.show_responding()
        
        try:
            # Add the initial analysis question to chat history
            user_message = "Please analyze this score configuration and tell me what you see."
            self.repl.chat_history.append(HumanMessage(content=user_message))
            
            # Start processing loop for handling tool calls and responses
            finished = False
            while not finished:
                try:
                    # Get response from LLM with tools
                    ai_msg = await asyncio.to_thread(
                        lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
                    )
                    
                    # Add the model response to chat history
                    self.repl.chat_history.append(ai_msg)
                    
                    # Check if the response has tool calls
                    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        # Process each tool call
                        for tool_call in ai_msg.tool_calls:
                            # Extract the tool input
                            tool_input = {}
                            if 'args' in tool_call:
                                tool_input = tool_call['args']
                            elif 'input' in tool_call:
                                tool_input = tool_call['input']
                            
                            # Update tool output widget
                            tool_name = tool_call.get('name', 'unknown')
                            self.add_tool_start(tool_name, tool_input)
                            # Force scrolling to bottom after tool start
                            self.force_scroll()
                            
                            # Process the command
                            command = tool_input.get('command', '')
                            tool_result = None
                            
                            if command == "view":
                                file_path = tool_input.get('path', '').lstrip('/')
                                try:
                                    tool_result = await asyncio.to_thread(
                                        self.repl.file_editor.view, file_path
                                    )
                                except FileNotFoundError:
                                    tool_result = f"Error: File not found: {file_path}"
                                
                            elif command == "str_replace":
                                file_path = tool_input.get('path', '').lstrip('/')
                                old_str = tool_input.get('old_str', '')
                                new_str = tool_input.get('new_str', '')
                                
                                if not file_path or not old_str or 'new_str' not in tool_input:
                                    tool_result = "Error: Missing required parameters"
                                else:
                                    tool_result = await asyncio.to_thread(
                                        self.repl.file_editor.str_replace, file_path, old_str, new_str
                                    )
                                
                            elif command == "undo_edit":
                                file_path = tool_input.get('path', '').lstrip('/')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.undo_edit, file_path
                                )
                                
                            elif command == "insert":
                                file_path = tool_input.get('path', '').lstrip('/')
                                insert_line = tool_input.get('insert_line', 0)
                                new_str = tool_input.get('new_str', '')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.insert, file_path, insert_line, new_str
                                )
                                
                            elif command == "create":
                                file_path = tool_input.get('path', '').lstrip('/')
                                content = tool_input.get('content', '')
                                tool_result = await asyncio.to_thread(
                                    self.repl.file_editor.create, file_path, content
                                )
                            
                            # Update tool output with result
                            if tool_result is not None:
                                # Update UI
                                self.add_tool_end(tool_result)
                                # Force scrolling to bottom after tool result
                                self.force_scroll()
                                
                                # Create a ToolMessage to send back to the model
                                tool_msg = ToolMessage(
                                    content=tool_result,
                                    tool_call_id=tool_call.get('id', ''),
                                    name=tool_name
                                )
                                
                                # Add the tool message to chat history
                                self.repl.chat_history.append(tool_msg)
                    else:
                        # No tool calls, add the AI response to the UI
                        content = ai_msg.content if hasattr(ai_msg, 'content') else ""
                        
                        if content:
                            if isinstance(content, str):
                                self.add_ai_response(content)
                            elif isinstance(content, list):
                                content_text = ""
                                for item in content:
                                    if isinstance(item, dict) and "text" in item:
                                        content_text += item["text"]
                                    elif isinstance(item, str):
                                        content_text += item
                                if content_text:
                                    self.add_ai_response(content_text)
                        
                        # Force scrolling to bottom after AI response
                        self.force_scroll()
                        
                        # We're done processing
                        finished = True
                
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # Display the error in chat
                    self.chat_container.add_message("Plexus", f"**Error:** {str(e)}", is_user=False)
                    # Force scrolling to bottom for error message
                    self.force_scroll()
                    
                    finished = True
        
        finally:
            self.response_status.hide_responding()
            self.is_processing = False

class ScoreChatREPL:
    """Interactive REPL for working with Plexus scores."""
    
    def __init__(self, scorecard: Optional[str] = None, score: Optional[str] = None, **kwargs):
        # Ignore prompt_toolkit parameter if passed from ScoreCommands.py
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

CRITICAL PLANNING REQUIREMENT: Before making ANY changes to files, you MUST:

1. THINK FIRST: Analyze what the user is asking for and understand the implications
2. CREATE A DETAILED PLAN: Explain step-by-step what changes you will make and why
3. IDENTIFY POTENTIAL ISSUES: Consider what could go wrong and how to avoid problems
4. GET USER CONFIRMATION: Present your plan to the user and ask if they want to proceed
5. ONLY THEN: Execute the file changes using the str_replace_editor tool

When the user requests changes, follow this exact process:
- First, explain your understanding of their request
- Then, provide a detailed plan of the specific changes you will make
- Explain the reasoning behind each change
- Ask the user to confirm before proceeding with any file modifications
- Only after confirmation, use the str_replace_editor tool to make changes

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
            doc_path = Path(__file__).parent.parent / "docs" / "score-yaml-format.md"
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

    def run(self, use_textual: bool = False):
        """Run the REPL with either Rich or Textual UI.
        
        Args:
            use_textual: Whether to use the Textual UI (default: False, uses Rich)
        """
        try:
            # If scorecard and score were provided, load them and get initial response
            if self.scorecard and self.score:
                self.load_score(self.scorecard, self.score)
                # Initialize system message with the loaded score
                self.initialize_system_message()
            
            if use_textual:
                # Run the Textual UI
                app = TextualScoreChatApp(self)
                app.run()
            else:
                # Original Rich-based REPL
                # If scorecard and score were provided, get initial response
                if self.scorecard and self.score:
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
        
        tool_output = self.query_one(ToolOutput)
        
        if cmd == "help":
            # Show help information
            help_text = """
[bold]Available Commands:[/bold]
/help             - Show this help message
/list             - List available scorecards
/pull <s> <s>     - Pull a score's current version
/push <s> <s>     - Push a score's updated version
/exit             - Exit the REPL
            """
            # Display using the AI message format
            chat_container = self.query_one(ChatContainer)
            chat_container.add_ai_message(help_text)
            
        elif cmd == "list":
            # List scorecards
            scorecards = self.list_scorecards()
            if scorecards:
                scorecard_text = "[bold]Available Scorecards:[/bold]\n"
                for scorecard in scorecards:
                    scorecard_text += f"{scorecard['name']} ({scorecard['key']})\n"
                chat_container = self.query_one(ChatContainer)
                chat_container.add_ai_message(scorecard_text)
            else:
                chat_container = self.query_one(ChatContainer)
                chat_container.add_ai_message("[yellow]No scorecards found.[/yellow]")
                
        elif cmd == "pull":
            if len(args) < 2:
                chat_container = self.query_one(ChatContainer)
                chat_container.add_ai_message("[red]Usage: /pull <scorecard> <score>[/red]")
                return
            
            self.update_status(f"Pulling score {args[1]} from scorecard {args[0]}...")
            result = self.pull_score(args[0], args[1])
            chat_container = self.query_one(ChatContainer)
            chat_container.add_ai_message(f"Pull result: {result}")
            self.update_status("Ready")
            
        elif cmd == "push":
            if len(args) < 2:
                chat_container = self.query_one(ChatContainer)
                chat_container.add_ai_message("[red]Usage: /push <scorecard> <score>[/red]")
                return
            
            self.update_status(f"Pushing score {args[1]} to scorecard {args[0]}...")
            result = self.push_score(args[0], args[1])
            chat_container = self.query_one(ChatContainer)
            chat_container.add_ai_message(f"Push result: {result}")
            self.update_status("Ready")
            
        elif cmd == "exit":
            self.console.print("[yellow]Goodbye![/yellow]")
            exit(0)
        else:
            chat_container = self.query_one(ChatContainer)
            chat_container.add_ai_message(f"[red]Unknown command: {cmd}[/red]")
    
    @work(exclusive=True)
    async def process_natural_language(self, user_input: str):
        """Process natural language input asynchronously."""
        self.is_processing = True
        
        # Show "Plexus is responding" indicator
        response_status = self.query_one(ResponseStatus)
        response_status.set_plexus_responding()
        response_status.display = True
        
        self.update_status("Processing...")
        
        try:
            # Clear tool output
            tool_output = self.query_one(ToolOutput)
            tool_output.clear()
            
            # Add the user input to chat history
            self.chat_history.append(HumanMessage(content=user_input))
            
            # Start processing loop
            finished = False
            while not finished:
                try:
                    # Get response from Claude
                    ai_msg = await self.llm_with_tools.ainvoke(self.chat_history)
                    
                    # Add the model response to chat history
                    self.chat_history.append(ai_msg)
                    
                    # Check if the response has tool calls
                    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        # Process each tool call
                        for tool_call in ai_msg.tool_calls:
                            # Extract the tool input
                            tool_input = {}
                            if 'args' in tool_call:
                                tool_input = tool_call['args']
                            elif 'input' in tool_call:
                                tool_input = tool_call['input']
                            
                            # Update tool output widget
                            tool_name = tool_call.get('name', 'unknown')
                            tool_output.update_output(tool_name, tool_input)
                            tool_output.add_class("active")
                            
                            # Process the command
                            command = tool_input.get('command', '')
                            tool_result = None
                            
                            if command == "view":
                                file_path = tool_input.get('path', '').lstrip('/')
                                try:
                                    tool_result = self.file_editor.view(file_path)
                                except FileNotFoundError:
                                    tool_result = f"Error: File not found: {file_path}"
                                
                            elif command == "str_replace":
                                file_path = tool_input.get('path', '').lstrip('/')
                                old_str = tool_input.get('old_str', '')
                                new_str = tool_input.get('new_str', '')
                                
                                if not file_path or not old_str or 'new_str' not in tool_input:
                                    tool_result = "Error: Missing required parameters"
                                else:
                                    tool_result = self.file_editor.str_replace(file_path, old_str, new_str)
                                
                            elif command == "undo_edit":
                                file_path = tool_input.get('path', '').lstrip('/')
                                tool_result = self.file_editor.undo_edit(file_path)
                                
                            elif command == "insert":
                                file_path = tool_input.get('path', '').lstrip('/')
                                insert_line = tool_input.get('insert_line', 0)
                                new_str = tool_input.get('new_str', '')
                                tool_result = self.file_editor.insert(file_path, insert_line, new_str)
                                
                            elif command == "create":
                                file_path = tool_input.get('path', '').lstrip('/')
                                content = tool_input.get('content', '')
                                tool_result = self.file_editor.create(file_path, content)
                            
                            # Update tool output with result
                            if tool_result is not None:
                                # Update UI
                                tool_output.update_output(tool_name, tool_input, tool_result)
                                
                                # Create a ToolMessage to send back to the model
                                tool_msg = ToolMessage(
                                    content=tool_result,
                                    tool_call_id=tool_call.get('id', ''),
                                    name=tool_name
                                )
                                
                                # Add the tool message to chat history
                                self.chat_history.append(tool_msg)
                    else:
                        # No tool calls, we're done
                        finished = True
                
                except Exception as e:
                    import traceback
                    error_details = traceback.format_exc()
                    
                    # Display the error in chat
                    chat_container = self.query_one(ChatContainer)
                    chat_container.add_ai_message(f"[red]Error: {str(e)}[/red]")
                    
                    # Also update the tool output
                    tool_output = self.query_one(ToolOutput)
                    tool_output.update_output("Error", {}, f"{str(e)}\n{error_details}")
                    tool_output.add_class("active")
                    
                    finished = True
        
        finally:
            # Hide the "Plexus is responding" indicator
            self.query_one(ResponseStatus).display = False
            self.is_processing = False
            self.update_status("Ready")
    
    def get_initial_response(self):
        """Get the initial response for a loaded score."""
        if not self.chat_history:
            return
        
        # Add the initial prompt to the chat history
        self.chat_history.append(HumanMessage(content="Please analyze this score configuration and tell me what you see."))
        
        # Show "Plexus is responding" indicator 
        response_status = self.query_one(ResponseStatus)
        response_status.set_plexus_responding()
        response_status.display = True
        
        self.is_processing = True
        self.update_status("Analyzing score configuration...")
        
        # This will be handled by the streaming callback
        self.process_natural_language("Please analyze this score configuration and tell me what you see.")

    def load_score(self, scorecard: str, score: str):
        """Load a score's configuration."""
        try:
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
            
            # Get score details to get its name and champion version
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
                
                # Get the YAML file path using the correct names
                yaml_path = get_score_yaml_path(scorecard_name, score_data['name'])
                
                # Write to file
                with open(yaml_path, 'w') as f:
                    f.write(version_data['configuration'])
                
                self.console.print(f"[green]Saved score configuration to: {yaml_path}[/green]")
                
            except Exception as e:
                self.console.print(f"[red]Error pulling score: {str(e)}[/red]")

        except Exception as e:
            self.console.print(f"[red]Error loading score: {str(e)}[/red]")

    def show_help(self):
        """Show available commands."""
        help_text = """
[bold]Available Commands:[/bold]
/help             - Show this help message
/list             - List available scorecards
/pull <s> <s>     - Pull a score's current version
/push <s> <s>     - Push a score's updated version
/exit             - Exit the REPL
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
            
            self.current_scorecard = scorecard
            self.current_score = score
            
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

    def process_input(self, user_input: str):
        """Process user input and get response from the LLM.
        
        Args:
            user_input: The user message to process
        """
        # Add the user input to chat history
        self.chat_history.append(HumanMessage(content=user_input))
        
        # Process this message with tools to allow for file viewing etc.
        response = self.llm_with_tools.invoke(self.chat_history)
        
        # Add the model response to chat history
        self.chat_history.append(response)
        
        # Check for tool calls
        if hasattr(response, 'tool_calls') and response.tool_calls:
            # Process each tool call
            for tool_call in response.tool_calls:
                # Extract tool information
                tool_name = tool_call.get('name', '')
                tool_args = tool_call.get('args', {})
                
                # Process the command
                command = tool_args.get('command', '')
                tool_result = None
                
                if command == "view":
                    file_path = tool_args.get('path', '').lstrip('/')
                    try:
                        tool_result = self.file_editor.view(file_path)
                    except FileNotFoundError:
                        tool_result = f"Error: File not found: {file_path}"
                    
                elif command == "str_replace":
                    file_path = tool_args.get('path', '').lstrip('/')
                    old_str = tool_args.get('old_str', '')
                    new_str = tool_args.get('new_str', '')
                    
                    if not file_path or not old_str or 'new_str' not in tool_args:
                        tool_result = "Error: Missing required parameters"
                    else:
                        tool_result = self.file_editor.str_replace(file_path, old_str, new_str)
                    
                elif command == "undo_edit":
                    file_path = tool_args.get('path', '').lstrip('/')
                    tool_result = self.file_editor.undo_edit(file_path)
                    
                elif command == "insert":
                    file_path = tool_args.get('path', '').lstrip('/')
                    insert_line = tool_args.get('insert_line', 0)
                    new_str = tool_args.get('new_str', '')
                    tool_result = self.file_editor.insert(file_path, insert_line, new_str)
                    
                elif command == "create":
                    file_path = tool_args.get('path', '').lstrip('/')
                    content = tool_args.get('content', '')
                    tool_result = self.file_editor.create(file_path, content)
                
                # If we have a tool result, create a tool message
                if tool_result is not None:
                    tool_msg = ToolMessage(
                        content=tool_result,
                        tool_call_id=tool_call.get('id', ''),
                        name=tool_name
                    )
                    
                    # Add the tool message to chat history
                    self.chat_history.append(tool_msg)
            
            # Get another response after tools have been processed
            final_response = self.llm_with_tools.invoke(self.chat_history)
            
            # Add the final response to chat history
            self.chat_history.append(final_response)
            
            return final_response.content
        
        # Return the response content
        return response.content

def run_textual_chat(scorecard: Optional[str] = None, score: Optional[str] = None):
    """Run the Textual-based chat interface.
    
    Args:
        scorecard: The scorecard to use
        score: The score to use
    """
    # Configure basic logging
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the Textual app
    try:
        console.print("Starting Plexus Score Chat Textual UI...")
        
        # First create a REPL instance to load the score
        repl = ScoreChatREPL(scorecard=scorecard, score=score)
        
        # Load the score if specified
        if scorecard and score:
            console.print(f"Loading score '{score}' from scorecard '{scorecard}'...")
            repl.load_score(scorecard, score)
            repl.initialize_system_message()
        
        # Now create the app with the initialized REPL
        app = TextualScoreChatApp(
            scorecard=scorecard,
            score=score,
            repl=repl  # Pass the initialized REPL with loaded score
        )
        app.run()
    except Exception as e:
        console.print(f"Error running Textual UI: {e}")
        import traceback
        console.print(traceback.format_exc())
        console.print("\nFalling back to traditional REPL...")
        # Fall back to traditional REPL
        try:
            repl = ScoreChatREPL(scorecard=scorecard, score=score)
            repl.run()
        except Exception as repl_error:
            console.print(f"Error falling back to traditional REPL: {repl_error}")
            console.print(traceback.format_exc())
            console.print("\nUnable to start any interface. Please check your environment setup.")

def main():
    """Main entry point when run as a module."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run the Score Chat REPL.")
    parser.add_argument(
        "--textual", "-t", 
        action="store_true",
        help="Use the Textual UI instead of the Rich UI."
    )
    parser.add_argument(
        "--scorecard", "-s",
        help="Scorecard identifier (ID, name, key, or external ID)."
    )
    parser.add_argument(
        "--score", "-q",
        help="Score identifier (ID, name, key)."
    )
    
    args = parser.parse_args()
    
    if args.textual:
        # Use the run_textual_chat function which now properly loads the score
        run_textual_chat(scorecard=args.scorecard, score=args.score)
    else:
        # Use the traditional Rich UI
        repl = ScoreChatREPL(scorecard=args.scorecard, score=args.score)
        repl.run()

if __name__ == "__main__":
    main()
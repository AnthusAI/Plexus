"""
Implementation of a Textual-based UI for the Plexus score chat command.

This module provides an interactive TUI interface for working with Plexus scores,
using Textual for beautiful terminal UI, with streaming LLM responses and command input.
"""

from typing import Optional, List, Dict, Any, Callable
import os
import asyncio
import sys
import traceback
import logging
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, Input, Static, Label
from textual.reactive import reactive
from textual import events

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.panel import Panel

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import BaseCallbackHandler

# Import with fallback mechanism for CLI integration
try:
    from plexus.cli.score_chat_repl import StreamingCallbackHandler, ScoreChatREPL
    from plexus.dashboard.api.client import PlexusDashboardClient
    from plexus.cli.file_editor import FileEditor
    from plexus.cli.shared import get_score_yaml_path
    from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
except ImportError as e:
    print(f"Warning: Failed to import Plexus modules: {e}")
    print("Textual UI requires the Plexus CLI environment to be set up properly.")
    print("Please ensure you're running the command from the correct directory.")
    raise

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables early
import dotenv
dotenv_path = os.path.expanduser("~/projects/Call-Criteria-Python/.env")
if os.path.exists(dotenv_path):
    dotenv.load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"Warning: No .env file found at {dotenv_path}")

class TextualStreamingHandler(BaseCallbackHandler):
    """Handler for streaming tokens to the Textual UI."""

    def __init__(self, update_callback: Callable[[str], None]):
        """Initialize the handler."""
        self.update_callback = update_callback
        self.current_text = ""
        self.first_token = True
        self.current_tool_call = None
        self.tool_calls = []
        self.streaming_active = False
        self.buffer = ""  # Buffer to collect tool call JSON data

    def on_llm_start(self, *args, **kwargs):
        """Called when the LLM starts generating."""
        self.current_text = ""
        self.first_token = True
        self.current_tool_call = None
        self.streaming_active = True
        self.buffer = ""  # Clear the buffer
        
    def on_llm_new_token(self, token: str, *args, **kwargs):
        """Called when a new token is generated."""
        # Skip tokens that aren't strings
        if not isinstance(token, str):
            return
            
        # Skip tool call data for streaming display
        if any(marker in token for marker in ['toolu_', '"command":', '"input":', 'tool_use', '"new_str":', '"old_str":']):
            self.buffer += token
            return
            
        if self.first_token:
            self.current_text = "AI: " + token
            self.first_token = False
        else:
            self.current_text += token
        
        # Update the display with new text if streaming is active
        if self.streaming_active:
            self.update_callback(self.current_text)
    
    def on_llm_end(self, *args, **kwargs):
        """Called when the LLM finishes generating."""
        self.streaming_active = False
        # Final update to ensure all text is displayed
        self.update_callback(self.current_text)
    
    def on_llm_error(self, error: Exception, *args, **kwargs):
        """Called when the LLM encounters an error."""
        self.streaming_active = False
        error_text = f"{self.current_text}\n\n[red]Error: {str(error)}[/red]"
        self.update_callback(error_text)
    
    def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs):
        """Called when a tool starts being used."""
        # Create a simplified tool call
        self.current_tool_call = {
            'name': serialized.get('name', 'unknown tool'),
            'input': input_str,
            'output': None
        }
        self.current_text += f"\n[Using tool: {self.current_tool_call['name']}]"
        self.update_callback(self.current_text)
    
    def on_tool_end(self, output: str, **kwargs):
        """Called when a tool finishes being used."""
        if self.current_tool_call:
            self.current_tool_call['output'] = output
            self.tool_calls.append(self.current_tool_call.copy())
            self.current_tool_call = None
            self.current_text += "\n[Tool finished]"
            self.update_callback(self.current_text)
    
    def on_chain_start(self, *args, **kwargs):
        """Called when a chain starts."""
        pass
        
    def on_chain_end(self, *args, **kwargs):
        """Called when a chain ends."""
        pass
        
    def __call__(self, *args, **kwargs):
        """Make the handler callable to avoid strip errors."""
        # This is critical - return self, not the result of any function calls
        return self

class ChatMessage(Static):
    """A widget to display a chat message."""
    
    def __init__(self, message_type: str, content: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message_type = message_type
        self.message_content = content
        
        # Add styling classes based on message type
        if message_type == "human":
            self.add_class("user-message")
        elif message_type == "ai":
            self.add_class("assistant-message")
        
    def compose(self) -> ComposeResult:
        if self.message_type == "human":
            # Create a user message bubble
            with Container(classes="message-container user-container"):
                yield Static("You", classes="sender-label user-label")
                static = Static(self.message_content, classes="message-content")
                static.border_title = "You"
                yield static
        elif self.message_type == "ai":
            # Create an AI message bubble with Markdown formatting
            with Container(classes="message-container ai-container"):
                yield Static("Plexus", classes="sender-label ai-label")
                static = Static(Markdown(self.message_content), classes="message-content")
                static.border_title = "Plexus"
                yield static
        elif self.message_type == "system":
            # System messages are simple without a bubble
            yield Static(f"[dim]{self.message_content}[/dim]", classes="system-message")
        elif self.message_type == "tool":
            # Tool messages have a special format
            yield Static(f"[bold green]Tool:[/bold green] {self.message_content}", classes="tool-message")

class ScoreChatApp(App):
    """Textual app for Plexus score chat."""
    
    CSS = """
    #chat-container {
        height: 1fr;
        border: solid green;
        overflow-y: auto;
        padding: 1 2;
    }
    
    #input-container {
        height: 3;
        margin: 1 0;
        border: solid green;
        padding: 0;
    }
    
    #current-input {
        height: 1;
        margin: 0;
        padding: 0 2;
        color: #FFFFFF;
    }
    
    ChatMessage {
        margin: 1 0;
        width: 100%;
    }

    /* Message containers */
    .message-container {
        width: 100%;
        margin: 1 0;
    }

    .user-container {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
    }

    .ai-container {
        display: flex;
        flex-direction: column;
        align-items: flex-start;
    }

    /* Styling for message bubbles */
    .user-message .message-content {
        background: #2b5278;
        color: #ffffff;
        margin-left: auto;
        margin-right: 0;
        padding: 1 2;
        border: heavy rounded #375a7f;
        max-width: 80%;
        min-width: 20%;
        border-title-color: #88aadd;
        border-title-background: #1b3254;
        border-title-align: right;
    }
    
    .assistant-message .message-content {
        background: #3a3a3a;
        color: #ffffff;
        margin-right: auto;
        margin-left: 0;
        padding: 1 2;
        border: heavy rounded #4a4a4a;
        max-width: 80%;
        min-width: 20%;
        border-title-color: #88dd88;
        border-title-background: #1b3b1b;
        border-title-align: left;
    }

    /* Sender labels */
    .sender-label {
        color: #888888;
        margin: 0 1;
        text-align: right;
        display: none;  /* Hide these for a cleaner look, using border titles instead */
    }

    .system-message {
        color: #888888;
        text-align: center;
        margin: 1 0;
    }

    .tool-message {
        color: #25bc26;
        margin: 1 0;
        padding: 0 2;
    }
    """
    
    def __init__(
        self, 
        scorecard: Optional[str] = None, 
        score: Optional[str] = None,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.scorecard = scorecard
        self.score = score
        self.chat_history = []
        self.messages = []  # List to track all messages for easier management
        self.initialization_error = None
        
        # Check for API key
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self.initialization_error = "ANTHROPIC_API_KEY environment variable is not set. This application requires an API key for Claude to function."
        
        # Initialize the ScoreChatREPL for backend functionality
        try:
            self.repl = ScoreChatREPL(scorecard=scorecard, score=score)
            
            # Replace the callback handler with our Textual-compatible one
            self.streaming_handler = TextualStreamingHandler(self.update_response)
            self.repl.callback_handler = self.streaming_handler
            
            # Replace the LLM instances with ones using our callback handler
            self.setup_llm()
        except Exception as e:
            logger.error(f"Error initializing REPL: {e}")
            self.initialization_error = f"Error initializing REPL: {e}"
    
    def setup_llm(self):
        """Set up the LLM with our custom callback handler."""
        # Get API key from environment
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self.add_message("No Anthropic API key found. Chat functionality will be limited.", message_type="system")
            return
        
        try:
            # Create the streaming handler first - this is critical
            self.streaming_handler = TextualStreamingHandler(self.update_response)
            
            # Create base LLM with streaming - exactly like in ScoreChatREPL
            self.repl.llm = ChatAnthropic(
                model_name="claude-3-7-sonnet-20250219",
                temperature=0.7,
                streaming=True,
                anthropic_api_key=api_key,
                max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
                callbacks=[self.streaming_handler]
            )
            
            # Create LLM with tools that also has streaming enabled - exactly like in ScoreChatREPL
            self.repl.llm_with_tools = ChatAnthropic(
                model_name="claude-3-7-sonnet-20250219",
                temperature=0.7,
                streaming=True,
                anthropic_api_key=api_key,
                max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
                callbacks=[self.streaming_handler]
            ).bind_tools([{
                "type": "text_editor_20250124",
                "name": "str_replace_editor"
            }])
        except Exception as e:
            logging.error(f"Error setting up LLM: {e}", exc_info=True)
            self.add_message(f"Error setting up LLM: {str(e)}", message_type="system")
    
    async def on_mount(self) -> None:
        """When the app is mounted, initialize the chat if scorecard/score were provided."""
        # Initialize our input buffer for key-based input
        self.input_buffer = ""
        
        # Make sure key events can be captured
        self.capture_keys = True
        
        # Set a timer to ensure the cursor keeps blinking
        self.set_interval(0.5, self.update_current_input_display)
        
        # If scorecard and score were provided, load them and get initial response
        if self.scorecard and self.score:
            # First, print debug info about the parameters
            logging.info(f"Initializing with scorecard={self.scorecard}, score={self.score}")
            
            # Add a loading message
            self.add_message(f"Loading score '{self.score}' from scorecard '{self.scorecard}'...", message_type="system")
            
            # First make sure the REPL loads the score, exactly like in the REPL class
            try:
                # Make sure we're passing the actual scorecard name/key, not "--scorecard"
                # This is likely the root cause of our issue
                actual_scorecard = self.scorecard
                if actual_scorecard.startswith("--"):
                    # This is a parameter name, not a value
                    self.add_message(f"Warning: Scorecard parameter '{actual_scorecard}' looks like a flag, not a value.", message_type="system")
                    
                    # Try to check if it was actually intended to be a value
                    if len(actual_scorecard) > 2 and not self.scorecard.startswith("--scorecard"):
                        # Use the value after "--" as the actual scorecard name
                        actual_scorecard = actual_scorecard[2:]
                    
                # Load the score - this will pull it from the server if needed
                self.repl.load_score(actual_scorecard, self.score)
                self.add_message(f"Successfully loaded score.", message_type="system")
                
                # Initialize the system message - this sets up the proper Plexus context
                self.repl.initialize_system_message()
                
                # Start async task to get the initial response
                asyncio.create_task(self.get_initial_response())
            except Exception as e:
                self.add_message(f"Error initializing: {str(e)}", message_type="system")
                logging.error(f"Error initializing: {e}", exc_info=True)
        
    def on_key(self, event: events.Key) -> None:
        """Handle key events for input capture."""
        # Log what key was pressed for debugging
        logging.info(f"Key pressed: {event.key}")
        
        # Direct key code for Ctrl+J (10 is the ASCII code for line feed/newline)
        if event.key == "ctrl+j":
            # Add a newline character
            self.input_buffer += "\n"
            self.update_current_input_display()
            return
                
        # Handle special keys
        if event.key == "enter":
            # Regular mode: submit or check for special commands
            if self.input_buffer:
                # Regular submission
                user_input = self.input_buffer
                # Log the submission
                logging.info(f"Submitting input: {user_input}")
                # Add the user message to the chat
                self.add_message(user_input, from_user=True, message_type="human")
                # Process the input 
                if user_input.startswith("/"):
                    asyncio.create_task(self.handle_command(user_input[1:]))
                elif user_input.lower() in ["exit", "quit"]:
                    self.exit()
                elif user_input.lower() == "help":
                    self.show_help()
                else:
                    # Handle as natural language input
                    asyncio.create_task(self.handle_natural_language(user_input))
                
                # Clear the buffer
                self.input_buffer = ""
                self.update_current_input_display()
        elif event.key == "backspace":
            # Remove the last character from the buffer
            if self.input_buffer:
                self.input_buffer = self.input_buffer[:-1]
                # Update display
                self.update_current_input_display()
        elif event.key == "escape":
            # Clear the entire buffer
            self.input_buffer = ""
            self.update_current_input_display()
        elif hasattr(event, 'character') and event.character:
            # Add the character to the buffer if it's a printable character
            # Skip control characters like arrow keys
            if len(event.character) == 1 and event.character.isprintable():
                self.input_buffer += event.character
                # Update display
                self.update_current_input_display()
                
    def update_current_input_display(self):
        """Update the display of the current input with proper formatting."""
        # Add a flashing cursor at the end of the input text
        current_text = self.input_buffer
        # Show a flashing cursor indicator
        cursor_text = current_text + "[blink]|[/blink]"
        self.query_one("#current-input").update(cursor_text)
        
    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        
        # Chat message display area (scrollable)
        with ScrollableContainer(id="chat-container"):
            # Welcome message
            yield ChatMessage("system", "Welcome to Plexus Score Chat! Type your messages below or use commands like /help, /list, /pull, /push, or exit/quit. Plexus specializes in configuring scorecard scores for call center QA.")
            
            # Display any initialization errors
            if self.initialization_error:
                yield ChatMessage("system", self.initialization_error)
        
        # Input container at the bottom - simpler with just a label showing what you're typing
        with Container(id="input-container"):
            # Replace input with a simple label showing current input
            input_label = Label("[blink]|[/blink]", id="current-input")
            input_label.can_focus = True
            yield input_label
        
        yield Footer()
    
    async def handle_command(self, command: str):
        """Handle explicit commands."""
        parts = command.split()
        cmd = parts[0]
        args = parts[1:]
        
        if cmd == "help":
            self.show_help()
        elif cmd == "list":
            await self.list_scorecards()
        elif cmd == "pull":
            if len(args) < 2:
                self.add_message("Usage: /pull <scorecard> <score>", message_type="system")
                return
            await self.pull_score(args[0], args[1])
        elif cmd == "push":
            if len(args) < 2:
                self.add_message("Usage: /push <scorecard> <score>", message_type="system")
                return
            await self.push_score(args[0], args[1])
        elif cmd == "debug":
            # Add a debug command to show the system message
            self.show_system_message()
        else:
            self.add_message(f"Unknown command: {cmd}", message_type="system")
    
    def show_help(self):
        """Show available commands."""
        help_text = """
Available Commands:
/help             - Show this help message
/list             - List available scorecards
/pull             - Pull a score's current version
/push             - Push a score's updated version
/debug            - Show debugging information
/ml               - Enter multiline mode (press Enter for newlines, /end to submit)
exit              - Exit the app (no slash needed)
quit              - Same as exit (no slash needed)

Natural Language:
You can also just ask questions or describe what you'd like to do in plain English.
"""
        self.add_message(help_text, from_user=False, message_type="system")
    
    async def list_scorecards(self):
        """List available scorecards."""
        self.add_message("Fetching scorecards...", message_type="system")
        
        try:
            # Call in executor to avoid blocking the UI
            result = await asyncio.to_thread(
                self.repl.list_scorecards
            )
            
            # Clear the "Fetching" message
            self.clear_messages_by_type_and_content("system", "Fetching")
            
        except Exception as e:
            self.add_message(f"Error listing scorecards: {str(e)}", message_type="system")
            logging.error(f"Error listing scorecards: {e}")
    
    async def pull_score(self, scorecard: str, score: str):
        """Pull a score's current version."""
        self.add_message(f"Pulling score {score} from scorecard {scorecard}...", message_type="system")
        
        try:
            # Call in executor to avoid blocking the UI
            result = await asyncio.to_thread(
                self.repl.pull_score,
                scorecard,
                score
            )
            
            # Clear the "Pulling" message
            self.clear_messages_by_type_and_content("system", "Pulling")
            
            # Success message is added by the repl method itself through the console
            self.add_message(f"Pulled score {score} from scorecard {scorecard} successfully.", message_type="system")
            
        except Exception as e:
            self.add_message(f"Error pulling score: {str(e)}", message_type="system")
            logging.error(f"Error pulling score: {e}")
    
    async def push_score(self, scorecard: str, score: str):
        """Push a score's updated version."""
        self.add_message(f"Pushing score {score} to scorecard {scorecard}...", message_type="system")
        
        try:
            # Call in executor to avoid blocking the UI
            result = await asyncio.to_thread(
                self.repl.push_score,
                scorecard,
                score
            )
            
            # Clear the "Pushing" message
            self.clear_messages_by_type_and_content("system", "Pushing")
            
            # Success message is added by the repl method itself through the console
            self.add_message(f"Pushed score {score} to scorecard {scorecard} successfully.", message_type="system")
            
        except Exception as e:
            self.add_message(f"Error pushing score: {str(e)}", message_type="system")
            logging.error(f"Error pushing score: {e}")
    
    async def handle_natural_language(self, user_input: str):
        """Handle natural language input."""
        # Check if we had an initialization error
        if hasattr(self, 'initialization_error') and self.initialization_error:
            self.add_message("Initialization error. Cannot process input.", message_type="system")
            return
        
        # Check if we have a properly initialized REPL and LLM with tools
        if not hasattr(self, 'repl') or not hasattr(self.repl, 'llm_with_tools'):
            self.add_message("REPL or LLM with tools not initialized. Cannot process input.", message_type="system")
            return
        
        try:
            # Append to REPL chat history
            self.repl.chat_history.append(HumanMessage(content=user_input))
            
            # Add a placeholder for the response
            self.add_message("Processing...", message_type="system")
            
            # Use the invoke method with to_thread, just like the working implementation
            ai_msg = await asyncio.to_thread(
                lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
            )
            
            # Add the model response to chat history
            self.repl.chat_history.append(ai_msg)
            
            # Clear the "Processing" message
            self.clear_messages_by_type_and_content("system", "Processing")
            
            # Extract content
            content = ai_msg.content if hasattr(ai_msg, 'content') else ""
            
            # Process tool calls
            tool_calls = []
            if hasattr(ai_msg, 'tool_calls'):
                tool_calls = ai_msg.tool_calls or []
            
            # Check if the response has tool calls
            if tool_calls:
                # Process each tool call
                for tool_call in tool_calls:
                    # Extract tool information
                    tool_name = tool_call.get('name', '')
                    tool_args = tool_call.get('args', {})
                    
                    # Add a tool message to the chat
                    self.add_message(f"Using tool: {tool_name}", message_type="system")
                    
                    # Process the command
                    command = tool_args.get('command', '')
                    tool_result_content = None
                    
                    try:
                        # Execute the tool call in a non-blocking way
                        if command == "view":
                            file_path = tool_args.get('path', '').lstrip('/')
                            try:
                                tool_result_content = await asyncio.to_thread(
                                    self.repl.file_editor.view, file_path
                                )
                            except FileNotFoundError:
                                tool_result_content = f"Error: File not found: {file_path}"
                                
                        elif command == "str_replace":
                            file_path = tool_args.get('path', '').lstrip('/')
                            old_str = tool_args.get('old_str', '')
                            new_str = tool_args.get('new_str', '')
                            
                            if not file_path or not old_str or 'new_str' not in tool_args:
                                tool_result_content = "Error: Missing required parameters"
                            else:
                                tool_result_content = await asyncio.to_thread(
                                    self.repl.file_editor.str_replace, file_path, old_str, new_str
                                )
                                
                        elif command == "undo_edit":
                            file_path = tool_args.get('path', '').lstrip('/')
                            tool_result_content = await asyncio.to_thread(
                                self.repl.file_editor.undo_edit, file_path
                            )
                            
                        elif command == "insert":
                            file_path = tool_args.get('path', '').lstrip('/')
                            insert_line = tool_args.get('insert_line', 0)
                            new_str = tool_args.get('new_str', '')
                            tool_result_content = await asyncio.to_thread(
                                self.repl.file_editor.insert, file_path, insert_line, new_str
                            )
                            
                        elif command == "create":
                            file_path = tool_args.get('path', '').lstrip('/')
                            content = tool_args.get('content', '')
                            tool_result_content = await asyncio.to_thread(
                                self.repl.file_editor.create, file_path, content
                            )
                        else:
                            logging.debug(f"Unknown tool command: {command}")
                            tool_result_content = f"Unknown command: {command}"
                    except Exception as tool_error:
                        logging.debug(f"Error executing tool: {tool_error}")
                        tool_result_content = f"Error executing tool: {str(tool_error)}"
                    
                    # Display tool result (short version in chat)
                    if tool_result_content:
                        # Create a shortened version for display
                        if len(tool_result_content) > 500:
                            display_content = f"{tool_result_content[:250]}...\n[output truncated]...{tool_result_content[-250:]}"
                        else:
                            display_content = tool_result_content
                            
                        self.add_message(f"Result from {tool_name}: {display_content}", message_type="tool")
                        
                        # Create a ToolMessage to send back to the model
                        tool_msg = ToolMessage(
                            content=tool_result_content,
                            tool_call_id=tool_call.get('id', ''),
                            name=tool_name
                        )
                        
                        # Add the tool message to chat history
                        self.repl.chat_history.append(tool_msg)
                
                # After processing all tool calls, get the final response
                self.add_message("Getting final response after tool usage...", message_type="system")
                final_response = await asyncio.to_thread(
                    lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
                )
                
                # Add the final response to chat history
                self.repl.chat_history.append(final_response)
                
                # Clear the "Getting final response" message
                self.clear_messages_by_type_and_content("system", "Getting final response")
                
                # Display the final response content
                if hasattr(final_response, 'content'):
                    content = final_response.content
                    if isinstance(content, str):
                        self.add_message(content, from_user=False, message_type="ai")
                    elif isinstance(content, list):
                        # Handle list content
                        content_text = ""
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                content_text += item["text"]
                            elif isinstance(item, str):
                                content_text += item
                        if content_text:
                            self.add_message(content_text, from_user=False, message_type="ai")
                        else:
                            self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                    else:
                        self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                else:
                    self.add_message("Response received but no content was found.", from_user=False, message_type="ai")
            else:
                # No tool calls, this is a final response
                logging.debug("No tool calls, treating as final response")
                
                # If there's content, display it
                if content:
                    if isinstance(content, str):
                        self.add_message(content, from_user=False, message_type="ai")
                    elif isinstance(content, list):
                        # Handle list content (which may be the case with tool calls)
                        content_text = ""
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                content_text += item["text"]
                            elif isinstance(item, str):
                                content_text += item
                        if content_text:
                            self.add_message(content_text, from_user=False, message_type="ai")
                        else:
                            self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
            
        except Exception as e:
            # Log the error and show a user-friendly message
            logging.error(f"Error in handle_natural_language: {str(e)}", exc_info=True)
            # Clear any processing message
            self.clear_messages_by_type_and_content("system", "Processing")
            self.add_message(f"Error processing your request: {str(e)}", from_user=False, message_type="system")

    def clear_messages_by_type_and_content(self, message_type, content_substring):
        """Clear messages of a specific type containing a specific substring."""
        # First, filter out the messages we want to remove
        messages_to_keep = []
        messages_to_remove = []
        
        for msg in self.messages:
            if msg["type"] == message_type and content_substring in msg["content"]:
                messages_to_remove.append(msg)
            else:
                messages_to_keep.append(msg)
        
        # Update our list
        self.messages = messages_to_keep
        
        # Remove widgets from UI
        for msg in messages_to_remove:
            if "widget" in msg and msg["widget"] is not None:
                try:
                    msg["widget"].remove()
                except Exception as e:
                    logging.error(f"Error removing widget: {e}")
    
    async def get_initial_response(self):
        """Get the initial response from the LLM."""
        # Check if we had an initialization error
        if hasattr(self, 'initialization_error') and self.initialization_error:
            self.add_message("Initialization error. Cannot get initial response.", message_type="system")
            return
        
        # Check if we have a properly initialized REPL and LLM
        if not hasattr(self, 'repl') or not hasattr(self.repl, 'llm'):
            self.add_message("REPL or LLM not initialized. Cannot get initial response.", message_type="system")
            return
        
        try:
            # First, ensure the system prompt is properly loaded with score information
            if not self.repl.chat_history or not any(isinstance(msg, SystemMessage) for msg in self.repl.chat_history):
                self.repl.initialize_system_message()
                
            # Check if we need to reload the file content
            if self.scorecard and self.score:
                # Get the score's file path - we'll need to make sure this is included in the system message
                yaml_path = get_score_yaml_path(self.scorecard, self.score)
                if yaml_path and yaml_path.exists():
                    # Make sure this file path is in the system message
                    for msg in self.repl.chat_history:
                        if isinstance(msg, SystemMessage) and f"file_path={str(yaml_path)}" not in msg.content:
                            # Re-initialize the system message with the correct file path
                            self.repl.initialize_system_message()
                            break
            
            self.add_message("Generating initial response...", message_type="system")
            
            # Add a human message to trigger the initial analysis - exactly like in the REPL
            self.repl.chat_history.append(HumanMessage(content="Please analyze this score configuration and tell me what you see."))
            
            # Use invoke method with tools - crucial distinction from before
            # We need to use llm_with_tools to enable file viewing as in original REPL
            response = await asyncio.to_thread(
                lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
            )
            
            # Add the response to chat history
            self.repl.chat_history.append(response)
            
            # Check for and handle any tool calls in the response
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                # Process each tool call
                for tool_call in tool_calls:
                    # Extract tool information
                    tool_name = tool_call.get('name', '')
                    tool_args = tool_call.get('args', {})
                    
                    # Add a tool message to the chat
                    self.add_message(f"Using tool: {tool_name}", message_type="system")
                    
                    # Process the command
                    command = tool_args.get('command', '')
                    tool_result_content = None
                    
                    try:
                        # Execute the tool call in a non-blocking way
                        if command == "view":
                            file_path = tool_args.get('path', '').lstrip('/')
                            try:
                                tool_result_content = await asyncio.to_thread(
                                    self.repl.file_editor.view, file_path
                                )
                            except FileNotFoundError:
                                tool_result_content = f"Error: File not found: {file_path}"
                                
                        # Handle other commands...
                        elif command == "str_replace":
                            file_path = tool_args.get('path', '').lstrip('/')
                            old_str = tool_args.get('old_str', '')
                            new_str = tool_args.get('new_str', '')
                            
                            if not file_path or not old_str or 'new_str' not in tool_args:
                                tool_result_content = "Error: Missing required parameters"
                            else:
                                tool_result_content = await asyncio.to_thread(
                                    self.repl.file_editor.str_replace, file_path, old_str, new_str
                                )
                        
                        # Add other tool commands as needed
                                
                    except Exception as tool_error:
                        logging.debug(f"Error executing tool: {tool_error}")
                        tool_result_content = f"Error executing tool: {str(tool_error)}"
                    
                    # Display tool result (short version in chat)
                    if tool_result_content:
                        # Create a shortened version for display
                        if len(tool_result_content) > 500:
                            display_content = f"{tool_result_content[:250]}...\n[output truncated]...{tool_result_content[-250:]}"
                        else:
                            display_content = tool_result_content
                            
                        self.add_message(f"Result from {tool_name}: {display_content}", message_type="tool")
                        
                        # Create a ToolMessage to send back to the model
                        tool_msg = ToolMessage(
                            content=tool_result_content,
                            tool_call_id=tool_call.get('id', ''),
                            name=tool_name
                        )
                        
                        # Add the tool message to chat history
                        self.repl.chat_history.append(tool_msg)
                
                # After processing all tool calls, get the final response
                final_response = await asyncio.to_thread(
                    lambda: self.repl.llm_with_tools.invoke(self.repl.chat_history)
                )
                
                # Add the final response to chat history
                self.repl.chat_history.append(final_response)
                
                # Clear the "Generating" message
                self.clear_messages_by_type_and_content("system", "Generating")
                
                # Display the final response content
                if hasattr(final_response, 'content'):
                    content = final_response.content
                    if isinstance(content, str):
                        self.add_message(content, from_user=False, message_type="ai")
                    elif isinstance(content, list):
                        # Handle list content
                        content_text = ""
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                content_text += item["text"]
                            elif isinstance(item, str):
                                content_text += item
                        if content_text:
                            self.add_message(content_text, from_user=False, message_type="ai")
                        else:
                            self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                    else:
                        self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                else:
                    self.add_message("Response received but no content was found.", from_user=False, message_type="ai")
            else:
                # No tool calls, just show the direct response
                self.clear_messages_by_type_and_content("system", "Generating")
                
                # Add the response content
                if hasattr(response, 'content'):
                    content = response.content
                    if isinstance(content, str):
                        self.add_message(content, from_user=False, message_type="ai")
                    elif isinstance(content, list):
                        # Handle list content (which may be the case with tool calls)
                        content_text = ""
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                content_text += item["text"]
                            elif isinstance(item, str):
                                content_text += item
                        if content_text:
                            self.add_message(content_text, from_user=False, message_type="ai")
                        else:
                            self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                    else:
                        self.add_message("Response received but content format was not recognized.", from_user=False, message_type="ai")
                else:
                    self.add_message("Response received but no content was found.", from_user=False, message_type="ai")
        except Exception as e:
            self.add_message(f"Error getting initial response: {str(e)}", from_user=False, message_type="system")
            logging.error(f"Error getting initial response: {e}", exc_info=True)
    
    def show_system_message(self):
        """Display the current system message for debugging."""
        if hasattr(self, 'repl') and hasattr(self.repl, 'chat_history') and self.repl.chat_history:
            for msg in self.repl.chat_history:
                if isinstance(msg, SystemMessage):
                    # Show just a short preview of the system message
                    content = msg.content
                    preview = content[:200] + "..." if len(content) > 200 else content
                    self.add_message(f"Current system message (preview): {preview}", message_type="system")
                    return
            self.add_message("No system message found in chat history.", message_type="system")
        else:
            self.add_message("REPL or chat history not initialized.", message_type="system")
            
    def update_response(self, new_text: str):
        """Update the streaming response in the UI."""
        # Simply ensure new_text is a string
        if not isinstance(new_text, str):
            new_text = "[Response content cannot be displayed]"
        
        # Format the AI response for better display
        if new_text.startswith("AI: "):
            new_text = new_text[4:]  # Remove the "AI: " prefix
            
        # Find the current AI response message or create a new one
        ai_messages = self.query_one("#chat-container").query(ChatMessage).filter(
            lambda msg: msg.message_type == "ai" and "Generating" not in msg.message_content
        )
        
        if ai_messages and ai_messages.last():
            # Update existing message
            last_ai_message = ai_messages.last()
            last_ai_message.update(f"{new_text}")
        else:
            # Create new message
            self.add_message(new_text, from_user=False, message_type="ai")
        
        # Scroll to the bottom
        chat_container = self.query_one("#chat-container")
        chat_container.scroll_end(animate=False)
    
    def add_message(self, content: str, from_user: bool = True, message_type: str = "human"):
        """Add a new message to the chat container."""
        # Format content if it's from user and contains newlines
        if from_user and message_type == "human":
            content = self.format_user_message(content)
            
        chat_container = self.query_one("#chat-container")
        message = ChatMessage(message_type, content)
        chat_container.mount(message)
        chat_container.scroll_end(animate=False)
        
        # Track message in our messages list
        self.messages.append({
            "type": message_type,
            "content": content,
            "from_user": from_user,
            "widget": message
        })
        
        # Make sure the input field stays focused
        self.query_one("#current-input").focus()

    def format_user_message(self, text: str) -> str:
        """Format user message text for display with proper handling of newlines."""
        # Handle multiline messages with better formatting
        if "\n" in text:
            # For multiline text, keep the formatting but ensure proper display
            lines = text.split("\n")
            formatted_lines = []
            for line in lines:
                if line.strip():  # Skip empty lines in display
                    formatted_lines.append(line)
                else:
                    formatted_lines.append(" ")  # Space placeholder for empty lines
            return "\n".join(formatted_lines)
        else:
            # For single line messages, just return as is
            return text

def run_textual_chat(scorecard: Optional[str] = None, score: Optional[str] = None):
    """Run the Textual-based chat interface."""
    # Configure basic logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Debug output for parameters
    print(f"Running with scorecard={scorecard} and score={score}")
    
    # Ensure API key is set (if not already)
    if "ANTHROPIC_API_KEY" not in os.environ:
        api_key = None
        # Try to get from environment file
        env_path = Path.home() / ".plexus" / "env"
        if env_path.exists():
            with open(env_path, "r") as f:
                for line in f:
                    if line.startswith("ANTHROPIC_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        
        # If still not found, prompt the user
        if not api_key:
            print("Anthropic API key is required to use Plexus Score Chat with Claude.")
            print("You can set it with the environment variable ANTHROPIC_API_KEY.")
            api_key = input("Enter your Anthropic API key (or press Enter to continue without it): ").strip()
        
        if api_key:
            os.environ["ANTHROPIC_API_KEY"] = api_key
    
    # Run the Textual app
    try:
        print("Starting Plexus Score Chat Textual UI...")
        app = ScoreChatApp(scorecard=scorecard, score=score)
        app.run()
    except Exception as e:
        print(f"Error running Textual UI: {e}")
        print(traceback.format_exc())
        print("\nFalling back to traditional REPL...")
        # Fall back to traditional REPL
        try:
            from plexus.cli.score_chat_repl import ScoreChatREPL
            repl = ScoreChatREPL(scorecard=scorecard, score=score)
            repl.run()
        except Exception as repl_error:
            print(f"Error falling back to traditional REPL: {repl_error}")
            print(traceback.format_exc())
            print("\nUnable to start any interface. Please check your environment setup.")

if __name__ == "__main__":
    import sys
    import argparse
    
    # Parse command line arguments more robustly
    parser = argparse.ArgumentParser(description="Plexus Score Chat Textual UI")
    parser.add_argument("--scorecard", help="Scorecard name or ID")
    parser.add_argument("--score", help="Score name or ID")
    parser.add_argument("--ui", action="store_true", help="Use the textual UI (default)")
    args = parser.parse_args()
    
    # Debug output for arguments
    print(f"Parsed arguments: {args}")
    
    run_textual_chat(scorecard=args.scorecard, score=args.score) 
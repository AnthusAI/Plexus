"""
Implementation of a reusable service for the Plexus score chat command.

This module provides core chat functionality for working with Plexus scores,
which can be used by different interfaces (CLI REPL, Celery worker, etc.).
"""

from typing import Optional, List, Dict, Any, Callable
import os
import json
from pathlib import Path
import logging
import time
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.callbacks import BaseCallbackHandler
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.file_editor import FileEditor
from plexus.cli.shared import get_score_yaml_path
from plexus.cli.identifier_resolution import resolve_scorecard_identifier, resolve_score_identifier
from plexus.cli.plexus_tool import PlexusTool


class ScoreChatService:
    """Core service for handling chat functionality for Plexus scores."""
    
    def __init__(self, 
                 scorecard: Optional[str] = None, 
                 score: Optional[str] = None,
                 callback_handler: Optional[BaseCallbackHandler] = None,
                 message_callback: Optional[Callable[[str], None]] = None):
        """Initialize the chat service.
        
        Args:
            scorecard: Optional scorecard identifier
            score: Optional score identifier
            callback_handler: Optional callback handler for LLM streaming
            message_callback: Optional callback for receiving message outputs
        """
        self.client = PlexusDashboardClient()
        self.file_editor = FileEditor()
        self.scorecard = scorecard
        self.score = score
        self.chat_history = []
        self.current_scorecard = None
        self.current_score = None
        self.message_callback = message_callback or (lambda x: None)
        
        # Initialize the PlexusTool for score management
        self.plexus_tool = PlexusTool()
        
        # Use provided callback handler or create a simple default one
        self.callback_handler = callback_handler
        
        # Create base LLM with streaming
        self.llm = ChatAnthropic(
            model_name="claude-3-7-sonnet-20250219",
            temperature=0.7,
            streaming=True,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
            callbacks=[self.callback_handler] if self.callback_handler else []
        )
        
        # Create LLM with tools that also has streaming enabled
        self.llm_with_tools = ChatAnthropic(
            model_name="claude-3-7-sonnet-20250219",
            temperature=0.7,
            streaming=True,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
            callbacks=[self.callback_handler] if self.callback_handler else []
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
            self.message_callback(f"Warning: Could not load documentation: {e}")
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
                self.message_callback(f"Scorecard not found: {self.scorecard}")
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
                self.message_callback(f"Error retrieving scorecard: {self.scorecard}")
                return
            scorecard_name = scorecard_data['name']
            
            # Resolve score ID and get its name
            score_id = resolve_score_identifier(self.client, scorecard_id, self.score)
            if not score_id:
                self.message_callback(f"Score not found: {self.score}")
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
                self.message_callback(f"Error retrieving score: {self.score}")
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
            
            # Add the system message to chat history
            self.chat_history = [SystemMessage(content=system_message)]
            
        except Exception as e:
            self.message_callback(f"Error initializing system message: {e}")
            # Fall back to a basic system message
            self.chat_history = [SystemMessage(content=self.system_message_template)]

    def initialize_session(self):
        """Initialize a chat session with a score."""
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
                    return response.content
                except Exception as e:
                    self.message_callback(f"Error getting initial response: {str(e)}")
                    return f"Error: Failed to analyze score configuration: {str(e)}"
            else:
                return "Please specify a scorecard and score to work with."
        except Exception as e:
            self.message_callback(f"Error initializing session: {str(e)}")
            return f"Error: {str(e)}"

    def process_message(self, user_input: str):
        """Process a natural language message from the user.
        
        Args:
            user_input: The user's message
            
        Returns:
            List of responses, which may include tool outputs
        """
        responses = []
        try:
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
                    
                    # Process AI message content
                    if ai_msg.content:
                        # Add the AI's text response to results
                        responses.append({"type": "ai_message", "content": ai_msg.content})
                    
                    # Check if the response has tool calls
                    if hasattr(ai_msg, 'tool_calls') and ai_msg.tool_calls:
                        for tool_call in ai_msg.tool_calls:
                            # Extract the tool input
                            tool_input = {}
                            
                            # First check the 'args' field (standard format)
                            if 'args' in tool_call:
                                tool_input = tool_call['args']
                            # Fallback to 'input' field
                            elif 'input' in tool_call:
                                tool_input = tool_call['input']
                            # Fallback to scanning all fields for expected command parameters
                            else:
                                for key, value in tool_call.items():
                                    if isinstance(value, dict) and any(param in value for param in ['command', 'path', 'old_str', 'new_str']):
                                        tool_input = value
                                        break
                            
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
                                content = tool_input.get('content', '')
                                tool_result_content = self.file_editor.create(file_path, content)
                            
                            # Add tool result to responses
                            if tool_result_content is not None:
                                responses.append({
                                    "type": "tool_result",
                                    "tool": tool_call.get('name', ''),
                                    "command": command,
                                    "result": tool_result_content
                                })
                                
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
                    error_msg = f"Error during model interaction: {str(e)}"
                    self.message_callback(error_msg)
                    responses.append({"type": "error", "content": error_msg})
                    # Try recovery if there's an issue
                    recovery_response = self.recover_and_continue()
                    if recovery_response:
                        responses.append({"type": "recovery", "content": recovery_response})
                    finished = True
            
        except Exception as e:
            error_msg = f"Error processing user input: {str(e)}"
            self.message_callback(error_msg)
            responses.append({"type": "error", "content": error_msg})
        
        return responses

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
            
            # Add the last human message
            last_human_msg = None
            for i in range(len(self.chat_history) - 1, -1, -1):
                if isinstance(self.chat_history[i], HumanMessage):
                    last_human_msg = self.chat_history[i]
                    break
            
            if last_human_msg:
                # Add the human message
                simplified_history.append(last_human_msg)
                
                # Try again with the simplified history
                # Create a new instance of the LLM to avoid any lingering state issues
                recovery_llm = ChatAnthropic(
                    model_name="claude-3-7-sonnet-20250219",
                    temperature=0.7,
                    streaming=True,
                    anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
                    max_tokens_to_sample=64000,  # Maximum allowed for Claude 3.7 Sonnet
                    callbacks=[self.callback_handler] if self.callback_handler else []
                )
                
                # Get a new response with the simplified history
                response = recovery_llm.invoke(simplified_history)
                
                # Add the response to the chat history
                self.chat_history.append(response)
                
                return response.content
        
        except Exception as e:
            self.message_callback(f"Error during recovery: {str(e)}")
            return f"Failed to recover from error: {str(e)}"
        
        return None

    def pull_score(self, scorecard: str, score: str):
        """Pull a score's current version."""
        # Resolve identifiers
        scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
        if not scorecard_id:
            self.message_callback(f"Scorecard not found: {scorecard}")
            return f"Error: Scorecard not found: {scorecard}"
        
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
            self.message_callback(f"Error retrieving scorecard: {scorecard}")
            return f"Error: Could not retrieve scorecard: {scorecard}"
        scorecard_name = scorecard_data['name']
        
        score_id = resolve_score_identifier(self.client, scorecard_id, score)
        if not score_id:
            self.message_callback(f"Score not found: {score}")
            return f"Error: Score not found: {score}"
        
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
                self.message_callback(f"Error retrieving score: {score}")
                return f"Error: Could not retrieve score: {score}"
            
            champion_version_id = score_data.get('championVersionId')
            if not champion_version_id:
                self.message_callback(f"No champion version found for score: {score}")
                return f"Error: No champion version found for score: {score}"
            
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
                self.message_callback(f"No configuration found for version: {champion_version_id}")
                return f"Error: No configuration found for version: {champion_version_id}"
            
            # Get the YAML file path using the scorecard name
            yaml_path = get_score_yaml_path(scorecard_name, score_data['name'])
            
            # Write to file
            with open(yaml_path, 'w') as f:
                f.write(version_data['configuration'])
            
            success_msg = f"Saved score configuration to: {yaml_path}"
            self.message_callback(success_msg)
            return success_msg
            
        except Exception as e:
            error_msg = f"Error pulling score: {str(e)}"
            self.message_callback(error_msg)
            return error_msg

    def push_score(self, scorecard: str, score: str):
        """Push a score's updated version."""
        # Resolve identifiers
        scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
        if not scorecard_id:
            self.message_callback(f"Scorecard not found: {scorecard}")
            return f"Error: Scorecard not found: {scorecard}"
        
        score_id = resolve_score_identifier(self.client, scorecard_id, score)
        if not score_id:
            self.message_callback(f"Score not found: {score}")
            return f"Error: Score not found: {score}"
        
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
                self.message_callback(f"Error retrieving score: {score}")
                return f"Error: Could not retrieve score: {score}"
            
            # Get the YAML file path
            yaml_path = get_score_yaml_path(scorecard, score_data['name'])
            
            if not yaml_path.exists():
                self.message_callback(f"YAML file not found at: {yaml_path}")
                return f"Error: YAML file not found at: {yaml_path}"
            
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
                    'note': 'Updated via API chat command',
                    'isFeatured': True
                }
            })
            
            if result.get('createScoreVersion'):
                success_msg = (
                    f"Successfully created new version for score: {score_data['name']}\n"
                    f"New version ID: {result['createScoreVersion']['id']}"
                )
                self.message_callback(success_msg)
                return success_msg
            else:
                error_msg = "Error creating new version"
                self.message_callback(error_msg)
                return error_msg
            
        except Exception as e:
            error_msg = f"Error pushing score: {str(e)}"
            self.message_callback(error_msg)
            return error_msg

    def load_score(self, scorecard: str, score: str):
        """Load a score's configuration."""
        try:
            # First pull the score
            pull_result = self.pull_score(scorecard, score)
            if pull_result.startswith("Error:"):
                return pull_result
            
            # Get scorecard details to get its name
            scorecard_id = resolve_scorecard_identifier(self.client, scorecard)
            if not scorecard_id:
                self.message_callback(f"Scorecard not found: {scorecard}")
                return f"Error: Scorecard not found: {scorecard}"
            
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
                self.message_callback(f"Error retrieving scorecard: {scorecard}")
                return f"Error: Could not retrieve scorecard: {scorecard}"
            scorecard_name = scorecard_data['name']
            
            # Get score details to get its name
            score_id = resolve_score_identifier(self.client, scorecard_id, score)
            if not score_id:
                self.message_callback(f"Score not found: {score}")
                return f"Error: Score not found: {score}"
            
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
                self.message_callback(f"Error retrieving score: {score}")
                return f"Error: Could not retrieve score: {score}"
            
            # Get the YAML file path using the correct names
            yaml_path = get_score_yaml_path(scorecard_name, score_data['name'])
            
            if not yaml_path.exists():
                self.message_callback(f"YAML file not found at: {yaml_path}")
                return f"Error: YAML file not found at: {yaml_path}"
            
            self.current_scorecard = scorecard
            self.current_score = score
            
            return f"Successfully loaded score: {score_data['name']} from scorecard: {scorecard_name}"
            
        except Exception as e:
            error_msg = f"Error loading score: {str(e)}"
            self.message_callback(error_msg)
            return error_msg 
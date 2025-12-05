"""
Chat Recording for Procedure Runs.

This module provides functionality to record AI conversations during procedure runs,
including tool calls and responses, for later analysis and display in the UI.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger(__name__)


def truncate_for_log(content: str, max_length: int = 200) -> str:
    """Truncate content for logging purposes."""
    if not content:
        return content
    if len(content) <= max_length:
        return content
    return content[:max_length] + f"... [truncated, total: {len(content)} chars]"


class ProcedureChatRecorder:
    """Records chat messages during procedure runs."""

    def __init__(self, client: PlexusDashboardClient, procedure_id: str, node_id: Optional[str] = None):
        self.client = client
        self.procedure_id = procedure_id
        self.node_id = node_id
        self.session_id = None
        self.account_id = None
        self.sequence_number = 0
        self._sequence_lock = None  # Will be initialized when needed
        self._state_data: Optional[Dict[str, Any]] = None  # Conversation state machine data
        
    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Start a new chat session for the procedure run."""
        try:
            # Create ChatSession record
            # Resolve account ID from environment (uses PLEXUS_ACCOUNT_KEY internally)
            account_id = self.client._resolve_account_id()
            if not account_id:
                raise ValueError("Could not resolve account ID. Is PLEXUS_ACCOUNT_KEY set?")

            # Get the actual IDs that are being passed
            scorecard_id = context.get('scorecard_id') if context else None
            score_id = context.get('score_id') if context else None
            
            session_data = {
                'accountId': account_id,
                'procedureId': self.procedure_id,
                'category': 'Hypothesize',
                'status': 'ACTIVE'
            }
            
            # Only include nodeId if it's not None (for experiment-level conversations)
            if self.node_id is not None:
                session_data['nodeId'] = self.node_id

            # Add scorecard/score IDs if they are present
            if scorecard_id and str(scorecard_id).strip():
                session_data['scorecardId'] = scorecard_id
                
            if score_id and str(score_id).strip():
                session_data['scoreId'] = score_id
            
            # Execute GraphQL mutation to create session
            mutation = """
            mutation CreateChatSession($input: CreateChatSessionInput!) {
                createChatSession(input: $input) {
                    id
                    status
                    createdAt
                }
            }
            """
            
            result = self.client.execute(mutation, {'input': session_data})
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating session: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_session_result = None
            if result and 'data' in result and 'createChatSession' in result['data']:
                chat_session_result = result['data']['createChatSession']
            elif result and 'createChatSession' in result:
                chat_session_result = result['createChatSession']
            
            if chat_session_result and 'id' in chat_session_result:
                self.session_id = chat_session_result['id']
                self.account_id = account_id  # Store account_id for use in message recording
                logger.info(f"Chat session created: {self.session_id} for account: {account_id}")
                return self.session_id
            else:
                logger.error(f"Failed to create session - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error starting session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    async def record_message(
        self,
        role: str,
        content: str,
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        tool_response: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[str] = None,
        human_interaction: Optional[str] = None
    ) -> str:
        """Record a chat message."""
        if not self.session_id:
            logger.warning("No active session - cannot record message")
            return None

        try:
            self.sequence_number += 1

            # Truncate content if it exceeds DynamoDB limits (400KB total item size)
            # Allow approximately 300KB for content to leave room for other fields
            MAX_CONTENT_SIZE = 300 * 1024  # 300KB in bytes
            original_content = content

            if len(content.encode('utf-8')) > MAX_CONTENT_SIZE:
                # Truncate content while preserving UTF-8 encoding
                truncated_bytes = content.encode('utf-8')[:MAX_CONTENT_SIZE]
                # Decode and handle potential broken UTF-8 at the end
                try:
                    content = truncated_bytes.decode('utf-8')
                except UnicodeDecodeError:
                    # Try truncating a bit more to avoid broken UTF-8
                    content = truncated_bytes[:-10].decode('utf-8', errors='ignore')

                # Add truncation indicator
                content += "\n\n... [Content truncated due to size limits]"
                logger.warning(f"Truncated message content from {len(original_content)} to {len(content)} characters")

            # Set intelligent default for humanInteraction if not provided
            if human_interaction is None:
                if role == 'USER':
                    human_interaction = 'CHAT'
                elif role == 'ASSISTANT':
                    human_interaction = 'CHAT_ASSISTANT'
                elif message_type == 'TOOL_CALL' or message_type == 'TOOL_RESPONSE':
                    human_interaction = 'INTERNAL'
                else:
                    # SYSTEM and other messages default to INTERNAL
                    human_interaction = 'INTERNAL'

            message_data = {
                'sessionId': self.session_id,
                'procedureId': self.procedure_id,
                'role': role,
                'content': content,
                'messageType': message_type,
                'sequenceNumber': self.sequence_number,
                'humanInteraction': human_interaction
                # Note: Omitting metadata field due to GraphQL validation issues
            }

            # Add accountId if available
            if self.account_id:
                message_data['accountId'] = self.account_id
            
            # Add tool-specific fields if provided
            if tool_name:
                message_data['toolName'] = tool_name
            if tool_parameters:
                import json
                message_data['toolParameters'] = json.dumps(tool_parameters)
            if tool_response:
                import json
                message_data['toolResponse'] = json.dumps(tool_response)
            if parent_message_id:
                message_data['parentMessageId'] = parent_message_id
            
            # Log message recording (reduced noise - just sequence and type)
            tool_info = f" | Tool: {tool_name}" if tool_name else ""
            logger.debug(f"📝 Recording message [{self.sequence_number}] {role}/{message_type}{tool_info}")

            # NOTE: We record the FULL content in the database, only the log is truncated

            # Execute GraphQL mutation to create message
            mutation = """
            mutation CreateChatMessage($input: CreateChatMessageInput!) {
                createChatMessage(input: $input) {
                    id
                    sequenceNumber
                    createdAt
                }
            }
            """

            result = self.client.execute(mutation, {'input': message_data})
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating message: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_message_result = None
            if result and 'data' in result and 'createChatMessage' in result['data']:
                chat_message_result = result['data']['createChatMessage']
            elif result and 'createChatMessage' in result:
                chat_message_result = result['createChatMessage']
            
            if chat_message_result and 'id' in chat_message_result:
                message_id = chat_message_result['id']
                logger.info(f"✅ Created message {message_id} (seq {self.sequence_number})")
                return message_id
            else:
                logger.error(f"Failed to create message - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    def _get_next_sequence_number(self) -> int:
        """Thread-safe sequence number generation."""
        import threading
        
        # Initialize lock if not already done
        if self._sequence_lock is None:
            self._sequence_lock = threading.Lock()
        
        with self._sequence_lock:
            self.sequence_number += 1
            return self.sequence_number
    
    def record_message_sync(
        self, 
        role: str, 
        content: str, 
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        parent_message_id: Optional[str] = None
    ) -> str:
        """Synchronous wrapper for recording messages from callbacks."""
        import asyncio
        import threading
        
        message_id = None
        error = None
        
        def run_async():
            nonlocal message_id, error
            try:
                # Create new event loop for this thread
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                # Override sequence number generation in async call for thread safety
                original_seq = self.sequence_number
                self.sequence_number = original_seq  # Don't increment here
                
                message_id = loop.run_until_complete(
                    self.record_message_with_sequence(
                        role, content, message_type, tool_name, None, None, parent_message_id,
                        sequence_number=self._get_next_sequence_number()
                    )
                )
                loop.close()
            except Exception as e:
                error = e
        
        thread = threading.Thread(target=run_async)
        thread.start()
        thread.join(timeout=30)  # 30 second timeout
        
        if error:
            logger.error(f"Error in sync message recording: {error}")
            return None
            
        return message_id
    
    async def record_message_with_sequence(
        self,
        role: str,
        content: str,
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        tool_response: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[str] = None,
        sequence_number: Optional[int] = None,
        human_interaction: Optional[str] = None
    ) -> str:
        """Record a chat message with explicit sequence number."""
        if not self.session_id:
            logger.warning("No active session - cannot record message")
            return None

        try:
            # Use provided sequence number or generate new one
            if sequence_number is None:
                sequence_number = self._get_next_sequence_number()

            # Set intelligent default for humanInteraction if not provided
            if human_interaction is None:
                if role == 'USER':
                    human_interaction = 'CHAT'
                elif role == 'ASSISTANT':
                    human_interaction = 'CHAT_ASSISTANT'
                elif message_type == 'TOOL_CALL' or message_type == 'TOOL_RESPONSE':
                    human_interaction = 'INTERNAL'
                else:
                    # SYSTEM and other messages default to INTERNAL
                    human_interaction = 'INTERNAL'

            message_data = {
                'sessionId': self.session_id,
                'procedureId': self.procedure_id,
                'role': role,
                'content': content,
                'messageType': message_type,
                'sequenceNumber': sequence_number,
                'humanInteraction': human_interaction
                # Note: Omitting metadata field due to GraphQL validation issues
            }

            # Add accountId if available
            if self.account_id:
                message_data['accountId'] = self.account_id

            # Add tool-specific fields if provided
            if tool_name:
                message_data['toolName'] = tool_name
            # Note: Omitting tool parameters and response for now due to GraphQL validation
            # These can be stored in the content field as formatted text instead
            if parent_message_id:
                message_data['parentMessageId'] = parent_message_id
            
            # Log message recording (reduced noise)
            tool_info = f" | Tool: {tool_name}" if tool_name else ""
            logger.debug(f"📝 Recording message [{sequence_number}] {role}/{message_type}{tool_info}")
                
            # Execute GraphQL mutation to create message
            mutation = """
            mutation CreateChatMessage($input: CreateChatMessageInput!) {
                createChatMessage(input: $input) {
                    id
                    sequenceNumber
                    createdAt
                }
            }
            """
            
            result = self.client.execute(mutation, {'input': message_data})
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL error creating message: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_message_result = None
            if result and 'data' in result and 'createChatMessage' in result['data']:
                chat_message_result = result['data']['createChatMessage']
            elif result and 'createChatMessage' in result:
                chat_message_result = result['createChatMessage']
            
            if chat_message_result and 'id' in chat_message_result:
                message_id = chat_message_result['id']
                logger.info(f"✅ Created message {message_id} (seq {sequence_number})")
                return message_id
            else:
                logger.error(f"Failed to create message - unexpected result: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording message: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None
    
    async def record_system_message(self, content: str) -> str:
        """Record a system message (like initial prompts)."""
        return await self.record_message('SYSTEM', content)
    
    async def record_user_message(self, content: str) -> str:
        """Record a user message."""
        return await self.record_message('USER', content)
    
    async def record_assistant_message(self, content: str) -> str:
        """Record an assistant message."""
        return await self.record_message('ASSISTANT', content)
    
    async def record_tool_call(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any], 
        description: Optional[str] = None
    ) -> str:
        """Record a tool call message."""
        # Include parameters in the content since GraphQL validation is strict
        param_str = json.dumps(parameters, indent=2) if parameters else "{}"
        content = f"{description or f'Calling tool: {tool_name}'}\n\nParameters:\n{param_str}"
        return await self.record_message(
            role='ASSISTANT',
            content=content,
            message_type='TOOL_CALL',
            tool_name=tool_name
        )
    
    async def record_tool_response(
        self, 
        tool_name: str, 
        response: Any, 
        parent_message_id: str,
        description: Optional[str] = None
    ) -> str:
        """Record a tool response message."""
        # Include response in the content since GraphQL validation is strict
        response_str = json.dumps(response, indent=2) if isinstance(response, dict) else str(response)
        content = f"{description or f'Response from tool: {tool_name}'}\n\nResponse:\n{response_str}"
        return await self.record_message(
            role='TOOL',
            content=content,
            message_type='TOOL_RESPONSE',
            tool_name=tool_name,
            parent_message_id=parent_message_id
        )
    
    async def update_session_name(self, name: str) -> bool:
        """Update the name of the current chat session."""
        if not self.session_id:
            logger.warning("No active session to update")
            return False
            
        try:
            mutation = """
            mutation UpdateChatSession($input: UpdateChatSessionInput!) {
                updateChatSession(input: $input) {
                    id
                    name
                    updatedAt
                }
            }
            """
            
            session_data = {
                'id': self.session_id,
                'name': name
            }
            
            result = self.client.execute(mutation, {'input': session_data})
            
            if 'errors' in result:
                logger.error(f"GraphQL error updating session name: {result['errors']}")
                return False
                
            logger.info(f"📝 Session {self.session_id} name updated to: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating session name: {e}")
            return False

    async def end_session(self, status: str = 'COMPLETED', name: Optional[str] = None) -> bool:
        """End the chat session with optional name update."""
        if not self.session_id:
            logger.debug("No active session to end")
            return True
            
        try:
            name_info = f" with name '{name}'" if name else ""
            logger.info(f"Ending session {self.session_id} with status {status}{name_info}")
            
            # Update session status and optionally name
            mutation = """
            mutation UpdateChatSession($input: UpdateChatSessionInput!) {
                updateChatSession(input: $input) {
                    id
                    status
                    name
                    updatedAt
                }
            }
            """
            
            update_data = {
                'id': self.session_id,
                'status': status
                # Note: Omitting metadata field due to GraphQL validation issues
            }
            
            if name:
                update_data['name'] = name
            
            result = self.client.execute(mutation, {'input': update_data})
            if result and 'updateChatSession' in result:
                logger.info(f"Session ended: {self.session_id}")
                return True
            else:
                logger.error(f"Failed to end session: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error ending session: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return False


class LangChainChatRecorderHook:
    """Hook into LangChain agent execution to record tool calls and responses."""
    
    def __init__(self, recorder: ProcedureChatRecorder):
        self.recorder = recorder
        self.tool_call_messages = {}  # Map tool calls to their message IDs
    
    async def record_agent_step(self, step_info: Dict[str, Any]):
        """Record a step in the agent execution."""
        try:
            action = step_info.get('action')
            if not action:
                return
                
            # Record tool call
            tool_name = action.get('tool')
            tool_input = action.get('tool_input', {})
            
            if tool_name:
                # Record the tool call
                tool_call_id = await self.recorder.record_tool_call(
                    tool_name=tool_name,
                    parameters=tool_input,
                    description=f"Agent is calling tool: {tool_name}"
                )
                
                # Store for linking response
                self.tool_call_messages[tool_name] = tool_call_id
                
                # Record tool response if available
                observation = step_info.get('observation')
                if observation and tool_call_id:
                    await self.recorder.record_tool_response(
                        tool_name=tool_name,
                        response=observation,
                        parent_message_id=tool_call_id,
                        description=f"Tool {tool_name} responded"
                    )
                    
        except Exception as e:
            logger.error(f"Error recording agent step: {e}")
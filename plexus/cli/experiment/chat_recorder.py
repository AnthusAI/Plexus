"""
Chat Recording for Experiment Runs.

This module provides functionality to record AI conversations during experiment runs,
including tool calls and responses, for later analysis and display in the UI.
"""

import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from plexus.dashboard.api.client import PlexusDashboardClient

logger = logging.getLogger(__name__)


class ExperimentChatRecorder:
    """Records chat messages during experiment runs."""
    
    def __init__(self, client: PlexusDashboardClient, experiment_id: str, node_id: Optional[str] = None):
        self.client = client
        self.experiment_id = experiment_id
        self.node_id = node_id
        self.session_id = None
        self.sequence_number = 0
        
    async def start_session(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Start a new chat session for the experiment run."""
        try:
            # Create ChatSession record  
            # Use default account if not provided in context
            import os
            default_account = os.environ.get('PLEXUS_ACCOUNT_KEY', 'call-criteria')
            
            session_data = {
                'accountId': context.get('account_id') if context and context.get('account_id') else default_account,
                'scorecardId': context.get('scorecard_id') if context else None,
                'scoreId': context.get('score_id') if context else None,
                'experimentId': self.experiment_id,
                'nodeId': self.node_id,
                'status': 'ACTIVE'
                # Note: Omitting metadata field due to GraphQL validation issues
                # Metadata can be added later if needed via update mutation
            }
            
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
            
            logger.info(f"Creating chat session with data: {session_data}")
            result = self.client.execute(mutation, {'input': session_data})
            
            # Check for GraphQL errors first
            if 'errors' in result:
                logger.error(f"GraphQL errors creating chat session: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_session_result = None
            if result and 'data' in result and 'createChatSession' in result['data']:
                chat_session_result = result['data']['createChatSession']
            elif result and 'createChatSession' in result:
                chat_session_result = result['createChatSession']
            
            if chat_session_result and 'id' in chat_session_result:
                self.session_id = chat_session_result['id']
                logger.info(f"Started chat session {self.session_id} for experiment {self.experiment_id}")
                return self.session_id
            else:
                logger.error(f"Failed to create chat session - unexpected result structure: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error starting chat session: {e}")
            return None
    
    async def record_message(
        self, 
        role: str, 
        content: str, 
        message_type: str = 'MESSAGE',
        tool_name: Optional[str] = None,
        tool_parameters: Optional[Dict[str, Any]] = None,
        tool_response: Optional[Dict[str, Any]] = None,
        parent_message_id: Optional[str] = None
    ) -> str:
        """Record a chat message."""
        if not self.session_id:
            logger.warning("No active chat session for recording message")
            return None
            
        try:
            self.sequence_number += 1
            
            message_data = {
                'sessionId': self.session_id,
                'experimentId': self.experiment_id,
                'role': role,
                'content': content,
                'messageType': message_type,
                'sequenceNumber': self.sequence_number
                # Note: Omitting metadata field due to GraphQL validation issues
            }
            
            # Add tool-specific fields if provided
            if tool_name:
                message_data['toolName'] = tool_name
            # Note: Omitting tool parameters and response for now due to GraphQL validation
            # These can be stored in the content field as formatted text instead
            if parent_message_id:
                message_data['parentMessageId'] = parent_message_id
                
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
                logger.error(f"GraphQL errors creating chat message: {result['errors']}")
                return None
                
            # Handle both wrapped and unwrapped GraphQL responses
            chat_message_result = None
            if result and 'data' in result and 'createChatMessage' in result['data']:
                chat_message_result = result['data']['createChatMessage']
            elif result and 'createChatMessage' in result:
                chat_message_result = result['createChatMessage']
            
            if chat_message_result and 'id' in chat_message_result:
                message_id = chat_message_result['id']
                logger.debug(f"Recorded message {message_id} in session {self.session_id}")
                return message_id
            else:
                logger.error(f"Failed to create chat message - unexpected result structure: {result}")
                return None
                
        except Exception as e:
            logger.error(f"Error recording chat message: {e}")
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
    
    async def end_session(self, status: str = 'COMPLETED') -> bool:
        """End the chat session."""
        if not self.session_id:
            return True
            
        try:
            # Update session status
            mutation = """
            mutation UpdateChatSession($input: UpdateChatSessionInput!) {
                updateChatSession(input: $input) {
                    id
                    status
                    updatedAt
                }
            }
            """
            
            update_data = {
                'id': self.session_id,
                'status': status
                # Note: Omitting metadata field due to GraphQL validation issues
            }
            
            result = self.client.execute(mutation, {'input': update_data})
            if result and 'updateChatSession' in result:
                logger.info(f"Ended chat session {self.session_id} with status {status}")
                return True
            else:
                logger.error(f"Failed to update chat session: {result}")
                return False
                
        except Exception as e:
            logger.error(f"Error ending chat session: {e}")
            return False


class LangChainChatRecorderHook:
    """Hook into LangChain agent execution to record tool calls and responses."""
    
    def __init__(self, recorder: ExperimentChatRecorder):
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
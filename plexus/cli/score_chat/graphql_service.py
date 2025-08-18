"""
GraphQL-based implementation of the Plexus score chat service.

This module provides chat functionality that works with the GraphQL API
instead of Celery, while preserving all file-editing capabilities.
"""

import json
import uuid
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from plexus.cli.score_chat.service import ScoreChatService
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.cli.shared.file_editor import FileEditor


class GraphQLChatService(ScoreChatService):
    """Chat service that uses GraphQL API for persistence and messaging."""
    
    def __init__(self, 
                 session_id: Optional[str] = None,
                 scorecard: Optional[str] = None, 
                 score: Optional[str] = None,
                 experiment_id: Optional[str] = None,
                 message_callback: Optional[Callable[[str], None]] = None):
        """Initialize the GraphQL chat service.
        
        Args:
            session_id: Existing chat session ID, or None to create new
            scorecard: Optional scorecard identifier for new sessions
            score: Optional score identifier for new sessions
            experiment_id: Optional experiment ID to associate session with
            message_callback: Optional callback for receiving message outputs
        """
        super().__init__(scorecard, score, message_callback=message_callback)
        self.session_id = session_id
        self.experiment_id = experiment_id
        
    async def create_session(self, account_id: str) -> str:
        """Create a new chat session in the database.
        
        Args:
            account_id: Account ID for the session
            
        Returns:
            Session ID of the created session
        """
        session_data = {
            'accountId': account_id,
            'status': 'ACTIVE'
        }
        
        if self.scorecard:
            # Resolve scorecard ID if needed
            scorecard_info = await self._resolve_scorecard()
            if scorecard_info:
                session_data['scorecardId'] = scorecard_info['id']
        
        if self.score:
            # Resolve score ID if needed  
            score_info = await self._resolve_score()
            if score_info:
                session_data['scoreId'] = score_info['id']
        
        if self.experiment_id:
            session_data['experimentId'] = self.experiment_id
        
        # Use GraphQL mutation to create session
        result = await self.client.create_chat_session(session_data)
        self.session_id = result['id']
        return self.session_id
    
    async def send_message(self, message: str, role: str = 'USER') -> Dict[str, Any]:
        """Send a message and save it to the database.
        
        Args:
            message: Message content
            role: Message role (USER, ASSISTANT, SYSTEM)
            
        Returns:
            Created message data
        """
        if not self.session_id:
            raise ValueError("No active chat session. Create session first.")
        
        message_data = {
            'sessionId': self.session_id,
            'role': role,
            'content': message
        }
        
        # Add experiment ID for efficient GSI queries
        if self.experiment_id:
            message_data['experimentId'] = self.experiment_id
        
        
        # Use GraphQL mutation to create message
        result = await self.client.create_chat_message(message_data)
        return result
    
    async def process_message_with_graphql(self, message: str) -> Dict[str, Any]:
        """Process a user message and return AI response via GraphQL.
        
        Args:
            message: User message to process
            
        Returns:
            Dictionary with response content and metadata
        """
        # Save user message to database
        await self.send_message(message, 'USER')
        
        # Process message using existing ScoreChatService logic
        # This handles all the file editing via FileEditor
        responses = self.process_message(message)
        
        # Extract AI responses and save to database
        ai_responses = []
        for response in responses:
            if response.get('type') == 'ai_message':
                ai_message = await self.send_message(response['content'], 'ASSISTANT')
                ai_responses.append(ai_message)
        
        return {
            'session_id': self.session_id,
            'responses': ai_responses,
            'chat_history': self.chat_history
        }
    
    async def end_session(self) -> Dict[str, Any]:
        """End the chat session and update its status.
        
        Returns:
            Updated session data
        """
        if not self.session_id:
            return {'error': 'No active session to end'}
        
        # Update session status to COMPLETED
        update_data = {
            'id': self.session_id,
            'status': 'COMPLETED'
        }
        
        result = await self.client.update_chat_session(update_data)
        return result
    
    
    async def _resolve_scorecard(self) -> Optional[Dict[str, Any]]:
        """Resolve scorecard identifier to full scorecard info."""
        try:
            from plexus.cli.shared.identifier_resolution import resolve_scorecard_identifier
            return resolve_scorecard_identifier(self.scorecard, self.client)
        except Exception as e:
            self.message_callback(f"Error resolving scorecard: {e}")
            return None
    
    async def _resolve_score(self) -> Optional[Dict[str, Any]]:
        """Resolve score identifier to full score info."""
        try:
            from plexus.cli.shared.identifier_resolution import resolve_score_identifier
            return resolve_score_identifier(self.score, self.current_scorecard, self.client)
        except Exception as e:
            self.message_callback(f"Error resolving score: {e}")
            return None


# Convenience functions for CLI and MCP usage
async def create_chat_session(account_id: str, scorecard: str = None, score: str = None, experiment_id: str = None) -> GraphQLChatService:
    """Create a new chat session.
    
    Args:
        account_id: Account ID for the session
        scorecard: Optional scorecard identifier
        score: Optional score identifier
        experiment_id: Optional experiment ID to associate with
        
    Returns:
        Initialized GraphQLChatService instance
    """
    service = GraphQLChatService(scorecard=scorecard, score=score, experiment_id=experiment_id)
    await service.create_session(account_id)
    return service


async def resume_chat_session(session_id: str) -> GraphQLChatService:
    """Resume an existing chat session.
    
    Args:
        session_id: ID of the session to resume
        
    Returns:
        GraphQLChatService instance connected to the session
    """
    service = GraphQLChatService(session_id=session_id)
    
    # Load session data and chat history from database
    session_data = await service.client.get_chat_session(session_id)
    if session_data:
        service.scorecard = session_data.get('scorecardId')
        service.score = session_data.get('scoreId')
        service.experiment_id = session_data.get('experimentId')
        
        # Load chat history
        messages = await service.client.list_chat_messages(session_id)
        service.chat_history = messages
    
    return service
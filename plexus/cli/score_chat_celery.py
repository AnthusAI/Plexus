"""
Implementation of a Celery-based handler for the Plexus score chat command.

This module provides a Celery task that can process chat messages for the
Plexus score chat feature, using the same core functionality as the CLI REPL.
"""

from typing import Dict, Any, Optional
import os
import json
import time
import uuid
from celery import shared_task, Task
from plexus.cli.score_chat_service import ScoreChatService
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.task import Task as PlexusTask
import logging

# Dictionary to store active chat sessions, indexed by chat ID
active_chat_sessions = {}

@shared_task(bind=True, name="plexus.score_chat.message")
def process_chat_message(self: Task, chat_id: str, message: str, scorecard: Optional[str] = None, 
                        score: Optional[str] = None, task_id: Optional[str] = None) -> Dict[str, Any]:
    """Process a chat message for the Plexus score chat feature.
    
    This task can either continue an existing chat session (identified by chat_id)
    or start a new one with the specified scorecard and score.
    
    Args:
        chat_id: Unique identifier for this chat session
        message: The user's message to process
        scorecard: Optional scorecard identifier to initialize a new session
        score: Optional score identifier to initialize a new session
        task_id: Optional task ID for tracking in the dashboard
        
    Returns:
        Dictionary containing the chat results
    """
    try:
        # Set up logging to capture messages
        message_logs = []
        
        def log_message(msg: str):
            """Callback to log messages from the chat service."""
            message_logs.append(msg)
            logging.info(f"Score Chat [{chat_id}]: {msg}")
        
        # Create or retrieve the chat service for this session
        chat_service = active_chat_sessions.get(chat_id)
        
        if chat_service is None:
            # This is a new chat session
            if not scorecard or not score:
                return {
                    "error": "New chat sessions require both scorecard and score parameters",
                    "chat_id": chat_id
                }
            
            # Create a new chat service
            chat_service = ScoreChatService(
                scorecard=scorecard,
                score=score,
                message_callback=log_message
            )
            
            # Store in the active sessions
            active_chat_sessions[chat_id] = chat_service
            
            # Initialize the session and get the welcome message
            welcome_message = chat_service.initialize_session()
            
            return {
                "chat_id": chat_id,
                "message": message,
                "responses": [
                    {"type": "ai_message", "content": welcome_message}
                ],
                "logs": message_logs
            }
        
        # Process the message using the existing chat service
        responses = chat_service.process_message(message)
        
        # Update task status in the dashboard if a task ID was provided
        if task_id:
            try:
                api_url = os.environ.get('PLEXUS_API_URL')
                api_key = os.environ.get('PLEXUS_API_KEY')
                
                if api_url and api_key:
                    client = PlexusDashboardClient(api_url=api_url, api_key=api_key)
                    task = PlexusTask.get_by_id(task_id, client)
                    
                    # Update the task status based on the chat responses
                    ai_responses = [r for r in responses if r.get("type") == "ai_message"]
                    if ai_responses:
                        # Get the latest AI response
                        latest_response = ai_responses[-1]["content"]
                        # Use a truncated version for the status message
                        status_msg = (latest_response[:100] + "...") if len(latest_response) > 100 else latest_response
                        
                        # Update task with response
                        task.update(
                            status="COMPLETED",
                            statusMessage=status_msg,
                            resultData=json.dumps({
                                "chat_id": chat_id,
                                "responses": responses
                            })
                        )
            except Exception as e:
                logging.error(f"Error updating task {task_id}: {str(e)}")
        
        # Return the results
        return {
            "chat_id": chat_id,
            "message": message,
            "responses": responses,
            "logs": message_logs
        }
        
    except Exception as e:
        error_msg = f"Error processing chat message: {str(e)}"
        logging.error(error_msg)
        return {
            "chat_id": chat_id,
            "message": message,
            "error": error_msg
        }

@shared_task(bind=True, name="plexus.score_chat.end_session")
def end_chat_session(self: Task, chat_id: str) -> Dict[str, Any]:
    """End a chat session and clean up resources.
    
    Args:
        chat_id: The chat session to end
        
    Returns:
        Status message
    """
    try:
        if chat_id in active_chat_sessions:
            # Remove the chat session
            del active_chat_sessions[chat_id]
            return {
                "chat_id": chat_id,
                "status": "success",
                "message": f"Chat session {chat_id} ended successfully"
            }
        else:
            return {
                "chat_id": chat_id,
                "status": "warning",
                "message": f"Chat session {chat_id} not found"
            }
    except Exception as e:
        error_msg = f"Error ending chat session: {str(e)}"
        logging.error(error_msg)
        return {
            "chat_id": chat_id,
            "status": "error",
            "message": error_msg
        }

def generate_chat_id() -> str:
    """Generate a unique chat ID.
    
    Returns:
        A unique identifier for a chat session
    """
    return f"chat-{uuid.uuid4()}" 
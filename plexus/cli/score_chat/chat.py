"""
Command module for Plexus score chat commands.

This module provides the CLI commands for using the Plexus score chat feature,
supporting both interactive REPL mode and Celery-based API access.
"""

import click
import os
import json
from typing import Optional
from plexus.cli.score_chat.repl import ScoreChatREPL
from plexus.cli.score_chat.celery import generate_chat_id, process_chat_message, end_chat_session

@click.group(name="score-chat")
def score_chat():
    """Commands for working with the Plexus score chat feature."""
    pass

@score_chat.command()
@click.option('--scorecard', help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', help='Score identifier (ID, name, key, or external ID)')
def repl(scorecard: Optional[str], score: Optional[str]):
    """Launch an interactive REPL for working with Plexus scores.
    
    If --scorecard and --score are provided, the REPL will start with that score's configuration.
    Otherwise, you can select a scorecard and score using the REPL commands.
    """
    repl = ScoreChatREPL(scorecard, score)
    repl.run()

@score_chat.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score identifier (ID, name, key, or external ID)')
@click.option('--message', required=True, help='The message to process')
@click.option('--chat-id', help='Chat session ID (generated if not provided)')
def message(scorecard: str, score: str, message: str, chat_id: Optional[str] = None):
    """Send a message directly to the Plexus score chat service.
    
    This is a synchronous version of the Celery task for testing purposes.
    """
    if not chat_id:
        chat_id = generate_chat_id()
        print(f"Generated chat ID: {chat_id}")
    
    # Call the task function directly (not as a Celery task)
    result = process_chat_message(chat_id=chat_id, message=message, 
                               scorecard=scorecard, score=score)
    
    # Print the result
    print(json.dumps(result, indent=2))
    
    return result

@score_chat.command()
@click.option('--chat-id', required=True, help='Chat session ID to end')
def end(chat_id: str):
    """End a chat session manually.
    
    This is a synchronous version of the Celery task for testing purposes.
    """
    # Call the task function directly (not as a Celery task)
    result = end_chat_session(chat_id=chat_id)
    
    # Print the result
    print(json.dumps(result, indent=2))
    
    return result

def register_tasks(app):
    """Register Celery tasks with the Celery app.
    
    This function should be called from the main Celery app setup.
    
    Args:
        app: The Celery app to register tasks with
    """
    # Import task functions
    from plexus.cli.score_chat.celery import process_chat_message, end_chat_session
    
    # Register tasks with the Celery app
    app.task(name=process_chat_message.name)(process_chat_message)
    app.task(name=end_chat_session.name)(end_chat_session)
    
    return app 
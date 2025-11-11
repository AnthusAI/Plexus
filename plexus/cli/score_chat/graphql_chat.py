"""
GraphQL-based command module for Plexus score chat commands.

This module provides CLI commands that use the GraphQL API instead of Celery,
while preserving all existing functionality including file editing.
"""

import click
import os
import json
import asyncio
from typing import Optional
from plexus.cli.score_chat.repl import ScoreChatREPL
from plexus.cli.score_chat.graphql_service import GraphQLChatService, create_chat_session, resume_chat_session


@click.group(name="score-chat")
def score_chat():
    """Commands for working with the Plexus score chat feature via GraphQL API."""
    pass


@score_chat.command()
@click.option('--scorecard', help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', help='Score identifier (ID, name, key, or external ID)')
def repl(scorecard: Optional[str], score: Optional[str]):
    """Launch an interactive REPL for working with Plexus scores.
    
    If --scorecard and --score are provided, the REPL will start with that score's configuration.
    Otherwise, you can select a scorecard and score using the REPL commands.
    """
    # The REPL can still use the existing ScoreChatREPL
    # which uses ScoreChatService internally
    repl = ScoreChatREPL(scorecard, score)
    repl.run()


@score_chat.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score identifier (ID, name, key, or external ID)')
@click.option('--message', required=True, help='The message to process')
@click.option('--session-id', help='Chat session ID (created if not provided)')
@click.option('--account-id', help='Account ID (defaults to environment variable)')
def message(scorecard: str, score: str, message: str, session_id: Optional[str] = None, account_id: Optional[str] = None):
    """Send a message via the GraphQL API.
    
    This creates a persistent chat session in the database and processes
    messages with full file-editing capabilities.
    """
    async def process_message():
        # Get account ID from environment if not provided
        if not account_id:
            account_id_env = os.environ.get('PLEXUS_ACCOUNT_ID')
            if not account_id_env:
                raise ValueError("PLEXUS_ACCOUNT_ID environment variable must be set")
        else:
            account_id_env = account_id
        
        try:
            if session_id:
                # Resume existing session
                service = await resume_chat_session(session_id)
                print(f"Resumed chat session: {session_id}")
            else:
                # Create new session
                service = await create_chat_session(account_id_env, scorecard, score)
                print(f"Created chat session: {service.session_id}")
            
            # Process the message
            result = await service.process_message_with_graphql(message)
            
            # Print the result
            print(json.dumps({
                'session_id': result['session_id'],
                'responses': result['responses']
            }, indent=2))
            
            return result
            
        except Exception as e:
            error_result = {
                'error': str(e),
                'session_id': session_id
            }
            print(json.dumps(error_result, indent=2))
            return error_result
    
    # Run the async function
    return asyncio.run(process_message())


@score_chat.command()
@click.option('--session-id', required=True, help='Chat session ID to end')
def end(session_id: str):
    """End a chat session.
    
    This updates the session status in the database to COMPLETED.
    """
    async def end_session():
        try:
            service = GraphQLChatService(session_id=session_id)
            result = await service.end_session()
            
            print(json.dumps(result, indent=2))
            return result
            
        except Exception as e:
            error_result = {
                'error': str(e),
                'session_id': session_id
            }
            print(json.dumps(error_result, indent=2))
            return error_result
    
    return asyncio.run(end_session())


@score_chat.command()
@click.option('--account-id', help='Account ID (defaults to environment variable)')
@click.option('--limit', default=10, help='Maximum number of sessions to list')
def list_sessions(account_id: Optional[str] = None, limit: int = 10):
    """List recent chat sessions for an account."""
    async def list_sessions_async():
        # Get account ID from environment if not provided
        if not account_id:
            account_id_env = os.environ.get('PLEXUS_ACCOUNT_ID')
            if not account_id_env:
                raise ValueError("PLEXUS_ACCOUNT_ID environment variable must be set")
        else:
            account_id_env = account_id
        
        try:
            service = GraphQLChatService()
            sessions = await service.client.list_chat_sessions(
                account_id=account_id_env, 
                limit=limit
            )
            
            print(json.dumps(sessions, indent=2))
            return sessions
            
        except Exception as e:
            error_result = {'error': str(e)}
            print(json.dumps(error_result, indent=2))
            return error_result
    
    return asyncio.run(list_sessions_async())


@score_chat.command()
@click.option('--session-id', required=True, help='Chat session ID')
@click.option('--limit', default=50, help='Maximum number of messages to show')
def history(session_id: str, limit: int = 50):
    """Show chat history for a session."""
    async def show_history():
        try:
            service = GraphQLChatService()
            messages = await service.client.list_chat_messages(
                session_id=session_id,
                limit=limit
            )
            
            print(json.dumps(messages, indent=2))
            return messages
            
        except Exception as e:
            error_result = {
                'error': str(e),
                'session_id': session_id
            }
            print(json.dumps(error_result, indent=2))
            return error_result
    
    return asyncio.run(show_history())


# No need for register_tasks function since we're not using Celery
def register_graphql_chat_commands(cli_group):
    """Register GraphQL chat commands with a CLI group.
    
    Args:
        cli_group: Click group to register commands with
    """
    cli_group.add_command(score_chat)
    return cli_group
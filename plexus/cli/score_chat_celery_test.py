"""
Test script for the Celery-based Score Chat feature.

This script allows for manual testing of the Celery-based chat functionality,
simulating calling the task directly or via the Celery task queue.
"""

import os
import sys
import json
import click
from typing import Optional
from plexus.cli.score_chat_celery import generate_chat_id, process_chat_message, end_chat_session
from plexus.cli.CommandDispatch import create_celery_app

@click.group()
def cli():
    """Test script for the Celery-based Score Chat feature."""
    pass

@cli.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score identifier (ID, name, key, or external ID)')
@click.option('--local', is_flag=True, help='Run the test locally (without using Celery)')
@click.option('--num-messages', default=3, help='Number of test messages to send')
def run_test(scorecard: str, score: str, local: bool, num_messages: int):
    """Run a full test of the Celery-based chat functionality."""
    # Generate a unique chat ID for this test
    chat_id = generate_chat_id()
    print(f"Test chat ID: {chat_id}")
    
    # Initialize the chat session with a welcome message
    if local:
        # Call the function directly for local testing
        result = process_chat_message(
            chat_id=chat_id,
            message="Hello, I'd like to work on this score.",
            scorecard=scorecard,
            score=score
        )
    else:
        # Use Celery for distributed testing
        celery_app = create_celery_app()
        result = celery_app.send_task(
            'plexus.score_chat.message',
            kwargs={
                'chat_id': chat_id,
                'message': "Hello, I'd like to work on this score.",
                'scorecard': scorecard,
                'score': score
            }
        ).get()  # Wait for the result
    
    # Print the initialization result
    print("\n=== Initialization Result ===")
    print(json.dumps(result, indent=2))
    
    # Send a series of test messages
    test_messages = [
        "What kind of score is this?",
        "Can you explain how the scoring works?",
        "Can we modify this score to use a different model?"
    ]
    
    # Only use the first num_messages messages
    test_messages = test_messages[:num_messages]
    
    for i, message in enumerate(test_messages):
        print(f"\n=== Sending Message {i+1}: '{message}' ===")
        
        if local:
            # Call the function directly for local testing
            result = process_chat_message(
                chat_id=chat_id,
                message=message
            )
        else:
            # Use Celery for distributed testing
            result = celery_app.send_task(
                'plexus.score_chat.message',
                kwargs={
                    'chat_id': chat_id,
                    'message': message
                }
            ).get()  # Wait for the result
        
        # Print the message result
        print(f"\n=== Result for Message {i+1} ===")
        print(json.dumps(result, indent=2))
    
    # End the chat session
    print("\n=== Ending Chat Session ===")
    if local:
        result = end_chat_session(chat_id=chat_id)
    else:
        result = celery_app.send_task(
            'plexus.score_chat.end_session',
            kwargs={'chat_id': chat_id}
        ).get()
    
    print(json.dumps(result, indent=2))
    
    print("\n=== Test Complete ===")

@cli.command()
@click.option('--scorecard', required=True, help='Scorecard identifier (ID, name, key, or external ID)')
@click.option('--score', required=True, help='Score identifier (ID, name, key, or external ID)')
@click.option('--message', required=True, help='Message to send')
@click.option('--chat-id', help='Chat ID (generated if not provided)')
@click.option('--local', is_flag=True, help='Run the test locally (without using Celery)')
def send_message(scorecard: str, score: str, message: str, chat_id: Optional[str], local: bool):
    """Send a single message to the chat service."""
    # Generate a chat ID if not provided
    if not chat_id:
        chat_id = generate_chat_id()
        print(f"Generated chat ID: {chat_id}")
    
    if local:
        # Call the function directly for local testing
        result = process_chat_message(
            chat_id=chat_id,
            message=message,
            scorecard=scorecard,
            score=score
        )
    else:
        # Use Celery for distributed testing
        celery_app = create_celery_app()
        result = celery_app.send_task(
            'plexus.score_chat.message',
            kwargs={
                'chat_id': chat_id,
                'message': message,
                'scorecard': scorecard,
                'score': score
            }
        ).get()  # Wait for the result
    
    # Print the result
    print(json.dumps(result, indent=2))

@cli.command()
@click.option('--chat-id', required=True, help='Chat ID to end')
@click.option('--local', is_flag=True, help='Run the test locally (without using Celery)')
def end_session(chat_id: str, local: bool):
    """End a chat session."""
    if local:
        result = end_chat_session(chat_id=chat_id)
    else:
        celery_app = create_celery_app()
        result = celery_app.send_task(
            'plexus.score_chat.end_session',
            kwargs={'chat_id': chat_id}
        ).get()
    
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    cli() 
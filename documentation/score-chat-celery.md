# Plexus Score Chat - Celery Edition

This documentation explains how to use the Celery-based Score Chat system in Plexus.

## Overview

The Plexus Score Chat system provides an AI assistant that helps users view and modify scorecard score configurations through natural language. It operates in two modes:

1. **CLI REPL Mode**: Interactive terminal-based chat interface (`plexus score-chat repl`)
2. **Celery API Mode**: Message-based API for integration with other services

Both modes use the same core AI agent and file handling capabilities, allowing for a consistent experience regardless of the interface. For detailed implementation plans and technical architecture, see `plans/score-chat-command.md`.

## Architecture

The system consists of these key components:

1. `ScoreChatService`: Core service that handles chat functionality and AI interactions
   - Manages chat sessions and history
   - Handles file editing operations
   - Processes AI responses and tool calls
   - Maintains conversation context
   
2. `ScoreChatREPL`: Terminal-based interactive chat interface
   - Rich-formatted terminal UI
   - Command history support
   - Real-time response streaming
   
3. `score_chat_celery.py`: Celery tasks for processing messages via API
   - Asynchronous message processing
   - Session management
   - Task status tracking
   - Dashboard integration
   
4. `ScoreChatCommands.py`: Command-line interface for both modes
   - REPL command (`score-chat repl`)
   - Direct message command (`score-chat message`)
   - Session management commands

## Using the CLI REPL

To start an interactive chat session:

```bash
plexus score-chat repl --scorecard <scorecard_id> --score <score_id>
```

This opens a REPL where you can chat with the AI assistant about the score configuration.

## Using the Celery API

The Celery API provides two main tasks:

1. `plexus.score_chat.message`: Process a chat message
2. `plexus.score_chat.end_session`: End a chat session

### Creating a Chat Session

To create a new chat session:

```python
from plexus.cli.score_chat_celery import generate_chat_id
from plexus.cli.CommandDispatch import create_celery_app

# Create a Celery app
celery_app = create_celery_app()

# Generate a unique chat ID
chat_id = generate_chat_id()

# Start a new chat session
result = celery_app.send_task(
    'plexus.score_chat.message',
    kwargs={
        'chat_id': chat_id,
        'message': 'Hello, I want to modify this score.',
        'scorecard': 'my-scorecard-id',
        'score': 'my-score-id'
    }
).get()
```

### Sending Messages to an Existing Session

Once you have a chat session, you can send more messages to it:

```python
# Send a follow-up message
result = celery_app.send_task(
    'plexus.score_chat.message',
    kwargs={
        'chat_id': chat_id,
        'message': 'Can you change the LLM model to GPT-4?'
    }
).get()
```

### Ending a Chat Session

When you're done with a chat session, you should end it to free up resources:

```python
# End the chat session
result = celery_app.send_task(
    'plexus.score_chat.end_session',
    kwargs={
        'chat_id': chat_id
    }
).get()
```

## Response Format

The response from the chat API includes:

```json
{
  "chat_id": "chat-12345678-1234-5678-1234-567812345678",
  "message": "Can you change the LLM model to GPT-4?",
  "responses": [
    {
      "type": "ai_message",
      "content": "I'll help you change the model to GPT-4..."
    },
    {
      "type": "tool_result",
      "tool": "str_replace_editor",
      "command": "view",
      "result": "..."
    }
  ],
  "logs": [
    "Retrieving score configuration...",
    "Updated score configuration..."
  ]
}
```

- `responses`: List of AI responses and tool operations performed
- `logs`: Log messages from the service operations

## Testing

You can use the test script to test the chat functionality without a full Celery setup:

```bash
python -m plexus.cli.score_chat_celery_test run-test --scorecard <id> --score <id> --local
```

Or to test a single message:

```bash
python -m plexus.cli.score_chat_celery_test send-message --scorecard <id> --score <id> --message "Hello" --local
```

## Integration with Dashboard Tasks

To integrate with the Dashboard task system, include the `task_id` parameter:

```python
result = celery_app.send_task(
    'plexus.score_chat.message',
    kwargs={
        'chat_id': chat_id,
        'message': 'Hello',
        'scorecard': 'my-scorecard',
        'score': 'my-score',
        'task_id': 'dashboard-task-id'
    }
).get()
```

This will automatically update the Dashboard task with the chat response.

## Deployment

The chat Celery tasks are automatically registered when the Plexus worker starts.
To ensure your workers process these tasks, update your worker start command:

```bash
plexus command worker --concurrency 4
```

## Error Handling

The system includes robust error handling:
- Automatic retries for API timeouts and connection issues
- Session recovery for interrupted conversations
- Graceful degradation for tool failures
- Detailed error logging and reporting

## Security Considerations

- All chat sessions are isolated and maintain their own state
- API authentication is required for all operations
- File operations are restricted to the score configuration directory
- Session data is cleaned up when sessions end

## Future Enhancements

See `plans/score-chat-command.md` for planned future enhancements, including:
- Batch operations support
- Version comparison tools
- Score template management
- Collaborative editing features 
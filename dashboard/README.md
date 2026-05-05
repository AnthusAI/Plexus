# Plexus Dashboard

This is a Next.js/Shadcn dashboard built on Amplify Gen2 for Plexus, with a Python API client code and a CLI tool. This dashboard is part of the [Plexus AI Agent Incubator](../README.md), providing a visual interface for managing scorecards and monitoring classification performance.

## Overview

The dashboard is the command center for Plexus operations. It allows users to:

- Monitor real-time activity via the **Activity Dashboard**.
- Manage **Scorecards** and **Scores**.
- View and grade items in **Feedback Queues**.
- Analyze **Evaluation Results**.
- Configure system settings and alerts.

For information on how AI agents integrate with this system, please see the [Agent Integration Guide](../AGENTS.md).

## Installation

Install the Plexus client Python module in development mode:
```bash
pip install -e .
```

## Configuration

Set up your environment variables in a `.env` file:
```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION_NAME=... 
PLEXUS_API_URL=...
PLEXUS_API_KEY=...
PLEXUS_ACCOUNT_KEY=...
```

For local procedure runs from the dashboard UI:
- `npm run dev` starts only the Next.js dev server
- `npm run dev:chat` starts the local Console chat worker (`plexus chat worker`)
- `npm run dev:dispatch` starts the local command task dispatcher (`PLEXUS_DISPATCH_MODE=local`)
- `npm run dev:workers` starts both local workers

`PLEXUS_ACCOUNT_KEY` is required for this local auto-dispatch flow.
Set `NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET=local:<developer>` for the web app and
run the chat worker with the matching `CONSOLE_RESPONSE_TARGET` or
`plexus chat worker --target local:<developer>`.
Console chat now targets the built-in procedure key `builtin:console/chat` backed by source-controlled Tactus code under `plexus/procedures/console/`.

Dispatch modes are intentionally separate:
- `plexus chat worker` handles pending Console `ChatMessage` rows for one local response target.
- `plexus command dispatcher` handles pending `Task` rows and either sends them to Celery or runs them locally.
- `PLEXUS_DISPATCH_MODE=local` inside `execute_tactus` means an async report/procedure request uses the direct local development path instead of remote Celery dispatch.

## Usage

### Python API

The library provides a client that mirrors the GraphQL schema structure:

```python
from plexus_dashboard.api.client import PlexusDashboardClient

# Initialize client with optional context
client = PlexusDashboardClient(
    context={
        'account_key': 'call-criteria',
        'scorecard_key': 'agent-performance'
    }
)

# Create a score result for an agent's call quality
client.ScoreResult.create(
    value=0.95,                    # 95% quality score
    item_id="call_20240309_123",   # Specific call being scored
    metadata={
        "duration_seconds": 342,
        "customer_sentiment": "positive",
        "topics": ["billing", "upgrade"]
    }
)

# Create a compliance score with immediate processing
client.ScoreResult.create(
    value=0.82,                    # 82% compliance score
    item_id="call_20240309_123",   # Same call, different score
    immediate=True,                # Process right away
    metadata={
        "regulations": ["pci", "hipaa"],
        "violations": []
    }
)

# Batch create multiple scores
client.ScoreResult.batch_create([
    {
        "value": 0.95,
        "item_id": "call_20240309_124",
        "metadata": {"agent_id": "agent_456"}
    },
    {
        "value": 0.88,
        "item_id": "call_20240309_125",
        "metadata": {"agent_id": "agent_457"}
    }
])

# Look up a scorecard by key
scorecard = client.Scorecard.get_by_key("agent-performance")

# Get an account by ID
account = client.Account.get_by_id("acc_123")
```

### Command Line Interface

Use `plexus-dashboard` to interact with the API:
```bash
# Create a score result
plexus-dashboard score-result create \
  --value 0.95 \
  --item call_20240309_123 \
  --account-id acc-123 \
  --scoring-job-id job-123 \
  --scorecard-id card-123 \
  --confidence 0.87 \
  --metadata '{"duration_seconds": 342, "topics": ["billing"]}'

# Update a score result
plexus-dashboard score-result update abc123 \
  --value 0.98 \
  --metadata '{"reviewed": true}'
```

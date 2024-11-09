## Plexus Dashboard

This is a Next.js/Shadcn dashboard built on Amplify Gen2 for Plexus, with a Python API client code and a CLI tool.

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
```

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
  --item-id call_20240309_123 \
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

### Working with Experiments

The library provides background processing for experiment operations:

```python
from plexus_dashboard.api.client import PlexusDashboardClient

client = PlexusDashboardClient(
    context={
        'account_key': 'call-criteria',
        'scorecard_key': 'agent-performance'
    }
)

# Create an experiment (non-blocking)
client.Experiment.create(
    type="accuracy",
    accountId="acc-123",
    scorecardId="card-123",
    parameters={
        "model": "gpt-4",
        "threshold": 0.8
    }
)

# Get an existing experiment
experiment = client.Experiment.get_by_id("exp-123")

# Update experiment status (non-blocking)
experiment.update(
    status="RUNNING",
    progress=0.45,
    processedItems=45,
    totalItems=100
)

# Add experiment results (non-blocking)
experiment.update(
    status="COMPLETED",
    accuracy=0.95,
    metrics={
        "precision": 0.94,
        "recall": 0.96,
        "f1": 0.95
    },
    confusionMatrix={
        "true_positive": 85,
        "false_positive": 5,
        "true_negative": 90,
        "false_negative": 4
    }
)

# Log experiment failure (non-blocking)
experiment.update(
    status="FAILED",
    errorMessage="Model API timeout",
    errorDetails={
        "timestamp": "2024-03-09T08:45:23Z",
        "request_id": "req-789",
        "error_code": "TIMEOUT"
    }
)
```

### Simulating Experiments

The CLI provides a simulation command for testing and demonstration purposes:

```bash
# Simulate an evaluation experiment
plexus-dashboard experiment simulate \
  --account-key call-criteria \
  --scorecard-key agent-scorecard \
  --num-items 100 \
  --accuracy 0.85
```

The simulate command:
- Creates an Experiment record
- Generates synthetic binary classification results
- Computes standard ML metrics in real-time
- Updates the experiment with metrics as results are generated

This is useful for:
- Testing the experiment tracking system
- Demonstrating the metrics calculation pipeline
- Generating sample data for UI development
- Validating metric calculations

The simulation parameters:
- `num_items`: Number of synthetic results to generate (default: 100)
- `accuracy`: Target accuracy for synthetic data (default: 0.85)
- Random delays between results (0.1-1.0 seconds)
- Random confidence scores (0.7-0.99)

The simulation computes and tracks:
- Overall accuracy
- Precision
- Sensitivity (Recall)
- Specificity
- Confusion matrix

Each result includes:
- Binary prediction (Yes/No)
- Confidence score
- Correctness flag
- Metadata with true/predicted values

## Implementation Details

### Background Processing
- Configurable batch sizes (default: 10 items)
- Configurable timeouts (default: 1 second)
- Immediate processing option for urgent data
- Automatic flushing on shutdown
- Error resilient (errors are logged but don't affect main thread)

### ID Resolution
- Lazy resolution of IDs from keys/names
- Caching of resolved IDs
- Thread-safe operations
- Graceful error handling

### Thread Safety
All client operations are thread-safe and can be used in concurrent environments.

#### Background Processing
All mutations (create/update) in the Experiment model are performed in background 
threads for non-blocking operation. This allows the main application to continue 
while experiment data is being saved.

- Create operations spawn a new thread
- Update operations spawn a new thread
- Errors are logged but don't affect the main thread
- No batching (experiments are processed individually)

#### Error Handling
Background operations handle errors gracefully:
```python
# This won't block or raise errors in the main thread
experiment.update(
    status="RUNNING",
    progress=0.5
)

# Continue immediately while update happens in background
print("Continuing with other work...")
```

## License

This library is licensed under the MIT-0 License. See the LICENSE file.
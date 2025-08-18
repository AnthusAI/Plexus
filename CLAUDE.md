# Plexus Project Guide

## Project Overview
Plexus is an orchestration system for AI/ML classification at scale. It provides a standardized framework for managing, evaluating and monitoring classification models.

## Key Components
- **Scorecard System**: Classifications organized with scorecards, sections, and individual scores
- **Task Dispatch System**: Two-level system connecting Next.js dashboard to Python workers via AWS Lambda
- **Dashboard**: Next.js/React frontend with TypeScript and Amplify Gen2
- **MCP Server**: Multi-Agent Cooperative Protocol for AI agent integration

## Build & Test Commands
### Dashboard
- Development: `npm run dev`
- Build: `npm run build`
- Lint: `npm run lint`
- Typecheck: `npm run typecheck`
- Tests: `npm test` or `npm run test:watch`
- Storybook: `npm run storybook`

### Python Backend
- **Environment**: Uses `py311` Conda environment 
- Task worker: `plexus command worker`
- Run evaluation: `plexus evaluate accuracy --scorecard-name <name>`
- Create report: `plexus report config create --name "Test" --file config.md`
- Generate report: `plexus report run --config "Test"`
- View last report: `plexus report last`

## Project Structure
- `/dashboard/`: Next.js application 
- `/plexus/`: Python backend modules
- `/MCP/`: Multi-Agent Cooperative Protocol server
- `/documentation/`: Project documentation

## Architecture Notes
- **Authentication**: AWS Amplify/Cognito
- **Data Storage**: DynamoDB with GraphQL API
- **Task Queue**: AWS SQS with Celery workers
- **Progress Tracking**: TaskProgressTracker system with stages

## Development Policies
- Do not run `npm run dev` yourself (developer runs that)
- Do not make git changes directly (no commits or pushing)
- Follow code style guidelines in dashboard/CLAUDE.md

- You can't test changes you make to MCP tools until we restart either the MCP server or you, so ask me to do that whenever you make changes to the MCP server tools.
- You should use the Plexus MCP tools rather than CLI tools or custom code tools whenever possible because they're more token-efficient with the output.  You only need other options when an existing MCP tool won't work or when you have changed the MCP tool since you can't access the new version until we restart either the MCP server or you.

## Configuration Loading (CRITICAL)

**NEVER manually set environment variables with secrets in test scripts.** Always use the proper Plexus configuration system.

### Correct Pattern for Test Scripts
```python
from plexus.cli.shared.client_utils import create_client

# This automatically loads .plexus/config.yaml and sets all environment variables
client = create_client()

# Now environment variables like OPENAI_API_KEY are available
import os
api_key = os.getenv('OPENAI_API_KEY')
```

### For Non-CLI Code (like services)
```python
from plexus.config.loader import load_config
import os

# Load Plexus configuration from .plexus/config.yaml
# This sets ALL environment variables including OPENAI_API_KEY
load_config()

# Now access environment variables normally
api_key = os.getenv('OPENAI_API_KEY')
plexus_api_url = os.getenv('PLEXUS_API_URL')
```

### How Configuration Loading Works
1. **Configuration Files**: Plexus loads from `.plexus/config.yaml` in current directory or home directory
2. **Environment Variable Mapping**: Configured in `plexus/config/loader.py:76` with mapping like `'openai.api_key': 'OPENAI_API_KEY'`
3. **DRY Pattern**: All CLI commands use `create_client()` which calls `load_config()` internally
4. **Precedence**: Environment variables > YAML config > defaults

### What NOT to Do
```python
# WRONG - Do not manually set secrets
PLEXUS_API_URL = "https://..."
PLEXUS_API_KEY = "da2-..."
OPENAI_API_KEY = "sk-..."

# WRONG - Do not set environment variables manually in scripts
os.environ['OPENAI_API_KEY'] = 'sk-...'
```

### Example Test Script (Correct Way)
```python
import sys
sys.path.append('/Users/ryan.porter/Projects/Plexus')

from plexus.cli.shared.client_utils import create_client
from plexus.cli.experiment.service import ExperimentService

# This loads .plexus/config.yaml automatically
client = create_client()
service = ExperimentService(client)

# Configuration is now loaded, proceed with test
result = service.run_experiment(experiment_id)
```
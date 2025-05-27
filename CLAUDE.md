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

## Score Types
- ProgrammaticScore: Custom code-based scoring
- KeywordClassifier: Simple keyword matching
- FuzzyMatchClassifier: Fuzzy text matching
- SemanticClassifier: Embedding-based matching
- LangGraphScore: LangGraph flow-based scoring
- SimpleLLMScore: Direct LLM-based scoring
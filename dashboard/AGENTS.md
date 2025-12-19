# Dashboard Development Guide

## Tech Stack

### Frontend Framework
- **Next.js 14.1** - React framework with server-side rendering
- **React** - UI library
- **TypeScript** - Type-safe JavaScript
- **Shadcn UI** - Component library

### Backend & Infrastructure
- **AWS Amplify Gen2** - Backend infrastructure and hosting
- **AWS Cognito** - Authentication and user management
- **GraphQL** - API layer for data operations
- **DynamoDB** - Database for task state
- **SQS + Celery** - Remote task dispatch to Python worker nodes

## Project Structure

### Key Directories
```
dashboard/
├── app/              # Next.js routes & pages
├── components/       # React components
├── amplify/          # AWS configuration & resources
├── utils/            # Utility functions
└── stories/          # Storybook component stories
```

## Core Files

### Authentication & Routing
**`app/client-layout.tsx`**
- Controls authentication and public routes
- Manages route access via `publicPaths` array
- Protected routes redirect to landing page

### Data Layer
**`amplify/data/resource.ts`**
- Core data model definitions
- GraphQL schema configuration
- Defines entities and relationships

**`utils/amplify-client.ts`**
- API client implementation
- Handles GraphQL operations
- Manages data fetching and mutations

## Task Progress Tracking System

The dashboard implements a multi-stage progress tracking system for long-running Python tasks.

### Key Implementation Files
- **`plexus/cli/task_progress_tracker.py`** - Core progress tracking (Python backend)
- **`components/Task.tsx`** - Task display component (React)
- **`components/ui/task-status.tsx`** - Progress bar UI implementation

### Progress Bar Behavior
- Only stages with `total_items` set will show progress bars
- Setup and Finalizing stages typically don't show progress
- Main Processing stages should show progress bars

### Documentation
For detailed task stage configuration, see docstrings in:
1. `TaskProgressTracker` class
2. `StageConfig` class
3. `Stage` class

## Authentication Flow

1. Auth handled by **AWS Amplify / Cognito**
2. Routes checked against `publicPaths` in `client-layout.tsx`
3. Protected routes redirect to landing page if not authenticated
4. Data operations flow through `amplify-client.ts`

## Development Workflow

### Running the Dashboard
```bash
cd dashboard
npm install
npm run dev
```

### Running Tests
```bash
cd dashboard
npm test
npm run test:coverage
```

### Storybook (Component Development)
```bash
cd dashboard
npm run storybook
```

## Task Dispatch Architecture

The dashboard dispatches tasks to remote Python workers:

1. User triggers task in dashboard (React/TypeScript)
2. GraphQL mutation sent to Amplify API
3. Task queued to AWS SQS
4. Celery worker (Python) picks up task
5. Worker processes task, updates progress via GraphQL
6. Dashboard polls for updates and displays progress
7. Results returned through GraphQL API

## Common Patterns

### Fetching Data
```typescript
import { generateClient } from 'aws-amplify/data';
const client = generateClient();

// Query data
const { data } = await client.models.Scorecard.list();

// Mutation
await client.models.Score.create({ name: 'New Score' });
```

### Protected Routes
Add to `publicPaths` array in `client-layout.tsx`:
```typescript
const publicPaths = [
  '/',
  '/login',
  '/signup',
  // Add your public route here
];
```

### Task Progress Updates
See `TaskProgressTracker` in Python backend for how to emit progress updates that the dashboard will display.

## File Naming Conventions

- **Routes**: `app/path/to/page.tsx`
- **Components**: `components/component-name.tsx` (kebab-case)
- **Client components**: Use `'use client'` directive at top
- **Server components**: Default (no directive needed)

## TypeScript Configuration

Dashboard has its own complete configuration:
- `package.json` - Dependencies and scripts
- `package-lock.json` - Locked dependency versions
- `tsconfig.json` - TypeScript compiler options
- `jest.config.js` - Test configuration

## AWS Amplify Gen2

### Resource Configuration
All AWS resources defined in `amplify/` directory:
- Data models (GraphQL schema)
- Authentication configuration
- Storage buckets
- Functions and triggers

### Deployment
```bash
cd dashboard
npx amplify sandbox  # Development environment
npx amplify deploy   # Production deployment
```

## Tips for AI Agents

- Always check `publicPaths` when working on authentication
- Task progress tracking requires both frontend (React) and backend (Python) changes
- Use Storybook for component development and testing
- GraphQL schema changes require Amplify code generation
- Dashboard is separate from root Python project - has its own dependencies

# Plexus Scorecard Management System

## Overview

This document outlines the implementation of Plexus's scorecard management system, which will provide a modern, user-friendly interface for managing scorecards and their configurations. The system will evolve from basic YAML editing to a sophisticated no-code visual block editor.

## Core Architecture

### Project Structure and File Path Conventions
- All dashboard components and features are contained within the `dashboard/` project directory
- ⚠️ IMPORTANT: Never create component files in the root project directory
  - ✅ Correct: `dashboard/components/ui/Button.tsx`
  - ❌ Incorrect: `components/ui/Button.tsx`
- File paths in imports must use the `@/dashboard` prefix for Next.js module resolution:
  - ✅ Correct: `import { Button } from "@/dashboard/components/ui/button"`
  - ❌ Incorrect: `import { Button } from "components/ui/button"`
  - ❌ Incorrect: `import { Button } from "@/components/ui/button"`
- Component locations:
  - UI components: `dashboard/components/ui/`
  - Feature components: `dashboard/components/[feature-name]/`
  - Pages: `dashboard/app/`
- When referencing paths in documentation or code:
  - Always use `@/dashboard` prefix for imports
  - Use relative paths only for same-directory imports
  - The `@/` alias is configured in tsconfig.json to point to the project root

### Existing Data Models
- Scorecard: Contains name, key, description, accountId, externalId, itemId
- ScorecardSection: Groups scores with name and order
- Score: Individual scoring criteria with name, key, description, order, type, configuration
- Relationships:
  - Scorecard -> ScorecardSection (1:many)
  - ScorecardSection -> Score (1:many)
  - Scorecard -> Account (many:1)

### Scorecard Components
- Grid-based dashboard layout matching other dashboards (Evaluations, Activity)
- Scorecard item component with dual-mode support (grid/detail)
- YAML configuration management interface
- Visual block editor for no-code configuration (future phase)

## Current Status

### Phase 1: Core Components
- Status: ✅ Completed
- Achievements:
  - Base Card component implemented and stable
  - ScorecardComponent and ScoreComponent created with grid/detail views
  - Initial component hierarchy established
  - Dashboard layout implemented with grid/detail view
  - Removed subscription-based updates
  - Fixed component organization and import paths
  - Implemented consistent styling and spacing
  - Completed component renaming for clarity
  - Finalized detail view layouts and functionality
  - Added proper metadata display and state management

### Phase 2: Schema Updates
- Status: ✅ Completed
- Achievements:
  - Created new `ScoreVersion` model to store versioned score configurations
  - Moved score configuration from `Score` model to `ScoreVersion`
  - Added `championVersion` reference in `Score` to track current version
  - Updated GraphQL schema and resolvers
  - Updated front-end types and components to match new schema
  - Successfully migrated existing configurations to new structure

### Phase 3: Front-End UI Updates (Current Focus)
- Status: In Progress
- Goals:
  - Update UI to support score version management
  - Add version history view for scores
  - Implement version comparison interface
  - Add ability to promote versions to champion
  - Show version metadata in evaluation results
- Next Steps:
  - Design version management UI components
  - Implement version history view
  - Add version promotion workflow
  - Update evaluation display to show version info

### Phase 3.5: Data Integrity Issues
- Status: Critical - In Progress
- Problems Identified:
  - Incorrect scorecard external IDs causing reference issues
  - Duplicate scores within scorecards creating ambiguity and evaluation errors
- Goals:
  - Fix incorrect external IDs across all scorecards
  - Identify and resolve duplicate scores
  - Implement validation to prevent future duplicates
  - Ensure data consistency between API and CLI tools
- Next Steps:
  - Audit all scorecards to identify incorrect external IDs
  - Create migration script to correct external IDs
  - Develop duplicate score detection algorithm
  - Implement score deduplication process
  - Add validation rules to prevent creation of duplicate scores
  - Update CLI tools to handle and report data integrity issues

### Phase 4: CLI API Integration
- Status: Planned
- Goals:
  - Update `plexus evaluate accuracy` to use API
  - Remove dependency on local YAML files for evaluation
  - Support fetching score configuration from cloud
  - Add version selection for evaluations
- Next Steps:
  - Update CLI evaluation command
  - Add API client for score version fetching
  - Implement version selection logic
  - Add progress indicators for API operations

### Phase 5: YAML Mode Support
- Status: Planned
- Goals:
  - Add commands for syncing score configuration YAML
  - Support `plexus scorecard pull` for downloading configs
  - Support `plexus scorecard push` for uploading configs
  - Maintain backward compatibility with YAML workflow
- Next Steps:
  - Design YAML format for version data
  - Implement pull/push commands
  - Add conflict resolution
  - Document YAML mode workflow

### Score Version Management
- Status: In Progress
- Implementation Details:
  - Score configurations are versioned in new `ScoreVersion` model
  - Each `Score` has a `championVersion` reference to its current champion
  - `ScoreResult` has optional `scoreVersion` reference for backward compatibility
  - Evaluations track which version they evaluated via `scoreVersion` reference
  - Optimized index structure for quick lookups:
    - `ScoreVersion`: `scoreId` + `createdAt` sort key for version history
    - `Evaluation`: `scoreVersionId` + `createdAt` sort key for latest results

#### Example GraphQL Query for Dashboard
This query efficiently fetches scores with their champion versions and latest evaluations:
```graphql
query GetScorecardScores($scorecardId: ID!) {
  listScores(filter: { scorecardId: { eq: $scorecardId } }) {
    items {
      id
      name
      type
      # ... other score fields ...
      championVersion {
        id
        configuration
        evaluations(
          filter: { status: { eq: "COMPLETED" } }
          sortDirection: DESC
          limit: 1
        ) {
          items {
            id
            accuracy
            createdAt
            # ... other evaluation fields ...
          }
        }
      }
    }
  }
}
```

This query structure enables:
- Single-query loading of scorecard dashboard
- Direct access to champion versions
- Efficient retrieval of latest evaluation results
- O(1) lookup time for most recent evaluations

### Phase 3-4: Future Phases
- Visual editor and advanced features planned for future iterations
- Will build on stable foundation from Phase 1 and 2
- Features to consider:
  - No-code visual block editor
  - Advanced configuration options
  - Enhanced validation rules
  - Template system
  - Bulk operations support

## Component Architecture

### Base Components
1. Card Component (`components/ui/card.tsx`)
   - Core layout component for all cards in the system
   - Supports grid/detail variants
   - Handles selection state
   - Manages full-width toggle
   - Common header/content structure
   - Props:
     ```typescript
     interface CardProps {
       variant: 'grid' | 'detail'
       title: string
       subtitle?: string
       time?: string
       isSelected?: boolean
       isFullWidth?: boolean
       onToggleFullWidth?: () => void
       onClose?: () => void
       controlButtons?: React.ReactNode
     }
     ```

2. Task Card (`components/TaskCard.tsx`)
   - Extends base Card
   - Adds task-specific functionality:
     - Status management
     - Progress tracking
     - Stage visualization
   - Used for Evaluations, Scoring Jobs, etc.

3. Scorecard Card (`components/ScorecardCard.tsx`)
   - Extends base Card
   - Grid view shows summary stats
   - Detail view contains:
     - Metadata (key, externalId)
     - Grid of Score Cards
     - Configuration panel

4. Score Card (`components/ScoreCard.tsx`)
   - Extends base Card
   - Shows score configuration
   - Grid view shows key metrics
   - Detail view shows full configuration

### Component Hierarchy
```
Card (Base)
├── TaskCard
│   ├── EvaluationTask
│   ├── ScoringJobTask
│   └── BatchJobTask
├── ScorecardCard
│   └── Grid<ScoreCard>
└── ScoreCard
```
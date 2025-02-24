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

### Phase 2: Schema Updates (Current Focus)
- Status: In Progress
- Goals:
  - Update UI to support score version management
  - Add version history view for scores
  - Implement version comparison interface
  - Add ability to promote versions to champion
  - Show version metadata in evaluation results
  - Add version indicator with timestamp in ScoreComponent
  - Add version history dropdown in ScoreComponent
  - Support creating new versions through name editing
- Progress:
  ✅ Basic version history UI implemented in ScoreComponent
  ✅ Version comment field added when editing scores
  ✅ Version list fetching from API working
  ✅ Creating new versions with comments working
  ✅ Version history expandable/collapsible view
  ✅ Basic version metadata display (timestamp, comment)
  🔄 In Progress:
    - Version promotion to champion
    - Version comparison interface
    - Version metadata in evaluation results
  📝 Next Steps:
    - Add version promotion workflow
    - Update evaluation display to show version info
    - Add version comparison UI
    - Implement version metadata in evaluation results
    - Add version indicator with timestamp to ScoreComponent
    - Add version history dropdown menu
    - Add name editing and new version creation flow

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

### Layout Patterns
1. Dashboard Layout
   - Left panel: Grid of ScorecardCards
   - Right panel: Selected ScorecardCard in detail mode

2. Scorecard Detail Layout
   - Header: Scorecard metadata
   - Content: Grid of ScoreCards
   - Right panel (when score selected): ScoreCard detail

3. Common Features
   - All cards support selection
   - Detail views support full-width toggle
   - Consistent grid/detail transitions
   - Uniform styling and spacing

### UI/UX Guidelines
- Consistent card sizing in grids
- Smooth transitions between states
- Clear selection indicators
- Uniform padding and spacing
- Responsive grid layouts
- Match existing dashboard patterns (Evaluations, Activity)
- Clear feedback for user actions
- Simple YAML editing interface
- Consistent styling with other components

### Data Flow
1. Dashboard loads scorecard list using existing GraphQL queries
2. Selection updates detail view
3. YAML edits update Score configuration
4. Changes saved through existing mutations

### Development Guidelines

#### Story Development
1. Create stories alongside component development
2. Cover all component variants and states
3. Document props and usage in story files
4. Include interactive examples
5. Test responsive behavior
6. Ensure accessibility in all states

#### Testing Requirements
- Visual regression tests for stories
- Interaction testing for interactive states
- Accessibility testing in Storybook
- Responsive testing across breakpoints

### Score Version Management UI
- Status: In Progress
- Implementation Details:
  - Each ScoreComponent displays:
    ✅ Basic header structure matching ScorecardComponent:
      - Editable title field with consistent styling
      - Editable external ID field with monospace font
      - Save/Cancel buttons appearing on changes
      - Action buttons in top-right (more, full width, close)
    - Current version indicator showing:
      - Relative timestamp using standard Timestamp component
      - "Champion" pill for champion version
      - Star icon for featured versions (clickable in detail mode)
      - Left-aligned placement under header section
    - Version history dropdown showing:
      - 12 most recent versions in reverse chronological order
      - Champion status via pill
      - Featured status via star icon
      - Relative timestamp for each version
  - Version Creation Flow:
    ✅ Name editing matches ScorecardCard UX:
      - In-place editing with same styling
      - Save/Cancel buttons appear on edit
      - Only name field editable initially
      - Name is required, no other validation
    - New version behavior:
      - Inherits configuration from current version
      - Does not automatically become champion
      - Timestamp set to creation time
  - UI Layout:
    ✅ Top-right corner reserved for action buttons (X, square, "...")
    ✅ Basic header layout established
    - Version selector positioned left-aligned under header
    - Version controls placed above YAML editor section
  - UI Components Needed:
    ✅ Editable name field
    ✅ Save/Cancel action buttons
    - Version indicator with timestamp
    - Champion status pill
    - Featured status star icon (interactive)
    - Version history dropdown

- Data Access Patterns
  - To achieve fast lookups in production, the Score record will store denormalized fields from the champion ScoreVersion:
    - Name and externalId are duplicated in the Score record.
    - A Global Secondary Index (GSI) will be applied on externalId (and optionally on name) to allow rapid querying of the current champion score.
    - This approach ensures that even while a full history is maintained in ScoreVersion records, the primary Score record remains the single source of truth for fast access.

- Overall Benefit
  - A single GraphQL query can quickly retrieve the current champion score using the denormalized fields, and then access the full version history via the associated ScoreVersion content.
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
  ✅ Version promotion to champion
  ✅ Version comparison interface
  ✅ Version metadata in evaluation results
  ✅ Version indicator with timestamp to ScoreComponent
  ✅ Version history dropdown menu
  ✅ Name editing and new version creation flow
  ✅ Featured version indicator and toggle functionality

### Phase 3: CLI API Integration (Current Focus)
- Status: ✅ Completed
- Goals:
  - Update `plexus evaluate accuracy` to use API
  - Remove dependency on local YAML files for evaluation
  - Support fetching score configuration from cloud
  - Add version selection for evaluations
  - Improve CLI scorecard display
- Progress:
  ✅ Enhanced scorecard display in CLI with improved layout
  ✅ Added "Scores" header to tree view with proper alignment
  ✅ Implemented full-width tree view for better readability
  ✅ Ensured proper display in both single and multiple column modes
  ✅ Added new `plexus scorecards score` command to view detailed information about a single score
  ✅ Implemented lookup by score ID, key, or external ID
  ✅ Added support for viewing score version history and configuration
  ✅ Optimized scorecard data fetching with single comprehensive GraphQL query
  ✅ Added `--fast` option to skip fetching sections and scores for better performance
  ✅ Added progress indicators for API operations
  ✅ Updated documentation to reflect new commands and performance improvements

### Phase 4: YAML Mode Support
- Status: In Progress
- Goals:
  - Add commands for syncing score configuration YAML
  - Support `plexus scorecard pull` for downloading configs
  - Support `plexus scorecard push` for uploading configs
  - Maintain backward compatibility with YAML workflow
- Implementation Plan:
  1. CLI Consolidation:
     - Remove redundant `plexus-dashboard scorecard sync` command
     - Consolidate all scorecard management functionality in the main `plexus` CLI
     - Ensure any unique functionality from dashboard CLI is preserved
  
  2. Handle duplicate records:
     - When synchronizing a score, check for multiple implementations of the same score ID in API
     - Reduce to maximum of one implementation
  
  3. Implement version-based upsert:
     - Perform upsert into score version record instead of score record
     - Find version corresponding to local YAML code
     - Create new child record from matching version
  
  4. Optimization:
     - Perform string comparison before creating new score version
     - Only create new version if YAML code differs
     - Otherwise just update timestamp on existing version
     - Add appropriate version metadata (user, timestamp, comment)
  
  5. New CLI Commands:
     - `plexus scorecard pull`: Download latest champion version of scores to local YAML files
     - `plexus scorecard push`: Upload local YAML changes as new versions
     - `plexus scorecard history`: View version history for scores
     - `plexus scorecard promote`: Promote specific version to champion
  
  6. Implementation Details:
     - Pull command will fetch champion versions of scores and save to local YAML files
     - Push command will create new versions of scores from local YAML files
     - History command will display version history with timestamps, comments, and status
     - Promote command will set a specific version as the champion
     - All commands will support filtering by scorecard, score name, or score key

### Score Version Management
- Status: ✅ Completed
- Implementation Details:
  - Score configurations are versioned in new `ScoreVersion` model
  - Each `Score` has a `championVersion` reference to its current champion
  - `ScoreResult` has optional `scoreVersion` reference for backward compatibility
  - Evaluations track which version they evaluated via `scoreVersion` reference
  - Optimized index structure for quick lookups:
    - `ScoreVersion`: `scoreId` + `createdAt` sort key for version history
    - `Evaluation`: `scoreVersionId` + `createdAt` sort key for latest results
  - UI Features Implemented:
    - Version history dropdown with timestamps and comments
    - Champion version promotion workflow
    - Featured version toggle
    - Version notes/comments
    - Version comparison
    - New version creation on edit

### Performance Improvements
- Status: ✅ Completed
- Implementation Details:
  - Replaced multiple separate GraphQL queries with a single comprehensive query
  - Eliminated the "N+1 query problem" in scorecard data fetching
  - Added `--fast` option to skip fetching sections and scores for better performance
  - Added `--hide-scores` option to exclude score details from output
  - Improved error handling and debug output
  - Updated documentation to reflect performance enhancements
  - Added progress indicators for long-running operations
  - Optimized score lookup with multiple identification methods (ID, key, name, external ID)

### Documentation Updates
- Status: ✅ Completed
- Implementation Details:
  - Updated Scorecards concept page with comprehensive CLI management section
  - Added Best Practices section with guidance on organization and performance
  - Updated Add/Edit Scorecard page with performance considerations
  - Added Score Version Management section to Add/Edit Score page
  - Added YAML Configuration section with examples
  - Updated CLI examples to reflect new commands and options
  - Added Efficient Score Lookup section explaining multiple lookup methods

### Phase 5: Visual Editor (Future)
- Status: Planned
- Goals:
  - Implement no-code visual block editor
  - Add advanced configuration options
  - Enhance validation rules
  - Create template system
  - Support bulk operations
- Next Steps:
  - Design visual editor interface
  - Implement block-based configuration
  - Add validation and testing tools
  - Create template library

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
- Status: ✅ Completed
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
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
  - Review and update data models for improved structure
  - Implement new GraphQL schema changes
  - Update queries and mutations for better data handling
  - Migrate existing data to new structure
  - Ensure backward compatibility during transition
- Next Steps:
  - Document current schema limitations
  - Design new schema structure
  - Plan migration strategy
  - Create migration scripts
  - Test data integrity

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
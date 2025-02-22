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

## Storybook Requirements

### Base Card Stories
```typescript
// Card.stories.tsx
export default {
  title: 'Components/Card',
  component: Card,
  argTypes: {
    variant: {
      control: 'radio',
      options: ['grid', 'detail']
    },
    isSelected: {
      control: 'boolean'
    },
    isFullWidth: {
      control: 'boolean'
    }
  }
} as Meta<typeof Card>

// Stories to implement:
- Grid Mode (Default)
- Grid Mode Selected
- Detail Mode
- Detail Mode Full Width
- With Control Buttons
- With Custom Content
- With Long Title/Subtitle
- Loading State
```

### Task Card Stories
```typescript
// TaskCard.stories.tsx
// Stories to implement:
- Grid Mode (Various Task Types)
- Detail Mode with Stages
- With Progress
- With Error State
- With Different Statuses
- Selected State
- Interactive Stage Progress
```

### Scorecard Card Stories
```typescript
// ScorecardCard.stories.tsx
// Stories to implement:
- Grid Mode (Empty)
- Grid Mode (With Scores)
- Grid Mode Selected
- Detail Mode
- Detail Mode with Scores Grid
- With Configuration Panel
- With YAML Editor
- Loading States
- Error States
```

### Score Card Stories
```typescript
// ScoreCard.stories.tsx
// Stories to implement:
- Grid Mode (Different Score Types)
- Detail Mode with Configuration
- Selected State
- With Validation Errors
- With Different Score Types
- Interactive Configuration
```

### Interactive Examples
- Card Selection Flow
- Full-width Toggle Animation
- Grid to Detail Transition
- Nested Selection (Scorecard -> Score)
- Configuration Changes
- Error Handling

## Implementation Plan

### Phase 1: Core Components
1. Base Card Component
   - Implement core card structure
   - Add variant support
   - Handle selection state
   - Add full-width toggle
   - Create comprehensive Storybook stories

2. Task Card Component
   - Extend base card
   - Add task-specific features
   - Migrate existing task components
   - Add task-specific stories
   - Document component variations

3. Scorecard Components
   - Implement ScorecardCard
   - Implement ScoreCard
   - Add grid layout support
   - Create stories for all states
   - Document usage patterns

### Phase 2: YAML Configuration
1. Score Configuration Editor
   - Add to ScoreCard detail view
   - Support YAML editing
   - Real-time validation

2. Scorecard Configuration
   - Metadata management
   - Section ordering
   - Score relationships

### Phase 3: Integration
1. Data Management
   - GraphQL mutations for updates
   - Real-time sync
   - Optimistic updates

2. State Management
   - Selection handling
   - View state persistence
   - Configuration changes

### Phase 4: Visual Editor (Future)
- Build on card component structure
- Add drag-and-drop support
- Visual configuration tools

## Current Status

### Phase 1: Core Components
- Status: In Progress with Issues
- Completed:
  - Base Card component implemented
  - ScorecardCard component created
  - Initial component hierarchy established
  - Cleaned up redundant components
  - Removed misplaced files from root app directory
- Current Issues:
  - Dashboard UI is currently unstable
  - Subscription-related error causing dashboard to clear
  - Component organization needs review
- Next Steps:
  - Debug subscription error causing dashboard clearing
  - Stabilize front-end component structure
  - Review and fix component import paths
  - Test and verify component state management

### Phase 2-4: Not Started

## Implementation Details

### Component Usage Example
```typescript
// Dashboard layout
<div className="flex">
  <div className="w-1/3">
    {scorecards.map(scorecard => (
      <ScorecardCard
        key={scorecard.id}
        variant="grid"
        isSelected={selectedId === scorecard.id}
        onSelect={handleSelect}
        {...scorecard}
      />
    ))}
  </div>
  {selectedScorecard && (
    <div className="w-2/3">
      <ScorecardCard
        variant="detail"
        isFullWidth={isFullWidth}
        onToggleFullWidth={toggleFullWidth}
        {...selectedScorecard}
      >
        <div className="grid grid-cols-3 gap-4">
          {scores.map(score => (
            <ScoreCard
              key={score.id}
              variant="grid"
              isSelected={selectedScoreId === score.id}
              onSelect={handleScoreSelect}
              {...score}
            />
          ))}
        </div>
      </ScorecardCard>
    </div>
  )}
</div>
```

### UI/UX Guidelines
- Consistent card sizing in grids
- Smooth transitions between states
- Clear selection indicators
- Uniform padding and spacing
- Responsive grid layouts

### Component Structure
```typescript
// Planned component hierarchy
<ScorecardDashboard>
  <ScorecardList>
    {/* Shows scorecard names in grid layout */}
  </ScorecardList>
  <ScorecardDetail mode="grid|detail">
    <ScorecardHeader>
      {/* Name, description, etc */}
    </ScorecardHeader>
    <ScorecardContent>
      {/* YAML editor or score list depending on mode */}
    </ScorecardContent>
    <ScorecardFooter>
      {/* Actions, status, etc */}
    </ScorecardFooter>
  </ScorecardDetail>
</ScorecardDashboard>
```

### Data Flow
1. Dashboard loads scorecard list using existing GraphQL queries
2. Selection updates detail view
3. YAML edits update Score configuration
4. Changes saved through existing mutations
5. Real-time updates through subscriptions

### UI/UX Guidelines
- Match existing dashboard patterns (Evaluations, Activity)
- Smooth transitions between grid and detail modes
- Clear feedback for user actions
- Simple YAML editing interface
- Consistent styling with other components 

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

## Implementation Plan

### Phase 1: Core Components
1. Base Card Component
   - Implement core card structure
   - Add variant support
   - Handle selection state
   - Add full-width toggle
   - Create comprehensive Storybook stories

2. Task Card Component
   - Extend base card
   - Add task-specific features
   - Migrate existing task components
   - Add task-specific stories
   - Document component variations

3. Scorecard Components
   - Implement ScorecardCard
   - Implement ScoreCard
   - Add grid layout support
   - Create stories for all states
   - Document usage patterns

### Phase 2: YAML Configuration
1. Score Configuration Editor
   - Add to ScoreCard detail view
   - Support YAML editing
   - Real-time validation

2. Scorecard Configuration
   - Metadata management
   - Section ordering
   - Score relationships

### Phase 3: Integration
1. Data Management
   - GraphQL mutations for updates
   - Real-time sync
   - Optimistic updates

2. State Management
   - Selection handling
   - View state persistence
   - Configuration changes

### Phase 4: Visual Editor (Future)
- Build on card component structure
- Add drag-and-drop support
- Visual configuration tools

## Current Status

### Phase 1: Core Components
- Status: In Progress with Issues
- Completed:
  - Base Card component implemented
  - ScorecardCard component created
  - Initial component hierarchy established
  - Cleaned up redundant components
  - Removed misplaced files from root app directory
- Current Issues:
  - Dashboard UI is currently unstable
  - Subscription-related error causing dashboard to clear
  - Component organization needs review
- Next Steps:
  - Debug subscription error causing dashboard clearing
  - Stabilize front-end component structure
  - Review and fix component import paths
  - Test and verify component state management

### Phase 2-4: Not Started

## Implementation Details

### Component Usage Example
```typescript
// Dashboard layout
<div className="flex">
  <div className="w-1/3">
    {scorecards.map(scorecard => (
      <ScorecardCard
        key={scorecard.id}
        variant="grid"
        isSelected={selectedId === scorecard.id}
        onSelect={handleSelect}
        {...scorecard}
      />
    ))}
  </div>
  {selectedScorecard && (
    <div className="w-2/3">
      <ScorecardCard
        variant="detail"
        isFullWidth={isFullWidth}
        onToggleFullWidth={toggleFullWidth}
        {...selectedScorecard}
      >
        <div className="grid grid-cols-3 gap-4">
          {scores.map(score => (
            <ScoreCard
              key={score.id}
              variant="grid"
              isSelected={selectedScoreId === score.id}
              onSelect={handleScoreSelect}
              {...score}
            />
          ))}
        </div>
      </ScorecardCard>
    </div>
  )}
</div>
```

### UI/UX Guidelines
- Consistent card sizing in grids
- Smooth transitions between states
- Clear selection indicators
- Uniform padding and spacing
- Responsive grid layouts

### Component Structure
```typescript
// Planned component hierarchy
<ScorecardDashboard>
  <ScorecardList>
    {/* Shows scorecard names in grid layout */}
  </ScorecardList>
  <ScorecardDetail mode="grid|detail">
    <ScorecardHeader>
      {/* Name, description, etc */}
    </ScorecardHeader>
    <ScorecardContent>
      {/* YAML editor or score list depending on mode */}
    </ScorecardContent>
    <ScorecardFooter>
      {/* Actions, status, etc */}
    </ScorecardFooter>
  </ScorecardDetail>
</ScorecardDashboard>
```

### Data Flow
1. Dashboard loads scorecard list using existing GraphQL queries
2. Selection updates detail view
3. YAML edits update Score configuration
4. Changes saved through existing mutations
5. Real-time updates through subscriptions

### UI/UX Guidelines
- Match existing dashboard patterns (Evaluations, Activity)
- Smooth transitions between grid and detail modes
- Clear feedback for user actions
- Simple YAML editing interface
- Consistent styling with other components 
# Plexus Item Management System

## Overview

This document outlines the implementation of Plexus's item management system, which will provide a modern, user-friendly interface for managing items and their details. The system will evolve from the current table-based list to a grid-based card layout similar to the scorecards dashboard.

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
- Item: Contains id, scorecard, score, date, status, results, inferences, cost
- Relationships:
  - Item -> Scorecard (many:1)
  - Item -> ScoreResults (1:many)
  - Item -> Account (many:1)

### Item Components
- Grid-based dashboard layout matching other dashboards (Scorecards, Evaluations)
- Item card component with dual-mode support (grid/detail)
- Detail view for comprehensive item information
- Storybook integration for component development and testing

## Implementation Plan

### Phase 1: Storybook Integration
- Status: ✅ Completed
- Achievements:
  - Created ItemDetail.stories.tsx with comprehensive fake data
  - Implemented multiple story variants (Default, WithError, NewItem)
  - Added state management in the story wrapper component
  - Created sample data structures for metadata, transcript, and score results
  - Implemented interactive handlers for feedback and annotations
  - Ensured proper styling and layout in storybook environment
  - Moved fake data from app to storybook
  - Set up proper component documentation with autodocs

### Phase 2: UI Modernization
- Status: 🔄 In Progress
- Goals:
  - Create base ItemCard component
  - Implement grid/detail view modes
  - Establish component hierarchy
  - Update UI to use grid-based card layout
  - Replace table-based list with card grid
  - Implement responsive design for all viewports
  - Add card selection and detail view
  - Ensure consistent styling with other dashboards
  - Implement smooth transitions between states
  - Add proper loading and error states
  - Optimize performance for large item lists
  - Add sorting and filtering capabilities
  - Implement pagination or infinite scrolling

### Phase 3: Data Integration
- Status: 📅 Planned
- Goals:
  - Connect real data to item cards
  - Replace fake data with API calls
  - Implement proper data fetching and caching
  - Add error handling for API failures
  - Optimize data loading with pagination
  - Implement real-time updates for item status
  - Add proper loading states during data fetching
  - Ensure consistent data formatting
  - Implement proper error recovery
  - Add retry mechanisms for failed requests

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

2. ItemCard (`components/items/ItemCard.tsx`)
   - Extends base Card
   - Grid view shows summary stats
   - Detail view contains:
     - Metadata (id, scorecard, date)
     - Status and metrics (results, inferences, cost)
     - Score visualization

3. ItemDetail (`components/items/ItemDetail.tsx`)
   - Comprehensive view of item details
   - Shows metadata, transcript, and score results
   - Supports expandable/collapsible sections
   - Handles full-width toggle
   - Manages state for expanded sections

### Component Hierarchy
```
Card (Base)
├── ItemCard
└── ItemDetail
```

### Layout Patterns
1. Dashboard Layout
   - Left panel: Grid of ItemCards
   - Right panel: Selected ItemCard in detail mode

2. Item Detail Layout
   - Header: Item metadata
   - Content: Expandable sections for metadata, transcript, and score results
   - Right panel (when selected): Full ItemDetail view

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
- Match existing dashboard patterns (Scorecards, Evaluations)
- Clear feedback for user actions
- Consistent styling with other components

### Data Flow
1. Dashboard loads item list using existing GraphQL queries
2. Selection updates detail view
3. Detail view loads additional item data as needed
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

### Performance Considerations
- Implement virtualization for large item lists
- Optimize data fetching with pagination
- Use proper memoization for expensive calculations
- Implement efficient state management
- Optimize rendering performance
- Use proper loading states during data fetching
- Implement proper error handling and recovery 
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
- Status: ✅ Completed
- Achievements:
  - Created base ItemCard component with grid/detail variants
  - Implemented responsive grid layout for items dashboard
  - Replaced table-based list with card grid
  - Added card selection and detail view
  - Ensured consistent styling with other dashboards
  - Implemented smooth transitions between states
  - Added proper loading and error states
  - Created Storybook stories for ItemCard component
  - Implemented responsive design for all viewports
  - Added proper metadata display in grid and detail views
  - Ensured consistent UI patterns with scorecard dashboard
  - Optimized layout density with more columns based on container width
  - Moved status pill to the right side below the item icon
  - Made cards more compact to fit better in the denser grid

### Phase 3: Data Integration
- Status: 🔄 In Progress
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

### Phase 4: Item Creation and Evaluation Tracking
- Status: 🔄 Planned
- Problem Statement:
  - Currently, items are not being automatically created when score results are generated
  - No distinction between evaluation items and production items in the database
  - No data appears in the items dashboard due to missing item records
- Goals:
  - Implement automatic item creation during the scoring process
  - Add evaluation tracking to distinguish between evaluation and production items
  - Ensure idempotent item creation to prevent duplicates
  - Update schema to support filtering by evaluation status
  - Optimize query performance for item retrieval

#### Item Creation Process
1. Automatic Item Creation:
   - When a score result is generated, check if an item with the same ID exists
   - If no item exists, create a new item record with appropriate metadata
   - If item exists, use the existing item for the score result
   - Ensure this process is idempotent to handle concurrent score result creation

2. Schema Updates:
   - Add `isEvaluation` boolean field to the Item model
   - Default value: `false` (production item)
   - Set to `true` when item is created as part of an evaluation

3. Data Model Changes:
   ```typescript
   Item: a
     .model({
       // Existing fields
       name: a.string().required(),
       description: a.string(),
       accountId: a.string().required(),
       // New field
       isEvaluation: a.boolean().required(),
       // Existing relationships
       account: a.belongsTo('Account', 'accountId'),
       // ...
     })
   ```

4. Query Optimization:
   - Challenge: Efficiently querying for non-evaluation items by accountId
   - DynamoDB limitations:
     - Can only query efficiently on partition key (accountId) and sort key (updatedAt)
     - Cannot directly filter by isEvaluation in the initial query
   - Recommended solution: Create a composite GSI (Global Secondary Index)
     
     - How it works:
       - Create a GSI with a composite partition key that combines accountId and isEvaluation
       - Use updatedAt as the sort key to enable sorting by recency
       - This allows efficient querying for specific combinations (e.g., all non-evaluation items for an account)
     
     - Implementation in Amplify schema:
       ```typescript
       Item: a
         .model({
           // Existing fields
           name: a.string().required(),
           description: a.string(),
           accountId: a.string().required(),
           isEvaluation: a.boolean().required(),
           updatedAt: a.datetime(),
           // ... other fields
         })
         .authorization((allow) => [
           allow.publicApiKey(),
           allow.authenticated()
         ])
         .secondaryIndexes((idx) => [
           // Existing index
           idx("accountId"),
           // New composite GSI
           idx("accountId-isEvaluation-index")
             .key(["accountId", "isEvaluation"])
             .sortKeys(["updatedAt"])
         ])
       ```
     
     - Query example:
       ```typescript
       // Query for recent non-evaluation items for a specific account
       const items = await API.graphql({
         query: listItemsByAccountAndEvaluationStatus,
         variables: {
           accountId: "ACC123",
           isEvaluation: false,
           sortDirection: "DESC", // Most recent first
           limit: 20,
           nextToken: pageToken
         }
       });
       ```
     
     - Benefits:
       - Highly efficient queries for specific combinations
       - Proper pagination support
       - Maintains sort capability by updatedAt
       - No client-side filtering needed
       - Reads only the relevant items (no wasted read capacity)
     
     - Implementation considerations:
       - Requires schema update and data migration
       - Additional storage overhead for the index
       - Need to generate appropriate GraphQL queries/mutations

#### Implementation Strategy
1. Score Result Processing:
   - Modify the Score class to handle item creation during predict/evaluate
   - Add API client integration to post items and score results
   - Implement idempotent item creation logic
   - Add context tracking to determine if a score is from evaluation

2. API Integration:
   - Create helper functions for item upsert operations
   - Implement batch processing for multiple score results
   - Add error handling and retry logic
   - Ensure proper transaction handling for related operations

3. Dashboard Updates:
   - Add filtering capability by evaluation status
   - Update item card to display evaluation status
   - Implement efficient pagination with filtering
   - Add visual indicators for evaluation vs. production items

#### Performance Considerations
- Use batch operations when creating multiple items/results
- Implement caching for frequently accessed items
- Consider implementing a write-through cache for item lookups
- Monitor DynamoDB capacity and adjust as needed
- Implement backoff strategies for API rate limiting
- Consider background processing for bulk operations

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
   - Props:
     ```typescript
     interface ItemCardProps {
       item: ItemData
       variant?: 'grid' | 'detail'
       isSelected?: boolean
       onClick?: () => void
       isFullWidth?: boolean
       onToggleFullWidth?: () => void
       onClose?: () => void
       getBadgeVariant: (status: string) => string
     }
     ```

3. ItemDetail (`components/ItemDetail.tsx`)
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
   - Responsive grid layout:
     - 2 columns for phone mode
     - 3 columns for tablet portrait mode
     - 4+ columns for wide mode, expanding as container width increases

2. Item Detail Layout
   - Header: Item metadata (using ItemCard in detail mode)
   - Content: Expandable sections for metadata, transcript, and score results (using ItemDetail)
   - Right panel (when selected): Full ItemDetail view

3. Common Features
   - All cards support selection
   - Detail views support full-width toggle
   - Consistent grid/detail transitions
   - Uniform styling and spacing
   - Status pill positioned on the right side below the item icon

### UI/UX Guidelines
- Compact card sizing in grids to maximize visible items
- Smooth transitions between states
- Clear selection indicators
- Uniform padding and spacing
- Responsive grid layouts based on container width (not viewport width)
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
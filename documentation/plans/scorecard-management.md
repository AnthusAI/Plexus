# Plexus Scorecard Management System

## Overview

This document outlines the implementation of Plexus's scorecard management system, which will provide a modern, user-friendly interface for managing scorecards and their configurations. The system will evolve from basic YAML editing to a sophisticated no-code visual block editor.

## Core Architecture

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

## Implementation Plan

### Phase 1: Dashboard Layout Modernization
1. Update Scorecard Dashboard Layout
   - Implement grid-based layout matching other dashboards
   - Create list view showing scorecard names
   - Add detail panel slot
2. Create Dual-Mode Scorecard Component
   - Grid mode: Display scorecard name and associated score names
   - Detail mode: Full scorecard configuration view
   - Implement mode switching with smooth transitions
   - Ensure consistent styling with Task and EvaluationTask components

### Phase 2: YAML Configuration Management
1. Basic YAML Editor Integration
   - Add Monaco Editor component for YAML editing
   - Pass through existing YAML configuration
   - Add basic syntax highlighting
   - Implement save functionality
2. Configuration Management
   - Direct YAML editing interface
   - Save/load using existing GraphQL mutations
   - Basic error handling for YAML syntax
   - Real-time preview if possible

### Phase 3: GraphQL Integration
1. Use Existing Schema
   - Leverage current Scorecard, ScorecardSection, and Score models
   - Utilize existing relationships and indexes
   - Maintain AWS Amplify Gen2 access control
2. API Integration
   - Implement necessary queries and mutations
   - Set up subscriptions for real-time updates
   - Ensure proper error handling
   - Maintain authorization rules

### Phase 4: Visual Block Editor (Future)
- Detailed planning to be done when reaching this phase
- Will build on top of YAML management system
- Focus on user-friendly interface for common configurations

## Current Status

### Phase 1: Dashboard Layout Modernization
- Status: Not Started
- Next Steps:
  - Begin dashboard layout updates
  - Create ScorecardList component
  - Design ScorecardDetail component with mode support

### Phase 2: YAML Configuration Management
- Status: Not Started
- Next Steps:
  - Set up Monaco Editor integration
  - Implement basic YAML editing functionality

### Phase 3: GraphQL Integration
- Status: Partial
- Existing:
  - Schema models defined
  - Basic relationships established
  - Access control configured
- Next Steps:
  - Review existing queries/mutations
  - Plan subscription implementation

### Phase 4: Visual Block Editor
- Status: Future Phase
- No immediate action required

## Implementation Details

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
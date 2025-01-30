# Workflow Pictograms Documentation

## File Organization

### Core Components
- `dashboard/components/workflow/nodes/`
  - `circle-node.tsx` - Standard circular node implementation
  - `square-node.tsx` - Square node with stepped rotation
  - `triangle-node.tsx` - Triangle node with scale animation
  - `hexagon-node.tsx` - Hexagon node with rotating inner element

### Base Components
- `dashboard/components/workflow/base/`
  - `container-base.tsx` - SVG container wrapper
  - `connection-base.tsx` - Connection line renderer

### Types and Utilities
- `dashboard/components/workflow/types.ts` - Shared types and interfaces

### Implementation Examples
- `dashboard/components/landing/workflow.tsx` - Landing page workflow demo

### Storybook Stories
- `dashboard/stories/workflow-nodes.stories.tsx` - Individual node demonstrations
  - Node States - Static display of each node type in each state
  - Node Sequences - Animated sequence demonstration
  - Media Nodes - Audio, Image, and Text node types
  - Classifier Nodes - Thumbs Up/Down node demonstrations
- `dashboard/stories/workflow-diagrams.stories.tsx` - Full workflow demonstrations
  - Base - Standard workflow layout
  - MultiModel - Complex workflow with multiple model types
  - ItemList - List-based workflow visualization

## Overview
The workflow pictograms provide visual representations of Plexus workflows, featuring animated nodes and connections. They serve both as UI elements in the dashboard and as interactive demonstrations on the landing page.

## Components

### Node Types ✓
- Circle Node: Standard processing node ✓
  - Spinning ring animation during processing ✓
  - Simple, clean design for main processes ✓
- Square Node: Alternative processing style ✓
  - Stepped 90-degree rotation with pauses ✓
  - Used for structured, systematic processes ✓
- Triangle Node: Alert/Decision node ✓
  - Throbbing scale animation ✓
  - Positioned slightly larger than other nodes ✓
- Hexagon Node: Complex processing node ✓
  - Counter-rotating inner hexagon ✓
  - Used for multi-step or advanced processes ✓

### Node States ✓
- Not Started ✓
  - Static outline with inner shape ✓
  - Neutral border color ✓
- Processing ✓
  - Shape-specific animations ✓
  - Secondary color for processing indicator ✓
- Complete ✓
  - Filled background ✓
  - Checkmark with custom positioning per shape ✓
  - Success color scheme ✓

### Connection Lines ✓
- Curved Bezier paths between nodes ✓
- Consistent stroke width and color ✓
- Responsive to node positioning ✓

### Animation System
#### Current Implementation ✓
- Status-based animation control ✓
  - Manual state management ✓
  - useEffect-based timing ✓
  - Direct state transitions ✓
- Basic sequence support ✓
  - Start delay handling ✓
  - Processing duration ✓
  - Completion timing ✓

#### Sequence-Based System ✓
- Declarative animation control ✓
  - Framer Motion integration ✓
  - Predefined sequences ✓
  - Consistent timing management ✓
- Enhanced features ✓
  - Jittered timing variations ✓
  - Coordinated node transitions ✓
  - Automatic cycling ✓

#### Migration Status ✓
- All components migrated to sequence-based system ✓
  - ItemListWorkflow successfully converted ✓
  - Timing refinements implemented ✓
  - Jitter added for organic feel ✓
- Key improvements achieved:
  - Predictable state transitions ✓
  - Configurable timing parameters ✓
  - Smoother animations ✓
  - Better state management ✓

## Development Priorities

1. Container Width Utilization
   - Phase 1: Visual Debug Setup ⏳
     - Add visible container boundaries in Storybook
     - Red border for outer container edge
     - Blue border for inner content area
     - Checkered background to highlight whitespace
   - Phase 2: Layout Adjustments
     - Analyze current spacing in all three diagrams
     - Adjust viewBox and coordinate systems
     - Modify node positioning calculations
     - Update connection line paths
   - Success Criteria
     - Diagrams touch left and right boundaries
     - Consistent spacing between elements
     - No unintended whitespace
     - Maintains visual balance

2. Layout System Improvements
   - Auto-layout capabilities
   - Multiple flow patterns
   - Responsive sizing
   - Dynamic grid adaptation

3. Interactive Features
   - Hover states
   - Click handlers
   - Context menus
   - Tooltip integration

4. Accessibility Implementation
   - ARIA labels
   - Keyboard navigation
   - High contrast mode
   - Reduced motion support

## Technical Implementation

### Stories ✓
- Node component demonstrations ✓
  - Basic node states and sequences ✓
  - Media node types ✓
  - Classifier nodes (with sequence support) ✓
- Full workflow diagrams ✓
  - Basic layouts ✓
  - Multi-model flows ✓
  - Item list patterns with conveyor belt animation ✓

### Animation Timing ✓
- Row entrance: 800ms ✓
- Node stagger: 200ms ✓
- Initial delay: 800ms ✓
- Processing duration: 1200ms ✓
- Completion buffer: 300ms ✓
- Exit animation: 800ms ✓
- Jitter factors:
  - Node stagger: ±25% ✓
  - Processing time: ±20% ✓
  - Completion buffer: ±30% ✓

### Testing
- Component unit tests
- Animation timing verification
- State transition testing
- Responsive layout validation
- Accessibility compliance checks

### Performance
- Animation optimization
- SVG rendering efficiency
- State management overhead
- Transition smoothness

## Usage Patterns

### Dashboard Integration
- Workflow status displays
- Process monitoring
- Real-time updates
- Interactive controls

### Landing Page
- Feature demonstrations
- Interactive examples
- Marketing animations
- Process explanations 
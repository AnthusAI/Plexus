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
  - `workflow-base.tsx` - Base workflow implementation with configurable timing and nodes

### Types and Utilities
- `dashboard/components/workflow/types.ts` - Shared types and interfaces

### Implementation Examples
- `dashboard/components/landing/workflow.tsx` - Landing page workflow demo (circle nodes only)
- `dashboard/components/workflow/layouts/multi-model-workflow.tsx` - Multi-model workflow with varied node types

### Storybook Stories
- `dashboard/stories/workflow-nodes.stories.tsx` - Individual node demonstrations
  - Node States - Static display of each node type in each state
  - Node Sequences - Animated sequence demonstration
  - Media Nodes - Audio, Image, and Text node types
  - Classifier Nodes - Thumbs Up/Down node demonstrations
- `dashboard/stories/workflow-diagrams.stories.tsx` - Full workflow demonstrations
  - Base - Standard workflow layout with circle nodes
  - MultiModel - Complex workflow with diverse node shapes
  - ItemList - List-based workflow visualization

## Overview
The workflow pictograms provide visual representations of Plexus workflows, featuring animated nodes and connections. They serve both as UI elements in the dashboard and as interactive demonstrations on the landing page.

## Components

### Node Types ✓
- Circle Node: Standard processing node ✓
  - Spinning ring animation during processing ✓
  - Simple, clean design for main processes ✓
  - Used exclusively in base workflow diagram ✓
- Square Node: Alternative processing style ✓
  - Stepped 90-degree rotation with pauses ✓
  - Used for structured, systematic processes in multi-model ✓
- Triangle Node: Alert/Decision node ✓
  - Throbbing scale animation ✓
  - Positioned slightly larger than other nodes ✓
  - Custom icon positioning for better visibility ✓
- Hexagon Node: Complex processing node ✓
  - Counter-rotating inner hexagon ✓
  - Used for multi-step or advanced processes in multi-model ✓

### Workflow Variants ✓
#### Base Workflow ✓
- Simple, consistent circle nodes throughout ✓
- Quick processing animations (3-5.5s cycle) ✓
- Standard timing sequence: ✓
  - Main node: 0-3s ✓
  - Row 1A: 1-4s ✓
  - Row 1B: 2-5s ✓
  - Row 2A: 1.5-4.5s ✓
  - Row 2B: 2.5-5.5s ✓
- 2s pause before reset ✓

#### Multi-Model Workflow ✓
- Varied node shapes for different processes ✓
- Extended processing animations to showcase each type ✓
- Custom timing configuration: ✓
  - Main (Circle): 15s processing ✓
  - Row 1A (Hexagon): 10s processing ✓
  - Row 1B (Triangle): 11s processing ✓
  - Row 2A (Square): 10s processing ✓
  - Row 2B (Hexagon): 11s processing ✓
- Quick reset (1s) to maximize processing display ✓

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
  - Enhanced completion animations ✓
    - Check mark: Throb to 140% scale ✓
    - Color-coded backgrounds ✓

### Animation System ✓
- Improved cycle management ✓
  - Proper timer cleanup ✓
  - Race condition prevention ✓
  - Cycle tracking with flags ✓
- Configurable timing ✓
  - Processing delay control ✓
  - Completion delay control ✓
  - Custom reset timing ✓
- State management ✓
  - Clean state transitions ✓
  - No flickering or duplicates ✓
  - Proper cleanup on unmount ✓

## Next Steps

1. Performance Optimization
   - Monitor memory usage during long cycles
   - Profile animation performance
   - Optimize state updates
   - Add performance monitoring

2. Testing and Validation
   - Add unit tests for animation behavior
   - Verify proper cleanup on unmount
   - Test edge cases in animation sequences
   - Validate performance in different scenarios

3. Documentation
   - Add inline code comments
   - Document timing configuration options
   - Create usage examples
   - Add troubleshooting guide 
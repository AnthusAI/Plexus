# ItemCard Skeleton Mode

## Overview

The ItemCard component and its subcomponents now support a skeleton loading mode that renders placeholder elements while maintaining the same layout structure as the loaded content. This prevents layout shifts and provides a consistent user experience during loading states.

## Usage

### Basic Usage

```tsx
import ItemCard from '@/components/items/ItemCard'

// Normal mode (default)
<ItemCard
  item={itemData}
  variant="grid"
  getBadgeVariant={getBadgeVariant}
  skeletonMode={false} // default
/>

// Skeleton mode
<ItemCard
  item={itemData}
  variant="grid" 
  getBadgeVariant={getBadgeVariant}
  skeletonMode={true}
/>
```

### Component Support

The `skeletonMode` prop is supported by the following components:

- **ItemCard**: Main component with grid and detail variants
- **IdentifierDisplay**: Shows skeleton placeholders for ID and identifier elements
- **Timestamp**: Shows skeleton placeholders for time and icon elements
- **NumberFlowWrapper**: Shows skeleton placeholder for animated numbers
- **CardButton**: Shows skeleton placeholder for action buttons
- **ItemScoreResultCard**: Shows skeleton placeholders for scorecard content

### Skeleton Design Principles

1. **Layout Consistency**: Skeleton elements match the exact dimensions and spacing of real content
2. **Visual Hierarchy**: Important elements (headings, icons) are represented with appropriate sizes
3. **Animation**: Uses `animate-pulse` class for subtle loading animation
4. **Responsiveness**: Skeleton layouts adapt to different screen sizes like real content
5. **Static Elements**: Elements that are always present (like the post-it icon and "Item" label) are shown normally rather than skeletonized

### Implementation Strategy

Instead of creating separate skeleton components, each component conditionally renders its skeleton state when `skeletonMode={true}`. This approach:

- Reduces code duplication and maintenance overhead
- Ensures skeleton layouts stay in sync with real content
- Prevents design drift between loading and loaded states
- Maintains consistent component APIs
- Shows static elements normally to provide visual anchors during loading

### Grid View Skeleton

In grid mode, the skeleton includes:
- **Real icon and "Item" label** in top-right corner (always present)
- Identifier display with icon and text placeholders
- Timestamp with icon and text placeholders  
- Elapsed time with icon and text placeholders
- Scorecard name placeholder
- Results count placeholder

### Detail View Skeleton

In detail mode, the skeleton includes:
- Header section with scorecard name placeholder
- Identifier, timestamp, and elapsed time placeholders
- Results summary placeholder
- Action buttons placeholders (more options, full width toggle, close)
- Scorecard breakdown section placeholders (when multiple scorecards)

### Examples

Check the Storybook stories for live examples:

- `GridSkeleton`: Basic grid skeleton
- `GridSelectedSkeleton`: Selected grid skeleton
- `DetailSkeleton`: Basic detail skeleton
- `DetailMultipleScorecardsSkeleton`: Detail skeleton with multiple scorecards
- `SkeletonComparison`: Side-by-side comparison of normal vs skeleton states

### Usage in Real Applications

```tsx
function ItemsList({ items, isLoading }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {isLoading ? (
        // Show skeleton cards while loading
        Array.from({ length: 6 }, (_, i) => (
          <ItemCard
            key={`skeleton-${i}`}
            item={placeholderItem}
            variant="grid"
            getBadgeVariant={getBadgeVariant}
            skeletonMode={true}
          />
        ))
      ) : (
        // Show real data when loaded
        items.map(item => (
          <ItemCard
            key={item.id}
            item={item}
            variant="grid"
            getBadgeVariant={getBadgeVariant}
            skeletonMode={false}
          />
        ))
      )}
    </div>
  )
}
```

## Development Notes

- The skeleton implementation preserves all component props and structure
- Interaction handlers are still available in skeleton mode but should be disabled in the consuming application
- The `item` prop is still required in skeleton mode for type safety, but its values are not rendered
- All skeleton elements use `bg-muted` background with `animate-pulse` for consistent styling 
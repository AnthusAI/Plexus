# ItemComponent Consolidation Plan

## Overview

This document outlines the plan to eliminate the duplication between `ItemComponent` and `ItemCard` by consolidating all functionality into a single, more capable `ItemCard` component. The goal is to maintain all existing features while providing both read-only and editable modes for different use cases.

## Problem Statement

Currently, we have two similar components serving overlapping purposes:

1. **ItemComponent** (`dashboard/components/ui/item-component.tsx`)
   - Used in scorecards dashboard for creating/editing items
   - Supports CRUD operations with save/cancel functionality
   - Includes metadata editor and file attachments
   - Has text and description fields for editing
   - Currently used only in: `scorecards-dashboard.tsx`

2. **ItemCard** (`dashboard/components/items/ItemCard.tsx`)
   - Used throughout the application for displaying items
   - Read-only display with score results and identifiers
   - Used in: `items-dashboard.tsx`, `feedback-dashboard.tsx`, multiple stories
   - More polished UI with modern styling

This duplication creates maintenance overhead and inconsistent user experiences across different parts of the application.

## Solution Strategy

Consolidate all functionality into `ItemCard` by:
1. Adding editing capabilities from `ItemComponent`
2. Creating sub-components for metadata and file attachments
3. Supporting both read-only and edit modes
4. Maintaining PII protection by conditional field display
5. Creating comprehensive Storybook documentation

## Implementation Plan

### Phase 1: Extract Sub-Components

#### 1.1 Create MetadataEditor Component
**File:** `dashboard/components/items/MetadataEditor.tsx`

**Features:**
- Read-only mode: Display metadata as key-value pairs
- Edit mode: Add/edit/delete metadata entries
- Proper validation and error handling
- Consistent styling with existing UI patterns

**Props:**
```typescript
interface MetadataEditorProps {
  metadata?: Record<string, string> | null
  readOnly?: boolean
  onChange?: (metadata: Record<string, string>) => void
  className?: string
}
```

**Storybook Stories:** `dashboard/stories/components/items/MetadataEditor.stories.tsx`
- MetadataReadOnly: Display existing metadata
- MetadataEdit: Interactive editing mode
- MetadataEmpty: Empty state handling
- MetadataValidation: Error states and validation

#### 1.2 Create FileAttachments Component
**File:** `dashboard/components/items/FileAttachments.tsx`

**Features:**
- Read-only mode: Display list of attached files with download links
- Edit mode: Upload new files, remove existing files
- File type validation and size limits
- Progress indication during uploads
- Error handling for upload failures

**Props:**
```typescript
interface FileAttachmentsProps {
  attachedFiles?: string[]
  readOnly?: boolean
  onChange?: (files: string[]) => void
  onUpload?: (file: File) => Promise<string>
  className?: string
  maxFiles?: number
  allowedTypes?: string[]
}
```

**Storybook Stories:** `dashboard/stories/components/items/FileAttachments.stories.tsx`
- FilesReadOnly: Display existing attachments
- FilesEdit: Interactive upload/remove functionality
- FilesEmpty: Empty state with upload prompt
- FilesLoading: Upload progress states
- FilesError: Error handling scenarios

### Phase 2: Enhance ItemCard

#### 2.1 Add Editing Capabilities
**File:** `dashboard/components/items/ItemCard.tsx`

**New Props:**
```typescript
interface ItemCardProps extends React.HTMLAttributes<HTMLDivElement> {
  // Existing props...
  
  // New editing props
  readOnly?: boolean
  onSave?: (item: ItemData) => Promise<void>
  onCancel?: () => void
  showMetadata?: boolean
  showFileAttachments?: boolean
  showDescription?: boolean
  showText?: boolean
  onFileUpload?: (file: File) => Promise<string>
}
```

**Enhanced ItemData Interface:**
```typescript
export interface ItemData {
  // Existing fields...
  
  // Enhanced fields from ItemComponent
  metadata?: Record<string, string> | null
  attachedFiles?: string[]
  description?: string
  text?: string
}
```

#### 2.2 Conditional Field Display
Implement smart field display logic:

```typescript
// Only show fields if they have content AND are enabled
const shouldShowDescription = showDescription && item.description
const shouldShowText = showText && item.text && !isPIIRestricted
const shouldShowMetadata = showMetadata && item.metadata && Object.keys(item.metadata).length > 0
const shouldShowFiles = showFileAttachments && item.attachedFiles && item.attachedFiles.length > 0
```

#### 2.3 Mode-Specific Behavior

**Read-Only Mode:**
- Display all available fields as read-only
- No editing controls visible
- Optimized for browsing and viewing
- Used in: items-dashboard, feedback-dashboard

**Edit Mode:**
- All fields become editable
- Save/Cancel buttons in header
- Live validation and error display
- Used in: scorecards-dashboard for item creation/editing

### Phase 3: Update Usage Sites

#### 3.1 Scorecards Dashboard
**File:** `dashboard/components/scorecards-dashboard.tsx`

Replace `ItemComponent` usage:
```typescript
// Before
<ItemComponent
  item={selectedItem}
  variant="detail"
  onSave={handleSaveItem}
  onClose={() => setSelectedItem(null)}
/>

// After
<ItemCard
  item={selectedItem}
  variant="detail"
  readOnly={false}
  showMetadata={true}
  showFileAttachments={true}
  showDescription={true}
  showText={true}
  onSave={handleSaveItem}
  onCancel={() => setSelectedItem(null)}
  onClose={() => setSelectedItem(null)}
  onFileUpload={handleFileUpload}
  getBadgeVariant={getBadgeVariant}
/>
```

#### 3.2 Items Dashboard
**File:** `dashboard/components/items-dashboard.tsx`

Update to use read-only mode:
```typescript
<ItemCard
  item={item}
  variant="detail"
  readOnly={true}
  showMetadata={true}
  showFileAttachments={true}
  showDescription={true}
  showText={false} // PII protection
  getBadgeVariant={getBadgeVariant}
/>
```

#### 3.3 Feedback Dashboard
**File:** `dashboard/components/feedback-dashboard.tsx`

Maintain existing read-only behavior:
```typescript
<ItemCard
  item={item}
  variant="grid"
  readOnly={true}
  showMetadata={false}
  showFileAttachments={false}
  showDescription={true}
  showText={false} // PII protection
  getBadgeVariant={getBadgeVariant}
/>
```

### Phase 4: Storybook Integration

#### 4.1 Enhanced ItemCard Stories
**File:** `dashboard/stories/components/items/ItemCard.stories.tsx`

**New Stories:**
- `ReadOnlyMode`: All fields visible, no editing
- `EditMode`: Full editing capabilities
- `PIIRestricted`: Text field hidden for privacy
- `MinimalDisplay`: Only basic fields shown
- `WithMetadata`: Showcasing metadata display/editing
- `WithAttachments`: File attachment functionality
- `EmptyStates`: Handling missing data gracefully
- `ValidationStates`: Error handling and validation

#### 4.2 Story Organization
Update story titles to maintain "Content" section organization:
- `Content/ItemCard/*`
- `Content/MetadataEditor/*`  
- `Content/FileAttachments/*`

### Phase 5: Cleanup and Migration

#### 5.1 Remove ItemComponent
- Delete `dashboard/components/ui/item-component.tsx`
- Delete `dashboard/stories/ui/item-component.stories.tsx`
- Update any remaining imports

#### 5.2 Update Type Definitions
Ensure consistent `ItemData` interface across all usage sites.

#### 5.3 Documentation Updates
- Update component documentation
- Update usage examples
- Update API references

## Technical Specifications

### Data Flow

#### Read-Only Mode
```
ItemCard (read-only) 
├── IdentifierDisplay (existing)
├── Timestamp (existing)
├── MetadataEditor (read-only)
├── FileAttachments (read-only)
└── ItemScoreResults (existing)
```

#### Edit Mode
```
ItemCard (editable)
├── Header Controls (Save/Cancel)
├── Editable Fields
│   ├── ExternalId Input
│   ├── Description Textarea
│   ├── Text Textarea (if enabled)
│   ├── MetadataEditor (editable)
│   └── FileAttachments (editable)
└── Validation & Error Display
```

### State Management

```typescript
interface ItemCardState {
  isEditing: boolean
  hasChanges: boolean
  editingItem: ItemData
  isSaving: boolean
  validationErrors: Record<string, string>
}
```

### PII Protection Strategy

```typescript
const isPIIRestricted = useMemo(() => {
  // Context-specific logic to determine if PII should be hidden
  return useContext(DashboardContext)?.hidePII || false
}, [context])
```

### File Upload Integration

```typescript
interface FileUploadConfig {
  maxFileSize: number // bytes
  allowedTypes: string[] // MIME types
  uploadEndpoint: string
  onProgress?: (progress: number) => void
  onError?: (error: string) => void
}
```

## Security Considerations

### PII Protection
- Text fields automatically hidden in items dashboard
- Configurable per context via props
- No accidental PII exposure in read-only modes

### File Upload Security
- File type validation
- Size limits enforcement
- Secure upload endpoints
- Virus scanning integration (future)

### Data Validation
- Client-side validation for immediate feedback
- Server-side validation enforcement
- Proper error handling and user feedback

## Performance Considerations

### Lazy Loading
- Metadata and attachments loaded on demand
- Efficient rendering for large item lists
- Proper memoization of expensive operations

### Caching Strategy
- Cache uploaded file references
- Optimize metadata updates
- Minimize API calls during editing

## Testing Strategy

### Unit Tests
- Component behavior in read-only/edit modes
- Validation logic
- File upload functionality
- PII protection logic

### Integration Tests
- End-to-end editing workflows
- Cross-component data flow
- Error handling scenarios

### Storybook Testing
- Visual regression tests
- Interaction testing
- Accessibility compliance
- Responsive behavior

## Migration Timeline

### Week 1: Foundation
- Create MetadataEditor component with stories
- Create FileAttachments component with stories
- Set up comprehensive test coverage

### Week 2: Enhancement
- Enhance ItemCard with editing capabilities
- Implement conditional field display
- Create expanded Storybook stories

### Week 3: Integration
- Update scorecards-dashboard usage
- Update items-dashboard configuration
- Update feedback-dashboard as needed

### Week 4: Cleanup
- Remove ItemComponent files
- Complete documentation updates
- Perform final testing and validation

## Success Criteria

1. **Functionality Preservation**: All existing ItemComponent features work in enhanced ItemCard
2. **Mode Flexibility**: Seamless switching between read-only and edit modes
3. **PII Protection**: Text fields properly hidden in appropriate contexts
4. **User Experience**: Consistent, intuitive interface across all usage sites
5. **Performance**: No degradation in rendering or interaction performance
6. **Maintainability**: Single component to maintain instead of two
7. **Documentation**: Comprehensive Storybook coverage for all scenarios

## Risk Mitigation

### Breaking Changes
- Maintain backward compatibility during transition
- Gradual migration with feature flags if needed
- Comprehensive testing before ItemComponent removal

### Data Loss Prevention
- Robust save/cancel functionality
- Proper validation before data submission
- Clear user feedback for all actions

### Performance Impact
- Monitor rendering performance during migration
- Optimize heavy operations with proper memoization
- Profile and optimize file upload operations

This consolidation will result in a more maintainable, feature-rich, and consistent item management experience across the entire Plexus application. 
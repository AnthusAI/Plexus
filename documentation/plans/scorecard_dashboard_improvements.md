# Scorecard Dashboard Improvements: Example Items

## Status Legend
- ⬜ Not Started
- 🟡 In Progress
- 🟢 Completed
- 🔴 Broken/Needs Refactoring

## Overview
This document outlines planned improvements to the Scorecard dashboard, specifically for managing example items associated with a Scorecard. The goal is to enhance the functionality for adding, editing, and viewing example items within the Scorecard edit interface.

**MAJOR SCHEMA CHANGE**: The relationship between Items and Scorecards has been changed from one-to-many to many-to-many using a join table (`ItemScorecard`). This is a breaking change requiring extensive refactoring.

## Current State
🟢 **PHASE 1 COMPLETE**: All critical functionality has been successfully fixed and is working properly. Items can be created, associated with scorecards, displayed correctly, and removed as expected.

🟢 **PHASE 2.1 COMPLETE**: External ID search functionality has been successfully implemented and deployed. Users can now search for existing items by external ID and associate them with scorecards through an intuitive search interface.

### Phase 2.1 Implementation Summary
- ✅ **Enhanced User Interface**: Changed "Add by Item ID" to "Add by External ID" with improved UX
- ✅ **Smart Search**: Uses `listItemByExternalId` query for exact external ID matching
- ✅ **Auto-association**: Single results are automatically associated, multiple results show selection UI
- ✅ **Validation**: Prevents duplicate associations with clear error messages
- ✅ **Loading States**: Shows "Searching..." feedback during API calls
- ✅ **Account Scoping**: Searches only within the current account's items
- ✅ **Error Handling**: Comprehensive error handling with user-friendly messages
- ✅ **Keyboard Support**: Enter key support for quick searching
- ✅ **Cross-Account Detection**: Detects when items exist but belong to different accounts

🟡 **PHASE 2.2 NEXT**: Add edit functionality for associated items in scorecard examples list.

### Phase 2.2 Next Implementation (Ready for Development)
- ⬜ **Add Edit Button**: Add edit button next to the X (remove) button for each associated item
- ⬜ **Open Item Editor**: Edit button should open the existing ItemComponent in detail mode
- ⬜ **Integrate with Item Card**: Reuse the existing item card component that was previously built
- ⬜ **Preserve Context**: After editing, return user to scorecard view with updated item information

## CRITICAL: Schema Refactoring Status

### Schema Changes Made
- 🟢 **ItemScorecard Join Table Created**:
  ```typescript
  ItemScorecard: a.model({
    itemId: a.id().required(),
    scorecardId: a.id().required(),
    assignedAt: a.datetime(),
    assignedBy: a.string(),
    notes: a.string(),
    item: a.belongsTo('Item', 'itemId'),
    scorecard: a.belongsTo('Scorecard', 'scorecardId'),
  })
  ```

- 🟢 **Item Model Updated**:
  - 🟢 REMOVED: `scorecardId: a.string()` (direct relationship)
  - 🟢 ADDED: `scorecards: a.hasMany('ItemScorecard', 'itemId')`

- 🟢 **Scorecard Model Updated**:
  - 🟢 ADDED: `items: a.hasMany('ItemScorecard', 'scorecardId')`

## 🎯 THREE-PHASE IMPLEMENTATION PLAN

### **Phase 1: Fix Broken Functionality (COMPLETED ✅)**

#### 1.1 Update amplify-client.ts
- 🟢 **Remove outdated scorecardId references**:
  - Remove `scorecardId?: string` from `Item.create()` method
  - Remove `scorecardId?: string` from `Item.update()` method
  
- 🟢 **Add ItemScorecard operations**:
  ```typescript
  ItemScorecard: {
    create: async (data: { itemId: string; scorecardId: string; assignedBy?: string; notes?: string })
    delete: async (params: { itemId: string; scorecardId: string })
    listByScorecard: async (scorecardId: string)
    listByItem: async (itemId: string)
    get: async (params: { itemId: string; scorecardId: string })
  }
  ```

#### 1.2 Fix ScorecardComponent.tsx
- 🟢 **Fix handleRemoveItem function**:
  ```typescript
  // OLD (BROKEN):
  await amplifyClient.Item.update({ id: itemId, scorecardId: null });
  
  // NEW (WORKING):
  await amplifyClient.ItemScorecard.delete({ itemId: itemId, scorecardId: score.id });
  ```

- 🟢 **Fix handleAddByItemId function**:
  ```typescript
  // Create ItemScorecard association instead of setting scorecardId
  await amplifyClient.ItemScorecard.create({ itemId: newItemId, scorecardId: score.id });
  ```

- 🟢 **Fix examples loading logic**:
  - Update to query through ItemScorecard join table
  - Replace direct item.scorecardId filters with join table queries

#### 1.3 Test Basic Association Operations
- 🟢 Verify item creation doesn't break
- 🟢 Verify adding items by ID creates proper associations
- 🟢 Verify removing items deletes associations properly
- 🟢 Verify examples list loads correctly

### **Phase 2: Improve UX (PARTIALLY COMPLETE - 2.1 ✅, 2.2 🟡)**

#### 2.1 Enhance "Add by Item ID" to "Add by External ID"
- 🟢 **Replace raw ID input with external ID search**:
  - Add search input for external ID
  - Query items by external ID pattern matching
  - Show search results with item details
  - Allow selection from results list

#### 2.2 Add Search Interface
- 🟢 **Create reusable ItemSearchDialog component**:
  - 🟢 Search by external ID, description, or text content
  - 🟢 Show item preview with metadata
  - 🟢 Handle search loading states
  - ⬜ Support pagination for large result sets (currently limited to 10 results)
  - ⬜ Extract as reusable component (currently implemented inline)

#### 2.3 Improve Association Management
- 🟢 **Add validation and error handling**:
  - Prevent duplicate associations
  - Better error messages for failed operations
  - Loading states for all async operations
  - ⬜ Confirmation dialogs for destructive actions (not needed for current workflow)

#### 2.4 Update Item Display
- 🟡 **Show richer item information in examples list**:
  - Display external ID prominently
  - Show item description/text preview
  - Add metadata indicators
  - Show which other scorecards the item belongs to
  - ⬜ **Add edit functionality for associated items** (Phase 2.2)

### **Phase 3: Polish & Optimize (MEDIUM PRIORITY - Do Last)**

#### 3.1 Update Related Components
- 🟢 **Audit and fix other components using old relationship**:
  - Items dashboard/listing components
  - Any item creation flows
  - Item filtering/searching components
  - GraphQL queries throughout the app

#### 3.2 Add Advanced Features
- ⬜ **Bulk association operations**:
  - Select multiple items for association
  - Bulk remove associations
  - Import items from CSV with associations

#### 3.3 Performance & UX Optimizations
- ⬜ **Optimize data loading**:
  - Add caching for frequently accessed associations
  - Implement optimistic UI updates
  - Add loading skeletons for better perceived performance

#### 3.4 Documentation & Testing
- ⬜ **Update documentation**:
  - API documentation for new relationship model
  - Component usage examples
  - Migration guide for breaking changes
- ⬜ **Add comprehensive tests**:
  - Unit tests for ItemScorecard operations
  - Integration tests for association workflows
  - E2E tests for complete user flows

## 🚨 BLOCKERS RESOLVED ✅

All critical blockers have been successfully resolved:

1. ✅ **amplify-client.ts Item.create()** - Fixed: Removed non-existent `scorecardId` field
2. ✅ **ScorecardComponent.tsx handleRemoveItem()** - Fixed: Now uses ItemScorecard.delete()
3. ✅ **ScorecardComponent.tsx handleAddByItemId()** - Fixed: Creates proper associations
4. ✅ **Item creation in scorecards-dashboard.tsx** - Fixed: Removed scorecardId, added ItemScorecard creation
5. ✅ **ItemData interface** - Fixed: Removed non-existent scorecardId field
6. ✅ **Examples loading** - Fixed: Uses ItemScorecard join table queries
7. ✅ **scorecards-dashboard.tsx** - Fixed: Updated GraphQL queries to use join table
8. ✅ **items-dashboard.tsx** - Fixed: Updated all queries and removed outdated field references

## 🎯 SUCCESS CRITERIA

### Phase 1 Complete ✅
- ✅ All existing broken functionality works again
- ✅ Can add items by ID and create proper associations  
- ✅ Can remove items and delete associations properly
- ✅ Examples list loads and displays correctly
- ✅ No console errors related to missing fields
- ✅ Items can be created and automatically associated with scorecards
- ✅ Page reloads show correct state
- ✅ All critical user workflows function as expected

### Phase 2.1 Complete ✅
- ✅ Can search for items by external ID
- ✅ Search results show helpful item information
- ✅ Association creation has proper validation
- ✅ Error handling provides clear feedback
- ✅ Loading states provide good UX
- ✅ Cross-account detection and helpful error messages

### Phase 2.2 Complete When:
- ⬜ Edit button appears next to remove button for associated items
- ⬜ Edit button opens existing ItemComponent in detail mode
- ⬜ Item editing preserves scorecard context
- ⬜ Updated item information reflects in scorecard examples list

### Phase 3 Complete When:
- ✅ All related components use new relationship model
- ⬜ Performance is optimized for large datasets
- ⬜ Documentation is updated and accurate
- ⬜ Comprehensive test coverage exists

## Technical Notes

- **Breaking Change Impact**: Successfully migrated all components to use the new many-to-many relationship model
- **Performance**: Join table queries working efficiently with proper sorting and filtering
- **Data Integrity**: Proper validation implemented to prevent orphaned join table records
- **Migration**: New association model working correctly for all use cases
- **UI/UX**: Successfully handling the concept that items can belong to multiple scorecards
- **Error Handling**: Robust error handling implemented for join table operations 
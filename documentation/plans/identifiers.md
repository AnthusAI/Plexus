# Plexus Identifiers Feature Enhancement Plan

**Status Legend:**
*   ⬜ Not Started / To Do
*   🟡 In Progress
*   ✅ Completed

***Note on Testing:*** *Test files in this project are typically located directly adjacent to the source code file they are testing (e.g., `service.py` would have a corresponding `service_test.py` in the same directory).*

---

## Introduction

This document outlines the plan for enhancing the Plexus identifiers system by moving from JSON-based storage within the `Item` model to a dedicated `Identifier` model and DynamoDB table. This change will enable efficient **exact-match searching** for items based on any identifier value without requiring expensive full-text search infrastructure.

The current system stores identifiers as a JSON field (`identifiers`) in the `Item` model, which works well for display purposes but makes searching impossible. The new system will create a separate `Identifier` model with Global Secondary Indexes (GSIs) that enable **direct-hit lookups** by exact identifier value.

## Current State Analysis

### Existing Implementation

Currently, identifiers are stored as a JSON field in the `Item` model:

```json
{
  "identifiers": [
    {
      "name": "Customer ID",
      "id": "CUST-123456", 
      "url": "https://example.com/customers/123456"
    },
    {
      "name": "Order ID",
      "id": "ORD-789012"
    }
  ]
}
```

### Current Usage

- **Display**: Components like `FeedbackItemView`, `IdentifierDisplay`, and `ItemCard` parse this JSON for display
- **Search**: Currently not possible - no way to find items by identifier values
- **Storage**: Stored directly in the `Item` record, making it part of the item's core data

### External Code Dependencies

**CRITICAL**: There is code in the **Call-Criteria-Python project** (located in an adjacent folder) that creates items with identifiers. This code must be updated as part of this feature implementation.

**Known Files That Create Items with Identifiers:**
- `../Call-Criteria-Python/api.py` - FastAPI application that creates items  
- `../Call-Criteria-Python/plexus_extensions/CallCriteriaDBCache.py` - Database cache that processes items

**Identifier Construction Pattern:**
Based on the system usage, the Call Criteria project likely constructs identifiers using patterns like:
```python
identifiers = [
    {
        "name": "Report ID",
        "id": str(report_id),
        "url": f"https://call-criteria.example.com/reports/{report_id}"
    },
    {
        "name": "Content ID", 
        "id": str(content_id)
    },
    {
        "name": "Form ID",
        "id": str(form_id)
    }
]
```

**Required Updates:**
The Call Criteria code currently creates items by setting the `identifiers` field as JSON. This code must be updated to:
1. Continue setting the JSON field for backward compatibility  
2. Additionally create separate `Identifier` records for each identifier
3. Ensure both approaches remain in sync during the transition period

### Limitations

1. **No Search Capability**: Cannot find items by identifier values
2. **Inefficient Queries**: Would require scanning all items and parsing JSON
3. **No Cross-Reference**: Cannot easily find relationships between items with shared identifiers
4. **Scaling Issues**: JSON parsing becomes expensive with large datasets
5. **Limited Analytics**: Cannot analyze identifier patterns or distributions

## Proposed Solution

### Core Concept

Create a separate `Identifier` model that establishes a many-to-many relationship between items and their identifiers, with **direct-hit search capabilities** through GSIs optimized for exact matches.

### Key Benefits

1. **Fast Exact Search**: Find any item by exact identifier value using single GSI query
2. **Scalable**: DynamoDB GSIs provide consistent O(1) performance for exact matches
3. **Cost Effective**: No need for ElasticSearch or other full-text search infrastructure
4. **Flexible**: Can easily add new identifier types without schema changes
5. **Analytics Ready**: Can analyze identifier patterns and cross-references

## Data Models

### New `Identifier` Model

```typescript
Identifier: a
  .model({
    itemId: a.string().required(),
    name: a.string().required(),      // e.g., "Customer ID", "Order ID"
    value: a.string().required(),     // e.g., "CUST-123456", "ORD-789012"
    url: a.string(),                  // Optional clickable link
    accountId: a.string().required(), // For data isolation
    createdAt: a.datetime().required(),
    updatedAt: a.datetime().required(),
    
    // Relationships
    item: a.belongsTo('Item', 'itemId'),
    account: a.belongsTo('Account', 'accountId'),
  })
  .authorization((allow) => [
    allow.publicApiKey(),
    allow.authenticated()
  ])
  .secondaryIndexes((idx) => [
    idx("accountId").sortKeys(["value"]).name("byAccountAndValue"),  // PRIMARY: Direct-hit search by exact value
    idx("accountId").sortKeys(["name", "value"]).name("byAccountNameAndValue"), // Search within identifier type
    idx("itemId"),  // Get all identifiers for an item
    idx("value").name("byValue"), // Global value lookup (if cross-account search needed)
  ])
```

### Updated `Item` Model

The `Item` model will retain the `identifiers` JSON field for backward compatibility and potential performance optimization, but it will no longer be the primary source of truth.

```typescript
Item: a
  .model({
    // ... existing fields ...
    identifiers: a.json(), // DEPRECATED - keep for backward compatibility
    
    // New relationship
    itemIdentifiers: a.hasMany('Identifier', 'itemId'),
  })
```

## Step-by-Step Implementation Plan

### Step 1: Schema Migration (Deploy First - ~30 min deployment time) 🟡

**Why First**: Schema changes take ~30 minutes to deploy, so we start this first and work on other tasks while it deploys.

1. **Add Identifier Model**
   - ✅ Define `Identifier` model in `dashboard/amplify/data/resource.ts`
   - ✅ Add all required fields and relationships
   - ✅ Define GSIs optimized for exact-match searching
   - 🟡 Deploy schema changes (In Progress - User deploying)

2. **Update Item Model**
   - ✅ Add `itemIdentifiers` relationship to existing `Item` model
   - ✅ Mark `identifiers` field as deprecated (comments only)
   - 🟡 Deploy schema updates (In Progress - User deploying)

### Step 2: Create Reusable Identifier Component (While Schema Deploys) ✅

**Why Second**: Can work on this while schema deploys. Creates the UI foundation we'll need.

1. **Factor Out Existing Component**
   - ✅ Locate current identifier display in feedback analysis report block
   - ✅ Extract into reusable `IdentifierDisplay` component
   - ✅ Make component data-agnostic (accepts array of identifier objects)

2. **Component Interface Design**
   ```typescript
   interface IdentifierItem {
     name: string;      // Required: "Customer ID", "Order ID", etc.
     value: string;     // Required: "CUST-123456", "ORD-789012", etc.
     url?: string;      // Optional: clickable link
   }
   
   interface IdentifierListProps {
     identifiers: IdentifierItem[];
     className?: string;
     // ... other styling props
   }
   ```

3. **Implementation Tasks**
   - ✅ Create `dashboard/components/ui/identifier-display.tsx` (Enhanced existing)
   - ✅ Support both linked and non-linked identifiers
   - ✅ Handle empty states gracefully
   - ✅ Add proper TypeScript types

4. **Storybook Story**
   - ✅ Create `dashboard/stories/ui/IdentifierDisplay.stories.tsx` (Enhanced existing)
   - ✅ Show various states: with URLs, without URLs, empty list
   - ✅ Test different identifier types and lengths

5. **Replace Existing Usage**
   - ✅ Update feedback analysis report to use new component
   - ✅ Ensure it works with existing JSON identifier data
   - ✅ Verify no visual regressions

### Step 3: Backend API Support ⬜

**Why Third**: Schema should be deployed by now, can create backend utilities.

1. **Create API Models**
   - ⬜ Create `plexus/dashboard/api/models/identifier.py`
   - ⬜ Add CRUD methods and exact-match search utilities
   - ⬜ Update `plexus/dashboard/api/models/__init__.py`

2. **Exact-Match Search Functions**
   - ⬜ Create `plexus/utils/identifier_search.py`
   - ⬜ Implement `find_item_by_identifier(value, account_id)` - single exact match
   - ⬜ Implement `find_items_by_identifier_type(name, account_id)` - all identifiers of a type
   - ⬜ Add batch exact-match capabilities for multiple values

### Step 4: Update Call-Criteria-Python Project ⬜

**Why Fourth**: Now we have the schema and tools to create both JSON and separate records.

1. **Identify Item Creation Code**
   - ⬜ Locate item creation in `../Call-Criteria-Python/api.py`
   - ⬜ Locate item creation in `../Call-Criteria-Python/plexus_extensions/CallCriteriaDBCache.py`
   - ⬜ Document current identifier patterns (report_id, content_id, form_id)

2. **Create Dual-Write Utilities**
   - ⬜ Create helper functions that write to both JSON field AND separate Identifier records
   - ⬜ Ensure atomic operations (both succeed or both fail)
   - ⬜ Handle errors gracefully

3. **Update Item Creation Logic**
   - ⬜ Modify all item creation code to use dual-write utilities
   - ⬜ Maintain backward compatibility with JSON field
   - ⬜ Test in Call-Criteria development environment

### Step 5: Add Identifier Lookup to Frontend ⬜

**Why Fifth**: Now we can start using the new search capabilities in the UI.

1. **Update IdentifierList Component**
   - ⬜ Add support for loading identifiers from new Identifier records
   - ⬜ Keep fallback to JSON field for backward compatibility
   - ⬜ Add loading states

2. **Add Search Interface**
   - ⬜ Create exact-match search component
   - ⬜ Integrate with existing search interfaces
   - ⬜ Add "Find by Exact Identifier" functionality

### Step 6: Data Migration ⬜

**Why Sixth**: Once dual-write is working, migrate existing data.

1. **Migration Script**
   - ⬜ Create CLI command `plexus identifiers migrate`
   - ⬜ Read existing `Item` records with `identifiers` JSON
   - ⬜ Create corresponding `Identifier` records
   - ⬜ Handle duplicates and validation errors

2. **Validation Tools**
   - ⬜ Create CLI command `plexus identifiers validate`
   - ⬜ Compare JSON identifiers with Identifier table records
   - ⬜ Report inconsistencies

### Step 7: Optimize and Clean Up ⬜

**Why Last**: Once everything is working, optimize and clean up.

1. **Performance Optimization**
   - ⬜ Add caching for frequent lookups
   - ⬜ Monitor GSI performance
   - ⬜ Add performance metrics

2. **Gradual Migration from JSON Field** (Low Priority)
   - ⬜ Update components to prefer Identifier records over JSON
   - ⬜ Add deprecation warnings for JSON field usage
   - ⬜ Consider eventual removal of JSON field (future major version)

## Technical Considerations

### GSI Design Strategy

The primary GSI `byAccountAndValue` enables the core use case - **account-scoped exact-match lookups**:
```
PK: accountId
SK: value
```

This design provides **direct-hit O(1) performance within account boundaries**:

**Example Query:**
```
Query: accountId = "account123" AND value = "CUST-123456"
Result: Single identifier record → O(1) lookup, no scanning
```

**Why this is O(1) and doesn't scan:**
1. **Partition Key (accountId)**: Directly targets the specific account's data partition
2. **Sort Key (value)**: Directly targets the exact identifier value within that partition
3. **No Iteration**: DynamoDB can directly compute the exact location of the record
4. **Account Isolation**: Only searches within the specified account, never across accounts

This allows **direct-hit queries** like:
- Find identifier with exact value "CUST-123456" in account X → O(1) lookup
- Find identifier with exact value "ORD-789012" in account X → O(1) lookup
- **Never scans all items in the account**
- **Never scans all identifiers in the account**
- **Always scoped to the specific account for security and performance**

**Important**: This design does NOT support prefix searches or "starts with" queries. For those use cases, alternative approaches would be needed (separate prefix indexes, external search services, etc.).

### Account-Scoped Search Examples

**Direct Hit Examples:**
```typescript
// Find exact identifier in specific account
const result = await client.query({
  IndexName: "byAccountAndValue",
  KeyConditionExpression: "accountId = :accountId AND value = :value",
  ExpressionAttributeValues: {
    ":accountId": "account123",
    ":value": "CUST-123456"
  }
});
// Returns: Single identifier record or empty result - O(1) performance

// Batch exact matches within account
const batchResults = await Promise.all([
  findIdentifier("account123", "CUST-123456"),
  findIdentifier("account123", "ORD-789012"), 
  findIdentifier("account123", "TICKET-555")
]);
// Each query: O(1) performance, all scoped to account123
```

**What makes this efficient:**
- ✅ **Account Scoped**: `accountId` as partition key ensures data isolation
- ✅ **Direct Hit**: `value` as sort key enables exact match without scanning
- ✅ **No Cross-Talk**: Account A searches never touch Account B data
- ✅ **Predictable Performance**: Response time independent of account size
- ✅ **Cost Effective**: Single GSI query per identifier lookup

### Search Limitations & Alternatives

**What this GSI design supports:**
- ✅ Exact value matches: `value = "CUST-123456"`
- ✅ Scoped searches: `accountId = "account123" AND name = "Customer ID"`
- ✅ Batch exact matches: Multiple exact values in parallel

**What this GSI design does NOT support:**
- ❌ Prefix searches: `value starts with "CUST-"`
- ❌ Partial matches: `value contains "123"`
- ❌ Fuzzy matching: `value similar to "CUST-123456"`

**For advanced search features**, consider:
- External search service (ElasticSearch, OpenSearch)
- Application-level prefix indexing
- Client-side filtering for small datasets
- Separate GSI with reversed/normalized values for specific patterns

### Data Consistency

- **Atomic Operations**: Ensure item and identifier operations are atomic
- **Event-Driven Sync**: Use DynamoDB streams to keep JSON field in sync (during transition)
- **Validation**: Ensure identifier uniqueness constraints where appropriate

### Performance Considerations

- **GSI Capacity**: Monitor and auto-scale GSI read/write capacity
- **Query Patterns**: Optimize for exact-match patterns
- **Caching**: Implement application-level caching for frequent exact lookups
- **Batch Operations**: Support bulk exact-match operations for efficiency

### Security & Authorization

- **Account Isolation**: All queries must be scoped to account
- **API Authorization**: Proper authentication for search endpoints
- **Data Validation**: Validate identifier formats and prevent injection
- **Audit Logging**: Log identifier access and modifications

## Success Metrics

### Functional Goals
- ✅ Can find any item by exact identifier value in <100ms
- ✅ Support for millions of identifiers with consistent O(1) performance
- ✅ Zero downtime migration from JSON to table-based storage
- ✅ Backward compatibility maintained during transition

### User Experience Goals
- ✅ Instant feedback for exact identifier matches
- ✅ Clear "not found" responses for non-existent identifiers
- ✅ Bulk exact-match operations complete in seconds
- ✅ Clear feedback on identifier conflicts/duplicates

### Technical Goals
- ✅ <10ms average GSI exact-match query response time
- ✅ 99.9% search availability
- ✅ Automated failover and recovery
- ✅ Complete API documentation and examples

## Risk Assessment & Mitigation

### High Risks
1. **Data Loss During Migration**
   - *Mitigation*: Comprehensive backup, staged rollout, validation tools
2. **Performance Degradation**
   - *Mitigation*: Load testing, gradual migration, rollback plans
3. **Breaking Changes**
   - *Mitigation*: Backward compatibility, feature flags, versioned APIs

### Medium Risks
1. **GSI Throttling**
   - *Mitigation*: Capacity monitoring, auto-scaling, request batching
2. **Complex Migration**
   - *Mitigation*: Detailed testing, staged deployment, automation
3. **Limited Search Capabilities**
   - *Mitigation*: Clear documentation of limitations, alternative solutions for advanced search

## Future Enhancements

### Advanced Search Features (Separate Implementation)
- External search service integration for prefix/fuzzy matching
- Application-level prefix indexing for common patterns
- Identifier relationship mapping
- Cross-account identifier resolution (with permissions)

### Analytics & Intelligence
- Identifier quality scoring
- Automatic identifier extraction from text
- Duplicate detection and merging suggestions
- Identifier usage patterns and recommendations

### Integration Opportunities
- External system identifier synchronization
- API-driven identifier management
- Webhook notifications for identifier changes
- Third-party search service integration for advanced queries 
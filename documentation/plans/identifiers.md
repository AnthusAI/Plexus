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

## Implementation Plan

### Project Structure Considerations

**Multi-Project Coordination Required:**
This feature spans two separate repositories that must be updated in coordination:

1. **Primary Project**: `Plexus` (current project)
   - Contains the main Identifier model and search infrastructure
   - Located at: `/Users/ryan.porter/Projects/Plexus` (example path)

2. **External Project**: `Call-Criteria-Python` 
   - Contains item creation code that sets identifiers
   - Located at: `/Users/ryan.porter/Projects/Call-Criteria-Python` (adjacent folder)
   - **Files requiring updates**:
     - `api.py` - FastAPI application 
     - `plexus_extensions/CallCriteriaDBCache.py` - Database cache processing
     - Any utility functions for item creation

**Development Notes:**
- Both projects exist in the same parent directory but are separate repositories
- The Call-Criteria-Python project imports and uses the Plexus dashboard client
- Changes must be coordinated to avoid breaking existing functionality
- Consider using feature flags during transition period

### Phase 1: Schema Migration ⬜

1. **Add Identifier Model**
   - ⬜ Define `Identifier` model in `dashboard/amplify/data/resource.ts`
   - ⬜ Add all required fields and relationships
   - ⬜ Define GSIs optimized for exact-match searching
   - ⬜ Deploy schema changes

2. **Update Item Model**
   - ⬜ Add `itemIdentifiers` relationship to existing `Item` model
   - ⬜ Mark `identifiers` field as deprecated (comments only)
   - ⬜ Deploy schema updates

3. **Create API Models**
   - ⬜ Create `plexus/dashboard/api/models/identifier.py`
   - ⬜ Add CRUD methods and exact-match search utilities
   - ⬜ Update `plexus/dashboard/api/models/__init__.py`

### Phase 2: Data Migration ⬜

1. **Migration Script**
   - ⬜ Create CLI command `plexus identifiers migrate`
   - ⬜ Read existing `Item` records with `identifiers` JSON
   - ⬜ Parse JSON and create corresponding `Identifier` records
   - ⬜ Handle duplicates and validation errors gracefully
   - ⬜ Provide progress reporting and rollback capability

2. **Validation Tools**
   - ⬜ Create CLI command `plexus identifiers validate`
   - ⬜ Compare JSON identifiers with Identifier table records
   - ⬜ Report inconsistencies and missing data
   - ⬜ Provide repair suggestions

### Phase 3: Backend Implementation ⬜

1. **Exact-Match Search Functions**
   - ⬜ Create `plexus/utils/identifier_search.py`
   - ⬜ Implement `find_item_by_identifier(value, account_id)` - single exact match
   - ⬜ Implement `find_items_by_identifier_type(name, account_id)` - all identifiers of a type
   - ⬜ Add batch exact-match capabilities for multiple values

2. **Item Management Updates**
   - ⬜ Update item creation to automatically create `Identifier` records
   - ⬜ Update item updates to sync identifier changes
   - ⬜ Ensure atomic operations (item + identifiers)

3. **API Enhancements**
   - ⬜ Add exact-match search endpoints to GraphQL schema
   - ⬜ Add identifier management mutations
   - ⬜ Implement proper authorization and validation

### Phase 4: External Code Dependencies ⬜

**CRITICAL**: Update Call-Criteria-Python project code to use the new Identifier model.

1. **Identify and Update Item Creation Code**
   - ⬜ **Locate item creation utilities**: Search for centralized functions that create items with identifiers in:
     - `../Call-Criteria-Python/api.py`
     - `../Call-Criteria-Python/plexus_extensions/CallCriteriaDBCache.py`
     - Any utility modules that construct the identifiers JSON structure
   - ⬜ **Analyze current implementation**: Document how identifiers are currently constructed (report_id, content_id, form_id patterns)
   - ⬜ **Create transition utilities**: Build helper functions to create both JSON and separate Identifier records

2. **Update Item Creation Logic**
   - ⬜ **Modify existing item creation**: Update all locations where items are created to:
     - Continue setting the `identifiers` JSON field (backward compatibility)
     - Additionally call new identifier creation utilities
     - Handle errors gracefully if identifier creation fails
   - ⬜ **Create identifier management utilities**: Add functions like:
     ```python
     def create_item_with_identifiers(client, item_data, identifiers_list):
         # Create item with JSON identifiers (existing)
         item = create_item(client, item_data, identifiers=identifiers_list)
         
         # Create separate Identifier records (new)
         for identifier in identifiers_list:
             create_identifier_record(client, item.id, identifier)
         
         return item
     ```

3. **Testing and Validation**
   - ⬜ **Test in Call Criteria development environment**: Ensure updated code works with existing workflows
   - ⬜ **Verify data consistency**: Confirm both JSON and Identifier records are created correctly
   - ⬜ **Performance testing**: Ensure additional Identifier record creation doesn't impact performance
   - ⬜ **Rollback plan**: Document how to revert changes if issues arise

4. **Deployment Coordination**
   - ⬜ **Coordinate deployment**: Both Plexus and Call-Criteria-Python projects must be updated together
   - ⬜ **Monitor transition**: Watch for any issues during the transition period
   - ⬜ **Data validation**: Run validation tools to ensure consistency between JSON and Identifier table

### Phase 5: Frontend Updates ⬜

1. **Display Components**
   - ⬜ Update `IdentifierDisplay` component to use new model
   - ⬜ Keep backward compatibility with JSON format
   - ⬜ Add loading states for identifier fetching
   - ⬜ Update `FeedbackItemView` and other components

2. **Exact-Match Search Interface**
   - ⬜ Create `IdentifierExactSearch` component for direct lookups
   - ⬜ Add search input with exact-match feedback
   - ⬜ Integrate with existing search interfaces
   - ⬜ Add filters by identifier type for scoped searches

3. **Management Interface**
   - ⬜ Add identifier management to item detail views
   - ⬜ Allow adding/editing/removing identifiers
   - ⬜ Provide bulk identifier operations
   - ⬜ Add identifier analytics/reporting

### Phase 6: Search Integration ⬜

1. **Global Search**
   - ⬜ Integrate exact-match identifier search into main search functionality
   - ⬜ Add identifier results to search suggestions
   - ⬜ Implement search result ranking for exact matches

2. **Dashboard Integration**
   - ⬜ Add exact-match identifier search to items dashboard
   - ⬜ Update filter interfaces to include identifier filters
   - ⬜ Add "Find by Exact Identifier" quick actions

3. **API Search**
   - ⬜ Add REST/GraphQL exact-match search endpoints
   - ⬜ Support batch identifier lookups
   - ⬜ Add search analytics and logging

### Phase 7: Performance & Analytics ⬜

1. **Performance Optimization**
   - ⬜ Add caching for frequent exact-match identifier lookups
   - ⬜ Optimize GSI query patterns for direct hits
   - ⬜ Monitor and tune DynamoDB performance
   - ⬜ Add performance metrics and alerting

2. **Analytics Features**
   - ⬜ Add identifier usage analytics
   - ⬜ Detect duplicate identifiers (exact matches)
   - ⬜ Provide identifier quality reports
   - ⬜ Add identifier pattern recognition for data quality

### Phase 8: Cleanup & Deprecation ⬜

1. **Backward Compatibility**
   - ⬜ Ensure all components work with both old and new systems
   - ⬜ Add migration warnings for deprecated JSON usage
   - ⬜ Provide clear upgrade paths

2. **JSON Field Deprecation**
   - ⬜ Mark `identifiers` JSON field as deprecated in schema
   - ⬜ Remove write operations to JSON field
   - ⬜ Plan eventual removal of JSON field (future major version)

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
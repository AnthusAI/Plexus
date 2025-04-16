# Public Evaluation Route

## Overview
This document outlines the implementation plan for adding a public evaluation route at `/evaluations/[ID]`. This route will allow direct access to evaluation results via a public URL, with the evaluation ID as the identifier.

## Current Status
✓ Initial Analysis Complete:
- Confirmed all necessary components exist
- Verified no schema changes needed
- Confirmed public access already configured in schema
- Identified all required data transformations

✓ Route Implementation Complete:
- Created route files:
  - `app/evaluations/[id]/page.tsx` - Main page component
  - `app/evaluations/[id]/layout.tsx` - Layout component
- Implemented data fetching using Amplify client
- Implemented UI with:
  - Full-width container layout
  - EvaluationTask in detail mode
  - Loading spinner
  - Error states
  - Footer integration

✓ Unit Tests Complete:
- Created test suite in `app/evaluations/[id]/__tests__/page.test.tsx`
- Implemented tests for:
  - Route component rendering
  - Data fetching
  - Error handling
  - Loading states
  - Component mocking

✓ Integration Tests Complete:
- Created Cypress test suite in `cypress/e2e/public-evaluation.cy.ts`
- Implemented end-to-end tests for:
  - Successful evaluation loading
  - Error handling (404, 500)
  - Responsive design across devices
  - API integration
  - Component interactions

## Implementation Requirements

### Core Components (All Existing)
- `EvaluationTask` component for displaying evaluation details
- Public API key authorization in Amplify schema
- Footer component from landing pages
- Data transformation utilities
- Evaluation model with all necessary relationships

### Route Structure
- Path: `/evaluations/[ID]`
- Type: Public route (no authentication required)
- Layout: Full-width with footer

## Implementation Plan

### Phase 1: Route Implementation ✓
1. Create route files: ✓
   - `app/evaluations/[id]/page.tsx` - Main page component
   - `app/evaluations/[id]/layout.tsx` - Layout component

2. Implement data fetching: ✓
   - Use Amplify's generated client
   - Fetch evaluation by ID
   - Transform data using existing utilities
   - Handle loading and error states

3. Implement UI: ✓
   - Full-width container layout
   - EvaluationTask in detail mode
   - Loading spinner
   - Error states
   - Footer integration

### Phase 2: Testing
1. Unit Tests: ✓
   - Route component rendering
   - Data fetching
   - Error handling
   - Loading states

2. Integration Tests: ✓
   - End-to-end route testing
   - Public access verification
   - Data transformation validation
   - Responsive design testing

3. Manual Testing:
   - Various evaluation states
   - Different screen sizes
   - Error scenarios
   - Loading behavior

## Technical Details

### Data Flow
1. Client requests `/evaluations/[ID]`
2. Page component fetches evaluation using public API client
3. Data is transformed using existing utilities
4. Rendered using `EvaluationTask` component

### Error Handling
- Not Found (404)
- Fetch Failures
- Data Transformation Errors
- Invalid Evaluation States

## Notes
Implementation was straightforward as all necessary components and infrastructure existed:
- No schema changes required
- Public access already configured
- All UI components available
- Data transformation utilities in place

## Next Steps
1. ✓ Create route files
2. ✓ Implement page component
3. ✓ Add unit tests
4. ✓ Add integration tests
5. Manual testing and verification

## Future Considerations
- Analytics tracking for public views
- Rate limiting if needed
- Caching strategy if high traffic expected
- SEO optimization if needed 

## Enhanced Secure Sharing Implementation

### Overview
To address security audit requirements and provide more control over shared resources, we will implement a secure sharing mechanism using a Lambda proxy with IAM authorization to AppSync. This approach will replace the direct public access to resources with a token-based system that supports expiration and revocation.

The primary goals of this implementation are:
1. Create a **simple lookup table for share URLs** that can be managed, expired, or deleted
2. Support sharing **multiple types of resources** (evaluations, reports, datasets, etc.)
3. Provide **fine-grained control** over what nested information is shared
4. Enable **different view variants** of the same resource for different audiences

### ShareLink Data Model
We'll keep the schema simple, similar to a URL shortener with a few additional fields:

```graphql
type ShareLink @model @auth(rules: [
  { allow: private },
  { allow: public, operations: [read], provider: iam }
]) {
  id: ID!
  token: String! @index
  resourceType: String!  # "Evaluation", "Report", "Dataset", etc.
  resourceId: ID!
  createdBy: ID!
  accountId: ID!
  expiresAt: AWSDateTime
  viewOptions: AWSJSON  # JSON field for all configuration options
  lastAccessedAt: AWSDateTime
  accessCount: Int
  isRevoked: Boolean
}
```

The `viewOptions` field will be a flexible JSON object that specifies all configuration options in one place, rather than as URL parameters:
- Which nested resources to include/exclude
- Display variants (detailed vs. summary)
- Specific fields to hide (e.g., cost metrics, PII)
- Custom labels or descriptions for the shared view

Example viewOptions for an Evaluation:
```json
{
  "includeScoreResults": false,  // Don't show individual score results with PII
  "includeCostMetrics": false,   // Hide cost information
  "displayMode": "summary",      // Show summary view instead of detailed
  "includeConfusionMatrix": true,  // Show confusion matrix
  "customTitle": "Project X Evaluation Results",
  "visibleMetrics": ["accuracy", "precision", "recall"]  // Only show these metrics
}
```

### Lambda Proxy Implementation
The Lambda function will:
1. Receive the share token from the public route
2. Validate the token against the ShareLink table
3. Check expiration and revocation status
4. If valid, use IAM credentials to query the appropriate resource
5. Apply view options to filter sensitive data and nested resources
6. Return the processed data to the client
7. Log access details to CloudWatch for analytics purposes

```typescript
// Lambda handler pseudocode
export const handler = async (event) => {
  try {
    const { token } = event.queryStringParameters;
    
    // Validate token
    const shareLink = await getShareLink(token);
    if (!shareLink || shareLink.isRevoked) {
      return { statusCode: 403, body: JSON.stringify({ error: 'Invalid or revoked link' }) };
    }
    
    // Check expiration
    if (shareLink.expiresAt && new Date(shareLink.expiresAt) < new Date()) {
      return { statusCode: 403, body: JSON.stringify({ error: 'Link expired' }) };
    }
    
    // Update access metrics
    await updateShareLinkAccess(token);
    
    // Determine query based on resource type and view options
    const { query, variables } = buildQueryFromOptions(
      shareLink.resourceType, 
      shareLink.resourceId,
      shareLink.viewOptions
    );
    
    // Execute AppSync query with IAM authorization
    const result = await appSyncClient.query({
      query,
      variables,
      authMode: 'AWS_IAM'
    });
    
    // Apply view options to filter data
    const filteredData = applyViewOptions(result.data, shareLink.viewOptions);
    
    // Log access for analytics via CloudWatch
    console.log(JSON.stringify({
      event: 'share_link_access',
      token: token,
      resourceType: shareLink.resourceType,
      resourceId: shareLink.resourceId,
      timestamp: new Date().toISOString(),
      viewOptions: shareLink.viewOptions
    }));
    
    return {
      statusCode: 200,
      body: JSON.stringify({
        data: filteredData,
        resourceType: shareLink.resourceType,
        viewOptions: shareLink.viewOptions
      })
    };
  } catch (error) {
    console.error('Error processing share request:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' })
    };
  }
};
```

### Analytics with CloudWatch
Instead of building a complex analytics system upfront, we'll:
1. Log detailed JSON objects to CloudWatch for each share link access
2. Use CloudWatch Log Insights to query and analyze usage patterns
3. Create dashboards for common metrics as needed
4. Scale analytics capabilities based on actual usage patterns

Example CloudWatch Log Insights query for share link usage:
```
filter @message like "share_link_access"
| parse @message "resourceType\":\"*\"" as resourceType
| stats count(*) as accessCount by resourceType, resourceId
| sort accessCount desc
```

### Share Route Implementation
The share route will use clean URLs without query parameters, with all configuration stored in the ShareLink record:

```typescript
// app/share/[token]/page.tsx
export default function SharePage({ params }) {
  const { token } = params;
  const [resourceData, setResourceData] = useState(null);
  const [resourceType, setResourceType] = useState(null);
  const [viewOptions, setViewOptions] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    async function fetchSharedResource() {
      try {
        // Call the Lambda function via API Gateway
        const response = await fetch(`/api/share/${token}`);
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.error || 'Failed to load shared resource');
        }
        
        const result = await response.json();
        setResourceData(result.data);
        setResourceType(result.resourceType);
        setViewOptions(result.viewOptions);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    
    fetchSharedResource();
  }, [token]);
  
  // Render appropriate component based on resource type
  const renderResource = () => {
    if (!resourceData || !resourceType) return null;
    
    switch(resourceType) {
      case 'Evaluation':
        return <EvaluationView data={resourceData} viewOptions={viewOptions} />;
      case 'Report':
        return <ReportView data={resourceData} viewOptions={viewOptions} />;
      case 'Dataset':
        return <DatasetView data={resourceData} viewOptions={viewOptions} />;
      default:
        return <div>Unknown resource type: {resourceType}</div>;
    }
  };
  
  return (
    <Layout>
      <div className="min-h-screen bg-background">
        <div className="w-[calc(100vw-2rem)] max-w-7xl mx-auto py-8">
          {loading ? (
            <LoadingSpinner />
          ) : error ? (
            <ErrorDisplay message={error} />
          ) : (
            renderResource()
          )}
        </div>
      </div>
    </Layout>
  );
}
```

### Share Management UI
We will add a management interface for users to:
1. Create share links with custom expiration dates
2. Configure exactly what information is shared via view options
3. View all active share links across resource types
4. Revoke links before expiration
5. View basic access statistics

Example share creation flow:
```typescript
// Example share creation function
async function createShareLink(resourceType, resourceId, options) {
  const defaultOptions = getDefaultOptionsForResourceType(resourceType);
  const viewOptions = { ...defaultOptions, ...options };
  
  // Generate a random token
  const token = generateSecureToken();
  
  // Calculate expiration (default: 7 days from now)
  const expiresAt = options.expiresAt || 
    new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString();
  
  // Create the share link
  const shareLink = await API.graphql({
    query: createShareLinkMutation,
    variables: {
      input: {
        token,
        resourceType,
        resourceId,
        expiresAt,
        viewOptions: JSON.stringify(viewOptions),
        isRevoked: false,
        accessCount: 0
      }
    }
  });
  
  return `${window.location.origin}/share/${token}`;
}
```

### Security Benefits
1. **No Direct Resource Access**: Resources are never directly exposed
2. **No URL Parameters**: All configuration stored in the database, not in URL
3. **Granular Content Control**: Precise control over what nested data is shared
4. **Time-Limited Access**: All shares have configurable expiration
5. **Revocation Control**: Links can be immediately revoked
6. **Access Auditing**: Complete tracking of all access attempts via CloudWatch
7. **IAM Authorization**: Secure delegation pattern for AppSync access
8. **PII Protection**: Ability to filter out personally identifying information

### Implementation Phases

#### Phase 1: Infrastructure Setup
1. ✓ Add ShareLink model to schema
2. Configure IAM authorization for AppSync
3. Create Lambda proxy function with IAM role
4. Set up API Gateway endpoint for Lambda
5. Configure CloudWatch logging for analytics

#### Phase 2: Share Management
1. Implement share creation UI with view option configuration
2. Build share management dashboard
3. Add expiration and revocation functionality

#### Phase 3: Resource-Specific View Options
1. Implement view option handlers for each resource type
2. Create UI components for different view variants
3. Add presets for common sharing scenarios

#### Phase 4: Migration and Analytics
1. Implement both systems in parallel
2. Add migration path for existing public URLs
3. Create CloudWatch Log Insights queries for common analytics needs
4. Gradually phase out direct public access

### Advantages Over Direct Public Access
1. **Simple Schema**: Straightforward lookup table similar to a URL shortener
2. **Flexible Resource Types**: Support for sharing any resource type
3. **Content Control**: Precise control over what information is shared
4. **Security**: No direct exposure of resource IDs or data
5. **Auditability**: Complete tracking of all share access via CloudWatch
6. **Compliance**: Meets security audit requirements for sensitive data
7. **Clean URLs**: No query parameters in shared URLs

This enhanced implementation provides a robust, secure sharing mechanism that will satisfy security audit requirements while maintaining simplicity in the database schema. The flexible `viewOptions` JSON field allows for extensive configuration without complicating the database structure, and CloudWatch logging provides a scalable approach to analytics that can be expanded as needed.

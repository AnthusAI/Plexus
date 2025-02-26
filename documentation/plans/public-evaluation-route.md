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
1. Create a **centralized table of share URLs** that can be managed, expired, or deleted
2. Support sharing **multiple types of resources** (evaluations, reports, datasets, etc.)
3. Provide **fine-grained control** over what nested information is shared
4. Enable **different view variants** of the same resource for different audiences

### Architecture
1. **ShareLink Table**: Central repository for all share tokens with expiration and access controls
2. **Lambda Proxy**: Authorized via IAM to make AppSync queries with content filtering
3. **Share Route**: Public endpoint that renders appropriate UI based on resource type and view options

### ShareLink Data Model
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
  viewOptions: AWSJSON  # Controls what nested data is included and display variants
  lastAccessedAt: AWSDateTime
  accessCount: Int
  isRevoked: Boolean
  name: String  # Optional friendly name for the share
  description: String  # Optional description of what is being shared
}
```

The `viewOptions` field will contain a JSON object that specifies:
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
    
    return {
      statusCode: 200,
      body: JSON.stringify({
        data: filteredData,
        resourceType: shareLink.resourceType,
        viewOptions: shareLink.viewOptions,
        name: shareLink.name,
        description: shareLink.description
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

// Helper function to build appropriate GraphQL query with field selection
function buildQueryFromOptions(resourceType, resourceId, viewOptions) {
  switch(resourceType) {
    case 'Evaluation':
      return buildEvaluationQuery(resourceId, viewOptions);
    case 'Report':
      return buildReportQuery(resourceId, viewOptions);
    case 'Dataset':
      return buildDatasetQuery(resourceId, viewOptions);
    default:
      throw new Error(`Unsupported resource type: ${resourceType}`);
  }
}

// Example of building a query with selective field inclusion
function buildEvaluationQuery(id, viewOptions) {
  // Base fields always included
  let fields = `
    id
    type
    parameters
    accuracy
    status
    createdAt
    updatedAt
  `;
  
  // Conditionally include nested resources based on viewOptions
  if (viewOptions.includeScoreResults) {
    fields += `
      scoreResults {
        items {
          id
          value
          confidence
          ${viewOptions.includeScoreResultExplanations ? 'explanation' : ''}
          ${viewOptions.includeScoreResultMetadata ? 'metadata' : ''}
          itemId
          createdAt
        }
      }
    `;
  }
  
  // Conditionally include cost metrics
  if (viewOptions.includeCostMetrics) {
    fields += `
      cost
      inferences
    `;
  }
  
  // Conditionally include confusion matrix
  if (viewOptions.includeConfusionMatrix) {
    fields += `
      confusionMatrix
      datasetClassDistribution
      predictedClassDistribution
    `;
  }
  
  return {
    query: `query GetEvaluation($id: ID!) {
      getEvaluation(id: $id) {
        ${fields}
      }
    }`,
    variables: { id }
  };
}
```

### IAM Authorization Setup
```typescript
// amplify/data/resource.ts
const api = a.graphqlApi({
  name: 'PlexusAPI',
  schema: schema,
  authorizationModes: {
    defaultAuthorizationMode: 'AMAZON_COGNITO_USER_POOLS',
    apiKeyConfig: {
      description: 'API key for public access',
      expiresAfter: '365 days'
    },
    iamConfig: {
      enableIamAuthorizationMode: true
    }
  }
});

// Lambda IAM role configuration
const shareLambdaRole = new iam.Role(this, 'ShareLambdaRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
});

// Grant AppSync access to the Lambda role for all resource types
api.resources.graphqlApi.grantQuery(shareLambdaRole, [
  'getEvaluation',
  'getReport',
  'getDataset',
  'getShareLink'
]);
```

### Share Route Implementation
The share route will dynamically render the appropriate component based on the resource type:

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
        const response = await fetch(`/api/share?token=${token}`);
        
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
We will add a comprehensive management interface for users to:
1. Create share links with custom expiration dates
2. Configure exactly what information is shared via view options
3. View all active share links across resource types
4. Revoke links before expiration
5. Track access statistics and usage patterns

The UI will include:
- A "Share" button on resource detail pages
- A modal for configuring share options with presets for common sharing scenarios
- A dedicated "Shared Links" section in the user settings
- Detailed analytics on share link usage

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
        name: options.name || `Shared ${resourceType}`,
        description: options.description || '',
        isRevoked: false,
        accessCount: 0
      }
    }
  });
  
  return `${window.location.origin}/share/${token}`;
}
```

### Content Filtering and View Variants
The system will support multiple view variants for each resource type:

#### Evaluation Sharing Options:
- **Full Detail**: Complete evaluation with all metrics and results
- **Summary**: High-level metrics without individual results
- **Client View**: Customized view with client-friendly terminology
- **Technical View**: Detailed view with technical metrics for internal teams

#### Report Sharing Options:
- **Executive Summary**: Key findings without technical details
- **Full Report**: Complete report with all sections
- **Custom Sections**: Only specific sections of the report

#### Dataset Sharing Options:
- **Metadata Only**: Dataset description without actual data
- **Sample Data**: Dataset with limited sample records
- **Full Dataset**: Complete dataset access

### Security Benefits
1. **No Direct Resource Access**: Resources are never directly exposed
2. **Granular Content Control**: Precise control over what nested data is shared
3. **Time-Limited Access**: All shares have configurable expiration
4. **Revocation Control**: Links can be immediately revoked
5. **Access Auditing**: Complete tracking of all access attempts
6. **IAM Authorization**: Secure delegation pattern for AppSync access
7. **PII Protection**: Ability to filter out personally identifying information

### Implementation Phases

#### Phase 1: Infrastructure Setup
1. Add ShareLink model to schema
2. Configure IAM authorization for AppSync
3. Create Lambda proxy function with IAM role
4. Set up API Gateway endpoint for Lambda

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
3. Build analytics dashboard for share usage
4. Gradually phase out direct public access

### Advantages Over Direct Public Access
1. **Centralized Management**: One table to manage all shared content
2. **Flexible Resource Types**: Support for sharing any resource type
3. **Content Control**: Precise control over what information is shared
4. **Security**: No direct exposure of resource IDs or data
5. **Auditability**: Complete tracking of all share access
6. **Compliance**: Meets security audit requirements for sensitive data

This enhanced implementation provides a robust, secure sharing mechanism that will satisfy security audit requirements while maintaining flexibility for future enhancements. The centralized ShareLink table allows for consistent management of all shared content, while the view options system provides fine-grained control over exactly what information is exposed to different audiences.

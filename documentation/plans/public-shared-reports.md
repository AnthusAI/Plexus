# Public Shared Reports Implementation Plan

## Current Issue

When attempting to access shared report URLs like `https://capacity-plexus.anth.us/reports/194b7982be2509b69c17ac42616d4215` or any URL starting with `/evaluations/`, unauthenticated users are being redirected to the login page. While we've successfully made these routes publicly accessible in the client-side routing, there's still an issue with GraphQL API access for unauthenticated users.

Error seen in the console:
```
Error listing from model: Object error: NoValidAuthTokens: No federated jwt
```

## Affected Files

1. `dashboard/app/client-layout.tsx` - Contains the public routes logic
2. `dashboard/amplify/data/resource.ts` - Contains the data model definitions and authorization rules
3. `dashboard/app/reports/[id]/page.tsx` - Contains the report service that fetches data

## Current Implementation

### Authorization Rules

The relevant models in `dashboard/amplify/data/resource.ts` have these authorization rules:

```typescript
Report: a
    .model({
        // ... fields ...
    })
    .authorization((allow: AuthorizationCallback) => [
        allow.publicApiKey(),
        allow.authenticated(),
        allow.public().to(['read']) // Only accessible if the full UUID is known.
    ])

ReportBlock: a
    .model({
        // ... fields ...
    })
    .authorization((allow: AuthorizationCallback) => [
        allow.publicApiKey(),
        allow.authenticated(),
        allow.public().to(['read'])
    ])
```

### Authentication in ReportService

In `dashboard/app/reports/[id]/page.tsx`, the `ReportService` class determines auth mode with:

```typescript
// Determine auth mode based on user's session
let authMode: 'userPool' | 'identityPool' = 'identityPool'; // Default to guest access
try {
  const session = await fetchAuthSession();
  if (session.tokens?.idToken) {
    authMode = 'userPool';
  } else {
    console.log('Using guest access mode');
  }
} catch (error) {
  console.log('Error checking auth session, falling back to guest access');
}
```

Then uses this auth mode for GraphQL queries:

```typescript
const response = await this.client.graphql({
  query: `query GetResourceByShareToken($token: String!) { ... }`,
  variables: { token },
  authMode
});
```

## Problems Identified

1. **Auth Mode Mismatch**: The code uses `identityPool` auth mode for guest access, but this requires Cognito identity pool federation token, which isn't available
2. **Public Access Configuration**: Even though models have `allow.public().to(['read'])`, the client isn't properly configured to use public access mode
3. **Missing Related Models**: Some related models that might be accessed during the report fetch might not have public access

## Required Changes

### 1. Update ReportService Authentication Logic

In `dashboard/app/reports/[id]/page.tsx`, modify the auth mode determination:

```typescript
// Determine auth mode based on user's session
let authMode: 'userPool' | 'apiKey' | undefined = undefined; // Default to public access (undefined)
try {
  const session = await fetchAuthSession();
  if (session.tokens?.idToken) {
    authMode = 'userPool';
  } else {
    // For unauthenticated access, use API key instead of identity pool
    authMode = 'apiKey';
    console.log('Using API key access mode');
  }
} catch (error) {
  console.log('Error checking auth session, falling back to API key access');
  authMode = 'apiKey';
}
```

### 2. Ensure All Related Models Have Public Access

In `dashboard/amplify/data/resource.ts`, ensure these models have consistent authorization rules:

- `Report`
- `ReportBlock`
- `ReportConfiguration`
- Custom resolver `getResourceByShareToken`

Add or verify public access:

```typescript
.authorization((allow: AuthorizationCallback) => [
    allow.publicApiKey(), // For API key access
    allow.authenticated(), // For authenticated users
    allow.public().to(['read']) // For completely public access
])
```

### 3. API Client Configuration

Ensure the Amplify client configuration includes API key settings. This is likely already set up in the data resource configuration:

```typescript
export const data = defineData({
    schema,
    authorizationModes: {
        defaultAuthorizationMode: 'userPool',
        apiKeyAuthorizationMode: {
            expiresInDays: 0  // Never expires
        }
    }
});
```

### 4. Test All Related GraphQL Queries

Test each of these GraphQL queries with an unauthenticated user:

1. `getResourceByShareToken` - Used to resolve the share token to a resource ID
2. `getReport` - Used to fetch the full report data
3. `listReportBlocks` - Used to fetch report blocks if needed

## Testing Plan

1. Clear browser cookies/storage to ensure you're testing as a completely unauthenticated user
2. Attempt to access a shared report URL (`/reports/{id}`)
3. Check browser console for GraphQL errors
4. Verify that the report loads correctly without authentication
5. Repeat for evaluation URLs (`/evaluations/{id}`)

## Deployment Considerations

After local testing is successful:

1. Deploy changes to a development environment
2. Test with real share tokens from the production system
3. Monitor for any unexpected authentication or authorization errors
4. Ensure the API key is properly configured in the deployed environment

## Security Considerations

- Reports are only accessible via full UUID, making them effectively private unless the URL is shared
- Consider adding additional access logging for unauthenticated access to reports
- Review any sensitive data that might be exposed in public reports 
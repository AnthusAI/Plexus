import type { Schema } from '../resource';
import { generateClient } from 'aws-amplify/api';
import { type GraphQLResult } from '@aws-amplify/api-graphql';

// Define the handler function with the correct type from Schema
export const handler: Schema["getResourceByShareToken"]["functionHandler"] = async (event) => {
  try {
    const { token } = event.arguments;
    
    if (!token) {
      throw new Error('Token is required');
    }
    
    // Create a client to interact with the API with IAM authentication
    const client = generateClient({
      authMode: 'iam'
    });
    
    // Get ShareLink by token
    const shareLinkResponse = await client.graphql({
      query: `
        query GetShareLinkByToken($token: String!) {
          listShareLinks(filter: { token: { eq: $token } }) {
            items {
              id
              token
              resourceType
              resourceId
              expiresAt
              viewOptions
              lastAccessedAt
              accessCount
              isRevoked
            }
          }
        }
      `,
      variables: { token }
    }) as GraphQLResult<any>;
    
    // Check for errors
    if (shareLinkResponse.errors && shareLinkResponse.errors.length > 0) {
      console.error('GraphQL errors:', shareLinkResponse.errors);
      throw new Error('Error fetching share link');
    }
    
    // Get the ShareLink from the response
    const shareLinks = shareLinkResponse.data?.listShareLinks?.items || [];
    
    if (shareLinks.length === 0) {
      throw new Error('Share link not found');
    }
    
    const shareLink = shareLinks[0];
    
    // Check if the link is revoked
    if (shareLink.isRevoked) {
      throw new Error('Share link has been revoked');
    }
    
    // Check if the link is expired
    if (shareLink.expiresAt && new Date(shareLink.expiresAt) < new Date()) {
      throw new Error('Share link has expired');
    }
    
    // Update access metrics
    const currentCount = shareLink.accessCount || 0;
    await client.graphql({
      query: `
        mutation UpdateShareLinkAccess($id: ID!, $lastAccessedAt: AWSDateTime!, $accessCount: Int!) {
          updateShareLink(input: {
            id: $id
            lastAccessedAt: $lastAccessedAt
            accessCount: $accessCount
          }) {
            id
            accessCount
            lastAccessedAt
          }
        }
      `,
      variables: {
        id: shareLink.id,
        lastAccessedAt: new Date().toISOString(),
        accessCount: currentCount + 1
      }
    });
    
    // Fetch the actual resource based on resourceType
    let resourceQuery;
    let resourceVariables;
    
    switch (shareLink.resourceType) {
      case 'Evaluation':
        resourceQuery = `
          query GetEvaluation($id: ID!) {
            getEvaluation(id: $id) {
              id
              type
              parameters
              metrics
              metricsExplanation
              inferences
              accuracy
              cost
              createdAt
              updatedAt
              status
              startedAt
              elapsedSeconds
              estimatedRemainingSeconds
              totalItems
              processedItems
              errorMessage
              errorDetails
              accountId
              scorecardId
              scorecard {
                id
                name
              }
              scoreId
              score {
                id
                name
              }
              confusionMatrix
              scoreGoal
              datasetClassDistribution
              isDatasetClassDistributionBalanced
              predictedClassDistribution
              isPredictedClassDistributionBalanced
              taskId
              task {
                id
                type
                status
                target
                command
                description
                dispatchStatus
                metadata
                createdAt
                startedAt
                completedAt
                estimatedCompletionAt
                errorMessage
                errorDetails
                currentStageId
                stages {
                  items {
                    id
                    name
                    order
                    status
                    statusMessage
                    startedAt
                    completedAt
                    estimatedCompletionAt
                    processedItems
                    totalItems
                  }
                }
              }
              scoreResults {
                items {
                  id
                  value
                  confidence
                  metadata
                  explanation
                  itemId
                  createdAt
                }
              }
            }
          }
        `;
        resourceVariables = { id: shareLink.resourceId };
        break;
      // Add cases for other resource types as needed
      default:
        throw new Error(`Unsupported resource type: ${shareLink.resourceType}`);
    }
    
    // Execute the resource query
    const resourceResponse = await client.graphql({
      query: resourceQuery,
      variables: resourceVariables
    }) as GraphQLResult<any>;
    
    // Check for errors
    if (resourceResponse.errors && resourceResponse.errors.length > 0) {
      console.error('GraphQL errors fetching resource:', resourceResponse.errors);
      throw new Error('Error fetching resource');
    }
    
    // Apply view options to filter the data
    const filteredData = applyViewOptions(
      resourceResponse.data, 
      shareLink.resourceType, 
      shareLink.viewOptions
    );
    
    // Log access for analytics
    console.log(JSON.stringify({
      event: 'share_link_access',
      token: token,
      resourceType: shareLink.resourceType,
      resourceId: shareLink.resourceId,
      timestamp: new Date().toISOString(),
      viewOptions: shareLink.viewOptions
    }));
    
    // Return the ShareLink data and the resource data
    return {
      shareLink: {
        token: shareLink.token,
        resourceType: shareLink.resourceType,
        resourceId: shareLink.resourceId,
        viewOptions: shareLink.viewOptions ? JSON.parse(shareLink.viewOptions) : {}
      },
      data: filteredData
    };
  } catch (error) {
    console.error('Error processing request:', error);
    throw error;
  }
};

// Apply view options to filter data based on resource type
function applyViewOptions(data: any, resourceType: string, viewOptions: any): any {
  // Default implementation - return all data
  if (!viewOptions) return data;
  
  try {
    const options = typeof viewOptions === 'string' ? JSON.parse(viewOptions) : viewOptions;
    
    // Resource-specific filtering
    switch (resourceType) {
      case 'Evaluation':
        // Filter evaluation data based on view options
        const evaluation = data.getEvaluation;
        
        // Create a filtered copy of the evaluation
        const filteredEvaluation = { ...evaluation };
        
        // Apply view options
        if (options.includeScoreResults === false) {
          delete filteredEvaluation.scoreResults;
        }
        
        if (options.includeCostMetrics === false) {
          delete filteredEvaluation.cost;
        }
        
        // Filter metrics if specific ones are requested
        if (options.visibleMetrics && Array.isArray(options.visibleMetrics) && filteredEvaluation.metrics) {
          if (typeof filteredEvaluation.metrics === 'string') {
            try {
              const metricsArray = JSON.parse(filteredEvaluation.metrics);
              filteredEvaluation.metrics = metricsArray.filter((metric: any) => 
                options.visibleMetrics.includes(metric.name.toLowerCase())
              );
            } catch (e) {
              console.error('Error parsing metrics JSON:', e);
            }
          } else if (Array.isArray(filteredEvaluation.metrics)) {
            filteredEvaluation.metrics = filteredEvaluation.metrics.filter((metric: any) => 
              options.visibleMetrics.includes(metric.name.toLowerCase())
            );
          }
        }
        
        return { getEvaluation: filteredEvaluation };
        
      // Add cases for other resource types as needed
      default:
        return data;
    }
  } catch (error) {
    console.error('Error applying view options:', error);
    return data;
  }
} 
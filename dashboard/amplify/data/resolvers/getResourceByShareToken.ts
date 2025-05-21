import type { Schema } from '../resource';
import { type GraphQLResult } from '@aws-amplify/api-graphql';
import { Sha256 } from '@aws-crypto/sha256-js';
import { defaultProvider } from '@aws-sdk/credential-provider-node';
import { SignatureV4 } from '@aws-sdk/signature-v4';
import { HttpRequest } from '@aws-sdk/protocol-http';
import fetch from 'node-fetch';
import { Request } from 'node-fetch';

// Define the handler function with the correct type from Schema
export const handler: Schema["getResourceByShareToken"]["functionHandler"] = async (event) => {
  try {
    const { token } = event.arguments;
    
    if (!token) {
      throw new Error('Token is required');
    }
    
    // Get the GraphQL endpoint from environment variables
    const GRAPHQL_ENDPOINT = process.env.API_PLEXUSDASHBOARD_GRAPHQLAPIENDPOINTOUTPUT;
    const AWS_REGION = process.env.AWS_REGION || 'us-east-1';
    
    if (!GRAPHQL_ENDPOINT) {
      throw new Error('GraphQL endpoint not found in environment variables');
    }
    
    // Create a signer for AWS Signature v4
    const endpoint = new URL(GRAPHQL_ENDPOINT);
    const signer = new SignatureV4({
      credentials: defaultProvider(),
      region: AWS_REGION,
      service: 'appsync',
      sha256: Sha256
    });
    
    // Get ShareLink by token
    const shareLinkQuery = `
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
    `;
    
    // Prepare the request to be signed
    const shareLinkRequest = new HttpRequest({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        host: endpoint.host
      },
      hostname: endpoint.host,
      body: JSON.stringify({ 
        query: shareLinkQuery,
        variables: { token }
      }),
      path: endpoint.pathname
    });
    
    // Sign and execute the request
    const signedShareLinkRequest = await signer.sign(shareLinkRequest);
    
    // Log the request details for debugging
    console.log('Request Headers:', JSON.stringify(signedShareLinkRequest.headers));
    
    const shareLinkFetchRequest = new Request(GRAPHQL_ENDPOINT, signedShareLinkRequest);
    const shareLinkFetchResponse = await fetch(shareLinkFetchRequest);
    const shareLinkResponse = await shareLinkFetchResponse.json() as any;
    
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
    const updateShareLinkQuery = `
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
    `;
    
    // Prepare the update request to be signed
    const updateShareLinkRequest = new HttpRequest({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        host: endpoint.host
      },
      hostname: endpoint.host,
      body: JSON.stringify({ 
        query: updateShareLinkQuery,
        variables: {
          id: shareLink.id,
          lastAccessedAt: new Date().toISOString(),
          accessCount: currentCount + 1
        }
      }),
      path: endpoint.pathname
    });
    
    // Sign and execute the update request
    const signedUpdateRequest = await signer.sign(updateShareLinkRequest);
    const updateFetchRequest = new Request(GRAPHQL_ENDPOINT, signedUpdateRequest);
    await fetch(updateFetchRequest);
    
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
                  trace
                  itemId
                  createdAt
                }
              }
            }
          }
        `;
        resourceVariables = { id: shareLink.resourceId };
        break;
      case 'Report':
        resourceQuery = `
          query GetReport($id: ID!) {
            getReport(id: $id) {
              id
              name
              createdAt
              updatedAt
              parameters
              output
              accountId
              reportConfigurationId
              reportConfiguration {
                id
                name
                description
              }
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
              reportBlocks {
                items {
                  id
                  name
                  position
                  type
                  output
                  log
                  reportId
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
    // Prepare the resource request to be signed
    const resourceRequest = new HttpRequest({
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        host: endpoint.host
      },
      hostname: endpoint.host,
      body: JSON.stringify({ 
        query: resourceQuery,
        variables: resourceVariables
      }),
      path: endpoint.pathname
    });
    
    // Sign and execute the resource request
    const signedResourceRequest = await signer.sign(resourceRequest);
    const resourceFetchRequest = new Request(GRAPHQL_ENDPOINT, signedResourceRequest);
    const resourceFetchResponse = await fetch(resourceFetchRequest);
    const resourceResponse = await resourceFetchResponse.json() as any;
    
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
        
        // Handle displayMode option
        if (options.displayMode === 'summary') {
          // In summary mode, don't include score results
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
        
      case 'Report':
        // Filter report data based on view options
        const report = data.getReport;
        
        // Create a filtered copy of the report
        const filteredReport = { ...report };
        
        // Apply view options
        if (options.includeReportBlocks === false) {
          delete filteredReport.reportBlocks;
        }
        
        // Handle displayMode option
        if (options.displayMode === 'summary') {
          // In summary mode, don't include report blocks
          delete filteredReport.reportBlocks;
        }
        
        if (options.includeCostMetrics === false) {
          delete filteredReport.cost;
        }
        
        // Filter metrics if specific ones are requested
        if (options.visibleMetrics && Array.isArray(options.visibleMetrics) && filteredReport.metrics) {
          if (typeof filteredReport.metrics === 'string') {
            try {
              const metricsArray = JSON.parse(filteredReport.metrics);
              filteredReport.metrics = metricsArray.filter((metric: any) => 
                options.visibleMetrics.includes(metric.name.toLowerCase())
              );
            } catch (e) {
              console.error('Error parsing metrics JSON:', e);
            }
          } else if (Array.isArray(filteredReport.metrics)) {
            filteredReport.metrics = filteredReport.metrics.filter((metric: any) => 
              options.visibleMetrics.includes(metric.name.toLowerCase())
            );
          }
        }
        
        return { getReport: filteredReport };
        
      // Add cases for other resource types as needed
      default:
        return data;
    }
  } catch (error) {
    console.error('Error applying view options:', error);
    return data;
  }
} 
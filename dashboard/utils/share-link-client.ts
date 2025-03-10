import { amplifyClient } from './amplify-client';
import type { Schema } from '@/amplify/data/resource';
import { fetchAuthSession } from 'aws-amplify/auth';

// Type for ShareLink data
export type ShareLink = Schema['ShareLink']['type'];

// Type for ShareLink creation parameters
export type CreateShareLinkParams = {
  resourceType: string;
  resourceId: string;
  accountId: string;
  expiresAt?: string;
  viewOptions?: Record<string, any>;
};

// Type for ShareLink view options
export type ShareLinkViewOptions = {
  displayMode?: 'summary' | 'detailed';
  includeMetrics?: boolean;
  includeCostInfo?: boolean;
  customTitle?: string;
  visibleSections?: string[];
  [key: string]: any;
};

// Client for ShareLink operations
export const shareLinkClient = {
  // Create a new ShareLink
  create: async (params: CreateShareLinkParams): Promise<{ data: ShareLink, url: string }> => {
    try {
      // Generate a secure random token
      const token = generateSecureToken();
      
      // Create the ShareLink using amplifyClient
      const response = await amplifyClient.ShareLink.create({
        token,
        resourceType: params.resourceType,
        resourceId: params.resourceId,
        createdBy: await getCurrentUserId(),
        accountId: params.accountId,
        expiresAt: params.expiresAt,
        viewOptions: params.viewOptions ? JSON.stringify(params.viewOptions) : undefined,
        accessCount: 0,
        isRevoked: false
      });
      
      // Generate the public URL based on the resource type
      const url = shareLinkClient.getPublicUrl(token, params.resourceType);
      
      return { 
        data: response.data as ShareLink,
        url
      };
    } catch (error) {
      console.error('Error creating ShareLink:', error);
      throw error;
    }
  },
  
  // Get a ShareLink by ID
  get: async (id: string): Promise<{ data: ShareLink | null }> => {
    try {
      const response = await amplifyClient.ShareLink.get({ id });
      return { data: response.data as ShareLink | null };
    } catch (error) {
      console.error('Error getting ShareLink:', error);
      throw error;
    }
  },
  
  // List ShareLinks for an account
  list: async (accountId: string): Promise<{ data: ShareLink[], nextToken: string | null }> => {
    try {
      const response = await amplifyClient.ShareLink.list({
        filter: { accountId: { eq: accountId } }
      });
      return { 
        data: response.data as ShareLink[], 
        nextToken: response.nextToken || null 
      };
    } catch (error) {
      console.error('Error listing ShareLinks:', error);
      throw error;
    }
  },
  
  // Update a ShareLink
  update: async (id: string, params: Partial<Omit<ShareLink, 'id'>>): Promise<{ data: ShareLink }> => {
    try {
      // Convert viewOptions to string if provided and prepare update params
      const updateParams: {
        id: string;
        token?: string;
        resourceType?: string;
        resourceId?: string;
        expiresAt?: string;
        viewOptions?: string;
        lastAccessedAt?: string;
        accessCount?: number;
        isRevoked?: boolean;
      } = { id };
      
      // Only add defined properties to avoid type issues
      if (params.token) updateParams.token = params.token;
      if (params.resourceType) updateParams.resourceType = params.resourceType;
      if (params.resourceId) updateParams.resourceId = params.resourceId;
      if (params.expiresAt) updateParams.expiresAt = params.expiresAt;
      if (params.viewOptions) updateParams.viewOptions = JSON.stringify(params.viewOptions);
      if (params.lastAccessedAt) updateParams.lastAccessedAt = params.lastAccessedAt;
      if (params.accessCount !== undefined && params.accessCount !== null) updateParams.accessCount = params.accessCount;
      if (params.isRevoked !== undefined && params.isRevoked !== null) updateParams.isRevoked = params.isRevoked;
      
      const response = await amplifyClient.ShareLink.update(updateParams);
      
      return { data: response.data as ShareLink };
    } catch (error) {
      console.error('Error updating ShareLink:', error);
      throw error;
    }
  },
  
  // Revoke a ShareLink
  revoke: async (id: string): Promise<{ data: ShareLink }> => {
    try {
      const response = await amplifyClient.ShareLink.update({
        id,
        isRevoked: true
      });
      
      return { data: response.data as ShareLink };
    } catch (error) {
      console.error('Error revoking ShareLink:', error);
      throw error;
    }
  },
  
  // Get the public URL for a ShareLink
  getPublicUrl: (token: string, resourceType?: string): string => {
    // For evaluations, use the direct evaluations route
    if (resourceType === 'Evaluation') {
      return `${window.location.origin}/evaluations/${token}`;
    }
    
    // For other resource types, use the generic share route
    return `${window.location.origin}/share/${token}`;
  }
};

// Helper function to generate a secure random token
function generateSecureToken(): string {
  const randomBytes = new Uint8Array(16);
  window.crypto.getRandomValues(randomBytes);
  return Array.from(randomBytes)
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

// Helper function to get the current user ID
async function getCurrentUserId(): Promise<string> {
  try {
    const session = await fetchAuthSession();
    const identityId = session.identityId;
    return identityId || 'unknown-user';
  } catch (error) {
    console.error('Error getting current user:', error);
    throw error;
  }
} 
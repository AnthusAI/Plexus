import { generateClient } from "aws-amplify/data";
import type { Schema } from "@/amplify/data/resource";

// IAM client for accessing resources with IAM authorization
let iamClient: ReturnType<typeof generateClient<Schema>> | null = null;

// Get or create the IAM client
export function getIamClient(): ReturnType<typeof generateClient<Schema>> {
  if (!iamClient) {
    // Create a client with IAM authorization
    iamClient = generateClient<Schema>({
      authMode: 'iam'
    });
  }
  return iamClient;
}

// ShareLink operations using IAM authorization
export const iamAmplifyClient = {
  ShareLink: {
    // Get a ShareLink by token using IAM authorization
    getByToken: async (token: string) => {
      const client = getIamClient();
      try {
        const response = await client.models.ShareLink.list({
          filter: {
            token: {
              eq: token
            }
          }
        });
        
        // Return the first matching ShareLink or null
        return { 
          data: response.data.length > 0 ? response.data[0] : null 
        };
      } catch (error) {
        console.error('Error fetching ShareLink by token:', error);
        throw error;
      }
    },
    
    // Get a ShareLink by ID using IAM authorization
    get: async (id: string) => {
      const client = getIamClient();
      try {
        const response = await client.models.ShareLink.get({
          id
        });
        
        return { data: response.data };
      } catch (error) {
        console.error('Error fetching ShareLink by ID:', error);
        throw error;
      }
    },
    
    // Update ShareLink access metrics
    updateAccess: async (id: string) => {
      const client = getIamClient();
      try {
        // First get the current access count
        const currentShareLink = await client.models.ShareLink.get({ id });
        const currentCount = currentShareLink.data?.accessCount || 0;
        
        // Then update with the incremented count
        const response = await client.models.ShareLink.update({
          id,
          lastAccessedAt: new Date().toISOString(),
          accessCount: currentCount + 1
        });
        
        return { data: response.data };
      } catch (error) {
        console.error('Error updating ShareLink access:', error);
        throw error;
      }
    }
  }
}; 
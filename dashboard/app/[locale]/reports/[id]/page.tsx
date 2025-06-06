'use client'

import React, { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { AlertCircle } from 'lucide-react'
import { generateClient } from 'aws-amplify/api'
import { fetchAuthSession } from 'aws-amplify/auth'
import { Schema } from '@/amplify/data/resource'
import ReportTask from '@/components/ReportTask'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getValueFromLazyLoader } from '@/utils/data-operations'
import { parseOutputString } from '@/lib/utils'
import { GraphQLResult } from '@aws-amplify/api'
import BlockRegistryInitializer from '@/components/blocks/BlockRegistryInitializer'
import SquareLogo, { LogoVariant } from '@/components/logo-square';
import { format, parseISO } from 'date-fns';
import { Timestamp } from '@/components/ui/timestamp';

// Share link data type
type ShareLinkData = {
  token: string;
  resourceType: string;
  resourceId: string;
  viewOptions: Record<string, any>;
};

// Report service for operations
export class ReportService {
  private client;

  constructor() {
    this.client = generateClient<Schema>();
  }

  // Helper method to safely get data from Amplify
  private async safeGet<T>(modelName: string, id: string): Promise<T | null> {
    try {
      // @ts-ignore - Bypass TypeScript's type checking for this specific call
      const response = await this.client.models[modelName].get({ id });
      return response.data as T;
    } catch (error) {
      console.error(`Error fetching ${modelName} with ID ${id}:`, error);
      return null;
    }
  }

  // Fetch report by ID for dashboard deep links
  async fetchReportById(id: string): Promise<any> {
    try {
      // Determine auth mode for unauthenticated access
      let authMode: 'userPool' | 'apiKey' | undefined = undefined;
      try {
        const session = await fetchAuthSession();
        if (session.tokens?.idToken) {
          authMode = 'userPool';
        } else {
          authMode = 'apiKey';
        }
      } catch (error) {
        authMode = 'apiKey';
      }

      // Use the graphql API directly with auth mode instead of safeGet
      const response = await this.client.graphql({
        query: `
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
            }
          }
        `,
        variables: { id },
        authMode
      }) as GraphQLResult<{
        getReport: Schema['Report']['type'];
      }>;

      const reportData = response.data?.getReport;
      
      if (!reportData) {
        throw new Error('Report not found');
      }
      
      // Return report data with blocks
      const reportWithBlocks = await this.fetchReportBlocks(reportData);
      return reportWithBlocks;
    } catch (error) {
      console.error('Error fetching report by ID:', error);
      throw error;
    }
  }

  // Fetch report blocks
  async fetchReportBlocks(report: any): Promise<any> {
    try {
      // Determine auth mode for unauthenticated access
      let authMode: 'userPool' | 'apiKey' | undefined = undefined;
      try {
        const session = await fetchAuthSession();
        if (session.tokens?.idToken) {
          authMode = 'userPool';
        } else {
          authMode = 'apiKey';
        }
      } catch (error) {
        authMode = 'apiKey';
      }

      // Condition to (re-)fetch blocks:
      // Simplified check: if reportBlocks or its items are missing, or if the first block lacks a type.
      const shouldFetchBlocks = 
        !report.reportBlocks || 
        !report.reportBlocks.items || 
        report.reportBlocks.items.length === 0 ||
        (report.reportBlocks.items.length > 0 && typeof report.reportBlocks.items[0].type === 'undefined');

      if (shouldFetchBlocks) {
        const blockResponse = await this.client.graphql({
          query: `
            query GetReportAndItsBlocks($reportId: ID!) {
              getReport(id: $reportId) {
                id
                reportBlocks {
                  items {
                    id
                    name
                    position
                    type
                    output
                    log
                    attachedFiles
                  }
                  nextToken
                }
              }
            }
          `,
          variables: { reportId: report.id },
          authMode
        }) as GraphQLResult<{
          getReport: {
            id: string;
            reportBlocks: {
              items: Array<{
                id: string;
                name?: string;
                position: number;
                type: string; // Ensure type is requested
                output: any;
                log?: string;
                attachedFiles?: string;
              }>;
              nextToken?: string;
            };
          };
        }>;

        if (blockResponse.data?.getReport?.reportBlocks?.items) {
          report.reportBlocks = {
            items: blockResponse.data.getReport.reportBlocks.items
          };
          // If you implement pagination, you'd also store blockResponse.data.getReport.reportBlocks.nextToken
        } else {
          report.reportBlocks = { items: [] };
        }
      }
      
      return report;
    } catch (error) {
      console.error('Error fetching report blocks:', error);
      // Ensure reportBlocks.items is at least an empty array on error to prevent further issues
      if (report && !report.reportBlocks) report.reportBlocks = {};
      if (report && !report.reportBlocks.items) report.reportBlocks.items = [];
      return report; // Return the report even if blocks fetch fails
    }
  }
  
  // Fetch report by share token
  async fetchReportByShareToken(token: string): Promise<any> {
    try {
      // Determine auth mode based on user's session
      let authMode: 'userPool' | 'apiKey' | undefined = undefined; // Default to public access
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
      
      // First get the share link data and resource ID
      const response = await this.client.graphql({
        query: `
          query GetResourceByShareToken($token: String!) {
            getResourceByShareToken(token: $token) {
              shareLink {
                token
                resourceType
                resourceId
                viewOptions
              }
              data
            }
          }
        `,
        variables: { token },
        authMode
      }) as GraphQLResult<{
        getResourceByShareToken: {
          shareLink: ShareLinkData;
          data: any;
        }
      }>;
      
      // Check for GraphQL errors
      if (response.errors && response.errors.length > 0) {
        throw new Error(response.errors[0].message);
      }
      
      if (!response.data?.getResourceByShareToken) {
        throw new Error('Failed to load shared resource');
      }
      
      const result = response.data.getResourceByShareToken;
      const shareLink = result.shareLink;
      
      if (!shareLink) {
        throw new Error('Invalid share link data');
      }
      
      // Verify that this is a Report resource
      if (shareLink.resourceType.toUpperCase() !== 'REPORT' && 
          shareLink.resourceType !== 'Report') {
        throw new Error(`Invalid resource type: ${shareLink.resourceType}. Expected: Report`);
      }
      
      // Get the reportId from the shareLink
      const reportId = shareLink.resourceId;
      
      // Parse the initial data if needed
      let reportData;
      if (typeof result.data === 'string') {
        try {
          const parsedData = JSON.parse(result.data);
          reportData = parsedData.getReport || parsedData;
        } catch (e) {
          console.error('Error parsing result.data as JSON:', e);
          reportData = result.data;
        }
      } else {
        reportData = result.data;
      }
      
      // If we have a reportId, fetch the full report data to ensure we have attachedFiles
      if (reportId) {
        try {
          const fullReportResponse = await this.client.graphql({
            query: `
              query GetFullReport($reportId: ID!) {
                getReport(id: $reportId) {
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
                    currentStageId
                    errorMessage
                    stages {
                      items {
                        id
                        name
                        order
                        status
                        statusMessage
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
                      attachedFiles
                    }
                  }
                }
              }
            `,
            variables: { reportId },
            authMode
          }) as GraphQLResult<{
            getReport: any;
          }>;
          
          if (fullReportResponse.data?.getReport) {
            reportData = fullReportResponse.data.getReport;
          }
        } catch (err) {
          console.error('Error fetching full report, will continue with partial data');
        }
      }
      
      // Fetch any additional blocks if needed
      return this.fetchReportBlocks(reportData);
    } catch (error) {
      console.error('Error fetching report by share token:', error);
      throw error;
    }
  }

  // Check if a string is a valid share token
  isValidToken(token: string): boolean {
    // Support both UUID format and MD5/hex string format
    return /^[0-9a-f]{32}$/i.test(token) || // MD5/hex string format (32 chars)
           /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(token); // UUID format
  }
}

// Props interface for the component
interface PublicReportProps {
  reportService?: ReportService;
  isDashboardView?: boolean;
}

export default function ReportPage() {
  // For share views, render the public report component
  return <PublicReport />;
}

export function PublicReport({ 
  reportService = new ReportService(),
  isDashboardView = false
}: PublicReportProps = {}) {
  const { id } = useParams() as { id: string };
  const router = useRouter();
  const [report, setReport] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Memoize the service to prevent re-renders
  const memoizedService = React.useMemo(() => reportService, []);

  useEffect(() => {
    async function loadReport() {
      try {
        if (!id) {
          throw new Error('No ID or token provided');
        }
        
        let data: any;
        
        // If this is a share token, fetch by token
        if (memoizedService.isValidToken(id) && !isDashboardView) {
          console.log('Loading report with token:', id);
          data = await memoizedService.fetchReportByShareToken(id);
        } else {
          // Otherwise, fetch by ID (for dashboard deep links)
          console.log('Loading report with ID:', id);
          data = await memoizedService.fetchReportById(id);
        }
        
        console.log('Successfully loaded report:', {
          id: data.id,
          name: data.name,
          blocksCount: data.reportBlocks?.items?.length || 0
        });
        
        setReport(data);
      } catch (err: any) {
        console.error('Error fetching report:', err);
        setError(err.message || 'Failed to load report');
      } finally {
        setLoading(false);
      }
    }
    
    loadReport();
  }, [id, memoizedService, isDashboardView]);

  // Show loading state
  if (loading) {
    return (
      <div className="px-4 w-full">
        <div className="bg-background p-6 rounded-md">
          <div className="flex flex-col items-center justify-center min-h-[200px]">
            <div className="w-10 h-10 border-t-[8px] border-secondary rounded-full animate-spin mb-4"></div>
            <p className="text-muted-foreground">Loading report...</p>
          </div>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="px-4 w-full">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <div className="mt-4">
          <Button onClick={() => router.push('/')}>Return to Home</Button>
        </div>
      </div>
    );
  }

  // Transform the report data into the format expected by ReportTask
  if (report) {
    // Extract task from the report
    const task = report.task ? getValueFromLazyLoader(report.task) : null;
    
    // Extract reportConfiguration
    const config = report.reportConfiguration ? 
      getValueFromLazyLoader(report.reportConfiguration) : null;
    
    // Parse report blocks
    const reportBlocks = report.reportBlocks?.items?.map((block: any) => {
      const outputData = parseOutputString(block.output);

      // Prioritize block.type from API, then outputData.class, then 'unknown'
      const blockType = block.type || outputData.class || 'unknown'; 
      
      return {
        type: blockType,
        config: outputData, // Config is often the same as output for many blocks
        output: outputData,
        log: block.log || undefined,
        name: block.name || undefined, // Use API block name if available
        position: block.position,
        attachedFiles: block.attachedFiles,
        // Pass the original block ID as well, might be useful for keys or debugging
        originalBlockId: block.id 
      };
    }) || [];
    
    // Ensure we have a valid display name
    const displayName = report.name || 
      (config?.name ? `${config.name}` : `Report ${report.id.substring(0, 6)}`);
    
    // Format stages for display
    const stages = [];
    if (task && task.stages) {
      const stagesData = getValueFromLazyLoader(task.stages);
      if (stagesData && stagesData.items) {
        stages.push(...stagesData.items.map((stage: any) => ({
          key: stage.id || `stage-${Math.random()}`,
          label: stage.name || '',
          color: 'bg-primary',
          name: stage.name || '',
          order: stage.order || 0,
          status: stage.status || 'PENDING',
          processedItems: stage.processedItems || 0,
          totalItems: stage.totalItems || 0,
          statusMessage: stage.statusMessage || ''
        })));
      }
    }
    
    // Find current stage name
    let currentStageName = '';
    if (task && task.currentStageId) {
      const currentStage = stages.find((s: any) => s.key === task.currentStageId);
      if (currentStage) {
        currentStageName = currentStage.name;
      }
    }

    const isShareView = memoizedService.isValidToken(id) && !isDashboardView;
    const displayTimestamp = report.updatedAt || report.createdAt;

    // Render the report task with data
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <div className="px-3 sm:px-4 md:px-5 lg:px-6 xl:px-8 w-full mt-4 flex-1">
          <BlockRegistryInitializer />
          <ReportTask
            variant={isShareView ? "bare" : "detail"}
            task={{
              id: report.id,
              type: 'Report',
              name: '',
              description: '',
              scorecard: '',
              score: '',
              time: report.updatedAt || report.createdAt || '',
              data: {
                id: report.id,
                title: displayName,
                name: displayName,
                configName: config?.name || displayName,
                configDescription: config?.description,
                createdAt: report.createdAt,
                updatedAt: report.updatedAt,
                output: report.output,
                reportBlocks: reportBlocks
              },
              stages: stages,
              status: task?.status || 'COMPLETED',
              currentStageName: currentStageName,
              errorMessage: task?.errorMessage
            }}
            onClick={() => {}}
          />
        </div>
        {isShareView && displayTimestamp && (
          <footer className="py-4 px-3 sm:px-4 md:px-5 lg:px-6 xl:px-8 flex-shrink-0">
            <div className="w-full">
              <div className="flex items-center justify-between">
                <Timestamp
                  time={displayTimestamp}
                  variant="relative"
                  showIcon={true}
                  className="text-sm"
                />
                {process.env.NEXT_PUBLIC_MINIMAL_BRANDING !== 'true' && (
                  <div className="flex items-center">
                    <span className="text-sm text-muted-foreground mr-2">powered by</span>
                    <a 
                      href="https://plexus.anth.us" 
                      target="_blank" 
                      rel="noopener noreferrer"
                      className="relative w-24 h-8"
                    >
                      <SquareLogo variant={LogoVariant.Wide} />
                    </a>
                  </div>
                )}
              </div>
            </div>
          </footer>
        )}
      </div>
    );
  }

  // Fallback if no report is loaded
  return null;
} 
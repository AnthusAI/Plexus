"use client"

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
// Import the setup file for its side effects
import "@/components/blocks/registrySetup"; 
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, MoreHorizontal, Trash2, Share, Pencil, Play } from "lucide-react"
import { format, formatDistanceToNow, parseISO } from "date-fns"
import { Badge } from "@/components/ui/badge"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter, useParams, usePathname } from 'next/navigation'
import { getClient } from '@/utils/amplify-client'
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api'
import { useMediaQuery } from "@/hooks/use-media-query"
import { CardButton } from "@/components/CardButton"
import { getValueFromLazyLoader } from '@/utils/data-operations'
import type { LazyLoader } from '@/utils/types'
import { toast } from "sonner"
import { shareLinkClient, ShareLinkViewOptions } from "@/utils/share-link-client"
import { ShareResourceModal } from "@/components/share-resource-modal"
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton" // Placeholder skeleton
import ReportTask, { ReportTaskData } from "@/components/ReportTask" // Import ReportTask with its types
import { TaskDispatchButton } from '@/components/task-dispatch' // Placeholder for dispatch

// Define types based on Amplify schema
type Report = Schema['Report']['type'] & {
  task?: Schema['Task']['type'] | LazyLoader<Schema['Task']['type']> | null
  reportConfiguration?: Schema['ReportConfiguration']['type'] | LazyLoader<Schema['ReportConfiguration']['type']> | null
};
type Task = Schema['Task']['type'];
type ReportConfiguration = Schema['ReportConfiguration']['type'];

// Simplified types for dashboard state
type ReportDisplayData = {
  id: string;
  name?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
  output?: string | null;
  reportConfiguration?: {
    id: string;
    name?: string | null;
    description?: string | null;
  } | null;
  task?: Task | null;
};

// TODO: Define actual report configuration for dispatch
interface TaskConfigType {
  taskType: string;
  label: string;
  icon: React.ComponentType;
  requiredContext: string[];
  getTaskMetadata: (context: Record<string, any>) => Record<string, any>;
}

const reportsConfig: TaskConfigType = {
  taskType: 'REPORT_GENERATION', // Example
  label: 'Generate Report',
  icon: Play,
  requiredContext: ['reportConfigurationId'], // Example
  getTaskMetadata: (context: Record<string, any>) => ({
    reportConfigurationId: context.reportConfigurationId,
    // Add other necessary metadata
  }),
};

const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || 'call-criteria'

// GraphQL query to list accounts
const LIST_ACCOUNTS = `
  query ListAccounts($filter: ModelAccountFilterInput) {
    listAccounts(filter: $filter) {
      items {
        id
        key
      }
    }
  }
`

// GraphQL query to list reports by account and update timestamp
// Includes nested task and reportConfiguration data
const LIST_REPORTS = `
  query ListReportByAccountIdAndUpdatedAt(
    $accountId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
    $nextToken: String
  ) {
    listReportByAccountIdAndUpdatedAt(
      accountId: $accountId
      sortDirection: $sortDirection
      limit: $limit
      nextToken: $nextToken
    ) {
      items {
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
      }
      nextToken
    }
  }
`

// GraphQL query to get a single report with its blocks
const GET_REPORT_WITH_BLOCKS = `
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
          output
          log
        }
      }
    }
  }
`

// GraphQL subscription queries for real-time updates
const SUBSCRIBE_ON_CREATE_REPORT = `
  subscription OnCreateReport($accountId: String!) {
    onCreateReport(filter: { accountId: { eq: $accountId } }) {
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
    }
  }
`;

const SUBSCRIBE_ON_UPDATE_REPORT = `
  subscription OnUpdateReport($accountId: String!) {
    onUpdateReport(filter: { accountId: { eq: $accountId } }) {
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
    }
  }
`;

const SUBSCRIBE_ON_CREATE_REPORT_BLOCK = `
  subscription OnCreateReportBlock {
    onCreateReportBlock {
      id
      name
      position
      output
      log
      reportId
    }
  }
`;

const SUBSCRIBE_ON_UPDATE_REPORT_BLOCK = `
  subscription OnUpdateReportBlock {
    onUpdateReportBlock {
      id
      name
      position
      output
      log
      reportId
    }
  }
`;

interface ListAccountResponse {
  listAccounts: {
    items: Array<{
      id: string;
      key: string;
    }>;
  };
}

interface ListReportsResponse {
  listReportByAccountIdAndUpdatedAt: {
    items: Report[];
    nextToken: string | null;
  };
}

interface GetReportResponse {
  getReport: Report & {
    reportBlocks: {
      items: RawReportBlock[];
    };
  };
}

// Add a type for the raw block data from the API
interface RawReportBlock {
  id: string;
  name?: string | null;
  position: number;
  output: Record<string, any>;
  log?: string | null;
}

// Function to safely access nested properties in objects
const getNestedProperty = (obj: any, path: string[], defaultValue: any = null) => {
  return path.reduce((prev, curr) => {
    return prev && prev[curr] !== undefined ? prev[curr] : defaultValue;
  }, obj);
};

// Transformation function
function transformReportData(report: Report): ReportDisplayData | null {
  if (!report) return null;

  console.log('Raw report data in transform:', { 
    id: report.id, 
    name: report.name, 
    hasName: !!report.name,
    nameType: typeof report.name,
    reportType: typeof report,
    configId: report.reportConfigurationId
  });

  const taskData = report.task ? getValueFromLazyLoader(report.task) : null;
  const configData = report.reportConfiguration ? getValueFromLazyLoader(report.reportConfiguration) : null;

  // Safely extract configuration data
  let configInfo = null;
  if (configData && typeof configData === 'object') {
    // Try to get properties from the object directly or from data property if it exists
    const id = getNestedProperty(configData, ['id'], '') || getNestedProperty(configData, ['data', 'id'], '');
    const name = getNestedProperty(configData, ['name'], null) || getNestedProperty(configData, ['data', 'name'], null);
    const description = getNestedProperty(configData, ['description'], null) || getNestedProperty(configData, ['data', 'description'], null);
    
    if (id) {
      configInfo = {
        id: id,
        name: name,
        description: description
      };
    }
  }

  // Extract name with fallbacks in order:
  // 1. Direct report.name
  // 2. If report.name is an object with a name property, use that
  // 3. Config name
  // 4. ID-based name
  let reportName = null;
  
  if (report.name) {
    if (typeof report.name === 'string') {
      reportName = report.name;
    } else if (typeof report.name === 'object' && report.name !== null) {
      // If it's an object, try to extract name from it
      reportName = (report.name as any).name || null;
    }
  }
  
  // Final fallbacks if we still don't have a name
  reportName = reportName || (configInfo?.name) || `Report ${report.id.substring(0, 6)}`;

  const transformed = {
    id: report.id,
    name: reportName,
    createdAt: report.createdAt,
    updatedAt: report.updatedAt,
    output: report.output || null,
    reportConfiguration: configInfo,
    task: taskData as Task | null
  };

  console.log('Transformed report data:', { 
    id: transformed.id, 
    name: transformed.name,
    configName: transformed.reportConfiguration?.name
  });

  return transformed;
}

export default function ReportsDashboard({
  initialSelectedReportId = null,
}: {
  initialSelectedReportId?: string | null,
} = {}) {
  // Add a useEffect to potentially log when setup runs relative to mount
  useEffect(() => {
    console.log("ReportsDashboard mounted. Block registry setup should have run.");
  }, []); 

  const { user } = useAuthenticator()
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [reports, setReports] = useState<ReportDisplayData[]>([])
  const [selectedReportId, setSelectedReportId] = useState<string | null>(initialSelectedReportId)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [dataHasLoadedOnce, setDataHasLoadedOnce] = useState(false)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const [isShareModalOpen, setIsShareModalOpen] = useState(false)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  const [nextToken, setNextToken] = useState<string | null>(null); // For pagination
  const [selectedReportBlocks, setSelectedReportBlocks] = useState<Array<{
    type: string;
    config: Record<string, any>;
    output: Record<string, any>;
    log?: string;
    name?: string;
    position: number;
  }> | null>(null);
  const [subscriptions, setSubscriptions] = useState<{ unsubscribe: () => void }[]>([]);

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        const accountResponse = await getClient().graphql<ListAccountResponse>({
          query: LIST_ACCOUNTS,
          variables: {
            filter: { key: { eq: ACCOUNT_KEY } }
          }
        })

        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const id = accountResponse.data.listAccounts.items[0].id
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setError('No account found')
          setIsLoading(false)
        }
      } catch (err: any) {
        console.error('Error fetching account:', err)
        setError(`Error fetching account: ${err.message}`)
        setIsLoading(false)
      }
    }
    fetchAccountId()
  }, [])

  // Fetch Reports Data
  const fetchReports = useCallback(async (currentAccountId: string, currentNextToken: string | null) => {
    setIsLoading(true);
    setError(null);
    try {
      console.log(`Fetching reports for account ${currentAccountId} with nextToken: ${currentNextToken}`);
      const reportsResponse = await getClient().graphql<ListReportsResponse>({
        query: LIST_REPORTS,
        variables: {
          accountId: currentAccountId,
          sortDirection: 'DESC', // Get newest first
          limit: 20, // Adjust limit as needed
          nextToken: currentNextToken,
        }
      });

      if ('data' in reportsResponse && reportsResponse.data?.listReportByAccountIdAndUpdatedAt) {
        const fetchedItems = reportsResponse.data.listReportByAccountIdAndUpdatedAt.items || [];
        const transformedItems = fetchedItems
          .map(transformReportData)
          .filter((item: unknown): item is ReportDisplayData => item !== null);

        console.log(`Fetched ${transformedItems.length} reports`);

        setReports(prevReports => currentNextToken ? [...prevReports, ...transformedItems] : transformedItems);
        setNextToken(reportsResponse.data.listReportByAccountIdAndUpdatedAt.nextToken);

        if (!dataHasLoadedOnce) {
          setDataHasLoadedOnce(true);
        }
      } else {
        console.warn('No reports data found in response:', reportsResponse);
        setReports(prevReports => currentNextToken ? prevReports : []); // Clear if initial fetch is empty
        setNextToken(null);
      }
    } catch (err: any) {
      console.error('Error fetching reports:', err);
      setError(`Error fetching reports: ${err.message}`);
      setReports(prevReports => currentNextToken ? prevReports : []); // Clear on error
      setNextToken(null);
    } finally {
      setIsLoading(false);
    }
  }, [dataHasLoadedOnce]); // Dependency array includes dataHasLoadedOnce

  // Add the effect for initial fetch when accountId is available
  useEffect(() => {
    if (accountId && !dataHasLoadedOnce) { // Only fetch initially if data hasn't loaded
      fetchReports(accountId, null);
    }
  }, [accountId, dataHasLoadedOnce, fetchReports]);

  // Fetch Report Blocks when selectedReportId changes
  useEffect(() => {
    if (selectedReportId) {
      fetchReportBlocks(selectedReportId);
    } else {
      setSelectedReportBlocks(null);
    }
  }, [selectedReportId]);

  // Set up subscriptions for real-time updates
  useEffect(() => {
    if (!accountId) return;

    console.log('Setting up report subscriptions for accountId:', accountId);
    const subscriptionHandlers: { unsubscribe: () => void }[] = [];

    // Subscribe to new report creations
    try {
      const createReportSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_CREATE_REPORT,
        variables: { accountId }
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateReport: any } }) => {
          console.log('🔔 New report created SUB-EVENT:', data?.onCreateReport);
          if (data?.onCreateReport) {
            const newReport = data.onCreateReport;
            console.log('🔔 SUB-EVENT: Original new report name:', newReport.name, 'type:', typeof newReport.name);
            
            // DIRECT APPROACH: Create a report display object manually to ensure name is preserved
            const manualTransformedReport: ReportDisplayData = {
              id: newReport.id,
              name: typeof newReport.name === 'string' ? newReport.name : 
                   (typeof newReport.name === 'object' && newReport.name !== null) ? 
                   (newReport.name as any).name || `Report ${newReport.id.substring(0, 6)}` : 
                   `Report ${newReport.id.substring(0, 6)}`,
              createdAt: newReport.createdAt,
              updatedAt: newReport.updatedAt,
              output: newReport.output || null,
              reportConfiguration: newReport.reportConfiguration ? {
                id: newReport.reportConfiguration.id,
                name: newReport.reportConfiguration.name,
                description: newReport.reportConfiguration.description
              } : null,
              task: newReport.task || null
            };
            
            console.log('🔔 SUB-EVENT: Manually transformed report:', manualTransformedReport);
            console.log('🔔 SUB-EVENT: Manual transformed name:', manualTransformedReport.name);
            
            // Use the manual transformation to ensure name is preserved
            setReports(prevReports => {
              const newReports = [manualTransformedReport, ...prevReports];
              console.log('🔔 SUB-EVENT: Updated reports array:', newReports.map(r => ({ id: r.id, name: r.name })));
              return newReports;
            });
          }
        },
        error: (error: Error) => {
          console.error('Error in create report subscription:', error);
        }
      });

      subscriptionHandlers.push(createReportSubscription);
    } catch (error) {
      console.error('Failed to set up create report subscription:', error);
    }

    // Subscribe to report updates
    try {
      const updateReportSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_UPDATE_REPORT,
        variables: { accountId }
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateReport: any } }) => {
          console.log('Report updated:', data?.onUpdateReport);
          if (data?.onUpdateReport) {
            const updatedReport = data.onUpdateReport;
            // Cast to any to avoid type issues with transformReportData
            const transformedReport = transformReportData(updatedReport as any);
            console.log('Transformed report from update subscription:', transformedReport);
            if (transformedReport) {
              // Ensure the name is properly set
              if (!transformedReport.name && updatedReport.name) {
                transformedReport.name = updatedReport.name;
              }
              setReports(prevReports => 
                prevReports.map(report => 
                  report.id === transformedReport.id ? transformedReport : report
                )
              );
            }
          }
        },
        error: (error: Error) => {
          console.error('Error in update report subscription:', error);
        }
      });

      subscriptionHandlers.push(updateReportSubscription);
    } catch (error) {
      console.error('Failed to set up update report subscription:', error);
    }

    // Save subscriptions for cleanup
    setSubscriptions(prevSubscriptions => [...prevSubscriptions, ...subscriptionHandlers]);

    // Cleanup on unmount or accountId change
    return () => {
      console.log('Cleaning up report subscriptions');
      subscriptionHandlers.forEach(subscription => {
        try {
          subscription.unsubscribe();
        } catch (err) {
          console.error('Error unsubscribing:', err);
        }
      });
    };
  }, [accountId]);

  // Make fetchReportBlocks more robust by handling parsed JSON if needed
  const fetchReportBlocks = async (reportId: string) => {
    try {
      // Keep this log to show when blocks are being fetched
      console.log(`Fetching blocks for report ${reportId}`);
      const response = await getClient().graphql<GetReportResponse>({
        query: GET_REPORT_WITH_BLOCKS,
        variables: { id: reportId }
      });

      if ('data' in response && response.data?.getReport?.reportBlocks?.items) {
        // Transform the blocks to match the expected structure
        const transformedBlocks = response.data.getReport.reportBlocks.items.map((block: RawReportBlock) => {
          // Handle case where output is already parsed or is a string
          let outputData;
          try {
            outputData = typeof block.output === 'string' ? JSON.parse(block.output) : block.output;
          } catch (err) {
            console.error('Error parsing block output:', err);
            outputData = block.output || {};
          }
          
          return {
            type: outputData.class || 'unknown', // Extract type from output.class
            config: outputData, // Use output as config
            output: outputData,
            log: block.log || undefined,
            name: block.name || undefined,
            position: block.position
          };
        });
        
        // Important log to verify block count
        console.log(`Fetched ${transformedBlocks.length} blocks for report ${reportId}`);
        
        // Force a state update by creating a new array
        setSelectedReportBlocks([...transformedBlocks]);
        
        // Create a new snapshot of the reports array with the updated report
        // This forces a re-render of the component tree
        setReports(prevReports => {
          return prevReports.map(r => {
            if (r.id === reportId) {
              // Keep this log to verify the report is being updated
              console.log(`Updating report ${reportId} with fresh data to trigger re-render`);
              // Create a new object to trigger reference change
              return { 
                ...r,
                // Add a timestamp to force React to detect the change
                _lastUpdated: Date.now() 
              };
            }
            return r;
          });
        });
      } else {
        console.log(`No blocks found for report ${reportId}`);
        setSelectedReportBlocks([]);
      }
    } catch (err: any) {
      console.error('Error fetching report blocks:', err);
      setSelectedReportBlocks([]);
    }
  };

  // Subscribe to report block updates for the selected report
  useEffect(() => {
    if (!selectedReportId) return;

    console.log('Setting up report block subscriptions for reportId:', selectedReportId);
    const blockSubscriptionHandlers: { unsubscribe: () => void }[] = [];

    // Subscribe to new report block creations
    try {
      const createBlockSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_CREATE_REPORT_BLOCK
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateReportBlock: { id: string, reportId: string, name?: string, position: number, output: any, log?: string } } }) => {
          // Important log to verify subscription is receiving events
          console.log('New report block created via subscription:', data?.onCreateReportBlock?.id);
          if (data?.onCreateReportBlock && data.onCreateReportBlock.reportId === selectedReportId) {
            // When a new block is created for the selected report, refresh blocks
            fetchReportBlocks(selectedReportId);
          }
        },
        error: (error: Error) => {
          console.error('Error in create report block subscription:', error);
        }
      });

      blockSubscriptionHandlers.push(createBlockSubscription);
    } catch (error) {
      console.error('Failed to set up create report block subscription:', error);
    }

    // Subscribe to report block updates
    try {
      const updateBlockSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_UPDATE_REPORT_BLOCK
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onUpdateReportBlock: { id: string, reportId: string, name?: string, position: number, output: any, log?: string } } }) => {
          if (data?.onUpdateReportBlock && data.onUpdateReportBlock.reportId === selectedReportId) {
            // Key log to verify subscription events
            console.log('Report block updated via subscription:', data.onUpdateReportBlock.id);
            
            // When a block is updated for the selected report, refresh blocks
            fetchReportBlocks(selectedReportId);
          }
        },
        error: (error: Error) => {
          console.error('Error in update report block subscription:', error);
        }
      });

      blockSubscriptionHandlers.push(updateBlockSubscription);
    } catch (error) {
      console.error('Failed to set up update report block subscription:', error);
    }

    // Save subscriptions for cleanup
    setSubscriptions(prevSubscriptions => [...prevSubscriptions, ...blockSubscriptionHandlers]);

    // Cleanup on unmount or selectedReportId change
    return () => {
      console.log('Cleaning up report block subscriptions');
      blockSubscriptionHandlers.forEach(subscription => {
        try {
          subscription.unsubscribe();
        } catch (err) {
          console.error('Error unsubscribing:', err);
        }
      });
    };
  }, [selectedReportId]);

  // Cleanup all subscriptions on component unmount
  useEffect(() => {
    return () => {
      console.log('Cleaning up all subscriptions on unmount');
      subscriptions.forEach(subscription => {
        try {
          subscription.unsubscribe();
        } catch (err) {
          console.error('Error unsubscribing on unmount:', err);
        }
      });
    };
  }, [subscriptions]);

  // Handle deep linking and browser navigation (similar to evaluations)
  useEffect(() => {
    const evalMatch = pathname.match(/\/lab\/reports\/([^\/]+)/);
    const idFromUrl = evalMatch ? evalMatch[1] : null;
    if (idFromUrl && idFromUrl !== selectedReportId) {
      setSelectedReportId(idFromUrl);
    }

    const handlePopState = () => {
      const evalMatchPop = window.location.pathname.match(/\/lab\/reports\/([^\/]+)/);
      const idFromUrlPop = evalMatchPop ? evalMatchPop[1] : null;
      setSelectedReportId(idFromUrlPop);
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, [pathname, selectedReportId]);

  // Handle selecting a report
  const handleSelectReport = (id: string | null) => {
    if (id !== selectedReportId) {
      setSelectedReportId(id);
      const newPathname = id ? `/lab/reports/${id}` : '/lab/reports';
      window.history.pushState(null, '', newPathname);
      if (isNarrowViewport && id) {
          setIsFullWidth(true);
      }
    }
  };

  // Handle closing the selected report detail view
  const handleCloseReport = () => {
    setSelectedReportId(null);
    setIsFullWidth(false);
    window.history.pushState(null, '', '/lab/reports');
  };

  // Placeholder delete handler
  const handleDelete = async (reportId: string) => {
    console.log("Attempting to delete report:", reportId);
    toast.info("Delete functionality not yet implemented.");
    // try {
    //   await getClient().graphql({ /* ... delete mutation ... */ });
    //   setReports(prev => prev.filter(r => r.id !== reportId));
    //   if (selectedReportId === reportId) {
    //     handleCloseReport();
    //   }
    //   toast.success("Report deleted");
    // } catch (error) {
    //   console.error("Error deleting report:", error);
    //   toast.error("Failed to delete report");
    // }
  };

  // Share functionality (similar to evaluations)
  const copyLinkToClipboard = (reportId: string) => {
    if (!reportId || !accountId) return;
    setSelectedReportId(reportId); // Ensure the correct report is selected for sharing
    setIsShareModalOpen(true);
    setShareUrl(null); // Clear previous URL
  }

  const handleCreateShareLink = async (expiresAt: string, viewOptions: ShareLinkViewOptions) => {
    if (!selectedReportId || !accountId) return;
    try {
      const { url } = await shareLinkClient.create({
        resourceType: 'Report', // Use 'Report' as resource type
        resourceId: selectedReportId,
        accountId: accountId,
        expiresAt,
        viewOptions
      });
      if (!url) throw new Error("Generated URL is empty");
      setShareUrl(url);
      await navigator.clipboard.writeText(url);
      toast.success("Share link created and copied");
      setIsShareModalOpen(false); // Close modal on success
    } catch (error) {
      console.error("Error creating/copying share link:", error);
      toast.error("Failed to create share link", { description: "Could not copy to clipboard." });
      // Keep modal open if copy fails so user can manually copy
      setIsShareModalOpen(true);
    }
  }

  const handleCloseShareModal = useCallback(() => {
    setIsShareModalOpen(false);
    setShareUrl(null);
  }, []);


  // Draggable panel resizing (similar to evaluations)
  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = leftPanelWidth

    const handleDrag = (e: MouseEvent) => {
      const delta = e.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + (delta / window.innerWidth) * 100, 20), 80)
      setLeftPanelWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
  }

  // Filter function to ensure valid objects
  const isReportDisplayData = (item: any): item is ReportDisplayData => {
    return item !== null && typeof item === 'object' && 'id' in item;
  };

  // Add useEffect to log reports state changes
  useEffect(() => {
    // Remove excessive logging of report state updates
    if (reports.length > 0) {
      console.log('Reports updated:', reports.length);
    }
  }, [reports]);

  // Memoized rendering of the selected report's details
  const renderSelectedReport = useMemo(() => {
    if (!selectedReportId) return null;
    const report = reports.find(r => r.id === selectedReportId);
    if (!report) return null; // Report might not be loaded yet

    // Streamlined log with just key information
    console.log('Rendering selected report:', {
      id: report.id,
      name: report.name,
      blocks: selectedReportBlocks?.length || 0
    });

    // Safely extract stages
    const stages = [];
    if (report.task && 'stages' in report.task && report.task.stages) {
      const stagesData = getValueFromLazyLoader(report.task.stages);
      if (stagesData && 'items' in stagesData && Array.isArray(stagesData.items)) {
        stages.push(...stagesData.items.map((stage: any) => ({
          key: stage.id || `stage-${Math.random()}`,
          label: stage.name || '',
          color: 'bg-primary',
          name: stage.name || '',
          order: typeof stage.order === 'number' ? stage.order : 0,
          status: stage.status || 'PENDING',
          processedItems: typeof stage.processedItems === 'number' ? stage.processedItems : 0,
          totalItems: typeof stage.totalItems === 'number' ? stage.totalItems : 0,
          statusMessage: stage.statusMessage || ''
        })));
      }
    }

    // Find current stage name safely
    let currentStageName = '';
    if (report.task && report.task.currentStageId) {
      const currentStage = stages.find(s => s.key === report.task?.currentStageId);
      if (currentStage) {
        currentStageName = currentStage.name;
      }
    }

    // Ensure we have a valid display name for the report
    const displayName = report.name || 'Report';

    // Generate a unique key that changes whenever blocks are updated
    const reportKey = `${report.id}-${selectedReportBlocks?.length || 0}-${Date.now()}`;

    return (
      <ReportTask
        variant="detail"
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
            configName: report.reportConfiguration?.name,
            configDescription: report.reportConfiguration?.description,
            createdAt: report.createdAt,
            updatedAt: report.updatedAt,
            output: report.output,
            reportBlocks: selectedReportBlocks || [] // Add the report blocks here
          },
          stages: stages,
          status: report.task?.status as any || 'PENDING',
          currentStageName: currentStageName,
          errorMessage: report.task?.errorMessage || undefined
        }}
        onClick={() => {}}
        controlButtons={
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
               <CardButton icon={MoreHorizontal} aria-label="More options" onClick={() => {}} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
               <DropdownMenuItem onClick={() => copyLinkToClipboard(report.id)}>
                <Share className="mr-2 h-4 w-4" />
                <span>Share</span>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => handleDelete(report.id)}>
                <Trash2 className="mr-2 h-4 w-4" />
                <span>Delete</span>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        }
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseReport}
        key={reportKey} // Force re-render when blocks change with timestamp
      />
    );
  }, [selectedReportId, reports, selectedReportBlocks, isFullWidth, handleCloseReport, handleDelete, copyLinkToClipboard]); // Dependencies

  // Memoized click handler factory
  const getReportClickHandler = useCallback((reportId: string) => {
      return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
        if (e && typeof e.preventDefault === 'function') {
            e.preventDefault();
        }
        handleSelectReport(reportId);
      };
  }, [handleSelectReport]);


  // Loading and Error States
  const showLoading = isLoading && !dataHasLoadedOnce;

  if (showLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {error ? `Error: ${error}` : ''}
        </div>
        <EvaluationDashboardSkeleton /> {/* Use placeholder */}
      </div>
    )
  }

  if (error && !dataHasLoadedOnce) { // Show error prominently if initial load failed
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">Reports</h1>
        <div className="text-sm text-destructive">Error fetching reports: {error}</div>
        <Button onClick={() => accountId && fetchReports(accountId, null)}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header Area - TODO: Add filtering/sorting controls */}
      <div className="flex-none p-1.5">
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-xl font-semibold">Reports</h1>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <div className="flex gap-2">
            <Button onClick={() => router.push('/lab/reports/edit')}>
              <Pencil className="mr-2 h-4 w-4"/> Edit Configurations
            </Button>
            <Button disabled>
              <Play className="mr-2 h-4 w-4"/> Run Report
            </Button>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex min-h-0 p-1.5">
        {/* Report List Panel */}
        <div
          className={`
            ${selectedReportId && !isNarrowViewport && !isFullWidth ? '' : 'w-full'}
            ${selectedReportId && !isNarrowViewport && isFullWidth ? 'hidden' : ''}
            h-full overflow-y-auto overflow-x-hidden @container
          `}
          style={selectedReportId && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          {isLoading && reports.length > 0 && <p className="text-sm text-muted-foreground p-2">Loading more...</p>}
          {!isLoading && reports.length === 0 && !error && (
            <div className="text-sm text-muted-foreground p-4 text-center">No reports found for this account.</div>
          )}
          {reports.length > 0 && (
            <div className={`
              grid gap-3
              ${selectedReportId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
            `}>
              {reports.map((report) => {
                const clickHandler = getReportClickHandler(report.id);
                
                // ADD DEBUG CODE
                console.log('🔍 DEBUG GRID ITEM:', {
                  reportId: report.id.substring(0, 6),
                  reportName: report.name,
                  reportHasName: !!report.name,
                  reportNameType: typeof report.name
                });
                
                // Safely extract stages (reuse the same approach as above)
                const stages = [];
                if (report.task && 'stages' in report.task && report.task.stages) {
                  const stagesData = getValueFromLazyLoader(report.task.stages);
                  if (stagesData && 'items' in stagesData && Array.isArray(stagesData.items)) {
                    stages.push(...stagesData.items.map((stage: any) => ({
                      key: stage.id || `stage-${Math.random()}`,
                      label: stage.name || '',
                      color: 'bg-primary',
                      name: stage.name || '',
                      order: typeof stage.order === 'number' ? stage.order : 0,
                      status: stage.status || 'PENDING',
                      processedItems: typeof stage.processedItems === 'number' ? stage.processedItems : 0,
                      totalItems: typeof stage.totalItems === 'number' ? stage.totalItems : 0,
                      statusMessage: stage.statusMessage || ''
                    })));
                  }
                }

                // Find current stage name safely
                let currentStageName = '';
                if (report.task && report.task.currentStageId) {
                  const currentStage = stages.find(s => s.key === report.task?.currentStageId);
                  if (currentStage) {
                    currentStageName = currentStage.name;
                  }
                }
                
                // Ensure we have a valid display name for the report - USE FORCED STRING TYPE
                const displayName = String(report.name || 'Report');
                
                console.log(`🔍 Grid item ${report.id} name debug:`, {
                  reportName: report.name, 
                  displayName,
                  configName: report.reportConfiguration?.name
                });
                
                // The ReportTask component uses configName as the primary display name
                // We need to pass the report name both as title and as configName to ensure it displays correctly
                const taskData = {
                  id: report.id,
                  type: 'Report',
                  name: '',  // This isn't used directly by ReportTask
                  description: '',
                  scorecard: '',
                  score: '',
                  time: report.updatedAt || report.createdAt || '',
                  data: {
                    id: report.id,
                    title: displayName,  // Used for TaskHeader
                    name: displayName,   // Backup
                    // CRITICAL FIX: ReportTask uses configName as primary display field
                    configName: displayName,  // This is what ReportTask actually displays
                    configDescription: report.reportConfiguration?.description,
                    createdAt: report.createdAt,
                    updatedAt: report.updatedAt
                  },
                  stages: stages,
                  status: report.task?.status as any || 'PENDING',
                  currentStageName: currentStageName
                };
                
                return (
                  <div key={report.id} onClick={clickHandler} className="cursor-pointer">
                    <ReportTask
                      variant="grid"
                      task={taskData}
                      isSelected={report.id === selectedReportId}
                      onClick={clickHandler}
                    />
                  </div>
                );
              })}
              {/* Placeholder for infinite scroll trigger */}
              {nextToken && !isLoading && (
                <div className="col-span-full flex justify-center p-4">
                   <Button variant="outline" onClick={() => accountId && fetchReports(accountId, nextToken)}>Load More</Button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Resizer */}
        {selectedReportId && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 group-hover:bg-accent" />
          </div>
        )}

        {/* Detail Panel (Right side or Fullscreen) */}
        {selectedReportId && !isNarrowViewport && !isFullWidth && (
          <div
            className="h-full overflow-hidden flex-shrink-0"
            style={{ width: `${100 - leftPanelWidth}%` }}
          >
            {renderSelectedReport}
          </div>
        )}

        {selectedReportId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50 bg-background overflow-y-auto">
            {renderSelectedReport}
          </div>
        )}
      </div>

       {/* Share Modal */}
       <ShareResourceModal
          isOpen={isShareModalOpen}
          onClose={handleCloseShareModal}
          onShare={handleCreateShareLink}
          resourceType="Report" // Specify resource type
          shareUrl={shareUrl}
       />
    </div>
  )
}

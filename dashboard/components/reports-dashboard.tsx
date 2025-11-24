"use client"

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
// Import the setup file for its side effects
import "@/components/blocks/registrySetup";
import { motion, AnimatePresence } from "framer-motion"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { FilterInput } from "@/components/FilterInput"
import { X, MoreHorizontal, Trash2, Share, Pencil, Settings } from "lucide-react"
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
import { getValueFromLazyLoader } from '@/utils/data-operations'
import type { LazyLoader } from '@/utils/types'
import { toast } from "sonner"
import { shareLinkClient, ShareLinkViewOptions } from "@/utils/share-link-client"
import { ShareResourceModal } from "@/components/share-resource-modal"
import { ReportsDashboardSkeleton } from "@/components/loading-skeleton"
import ReportTask, { ReportTaskData } from "@/components/ReportTask" // Import ReportTask with its types
import { RunReportButton } from '@/components/task-dispatch' // Import direct button
import ReportConfigurationSelector from "@/components/ReportConfigurationSelector"
import { parseOutputString } from '@/lib/utils'

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

const ACCOUNT_KEY = process.env.NEXT_PUBLIC_PLEXUS_ACCOUNT_KEY || ''

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

// GraphQL query to list reports by report configuration ID and creation timestamp
const LIST_REPORTS_BY_CONFIG = `
  query ListReportByReportConfigurationIdAndCreatedAt(
    $reportConfigurationId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
    $nextToken: String
  ) {
    listReportByReportConfigurationIdAndCreatedAt(
      reportConfigurationId: $reportConfigurationId
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
          type
          output
          log
          attachedFiles
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
      type
      output
      log
      attachedFiles
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
      type
      output
      log
      attachedFiles
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

interface ListReportsByConfigResponse {
  listReportByReportConfigurationIdAndCreatedAt: {
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
  type: string;
  output: Record<string, any>;
  log?: string | null;
  attachedFiles?: string[] | null;
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

  return transformed;
}

export default function ReportsDashboard({
  initialSelectedReportId = null,
}: {
  initialSelectedReportId?: string | null,
} = {}) {
  // Add a useEffect to potentially log when setup runs relative to mount
  useEffect(() => {
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
  const [selectedReportConfiguration, setSelectedReportConfiguration] = useState<string | null>(null); // For filtering by report configuration
  const [selectedReportBlocks, setSelectedReportBlocks] = useState<Array<{
    type: string;
    config: Record<string, any>;
    output: Record<string, any>;
    log?: string;
    name?: string;
    position: number;
  }> | null>(null);
  const [subscriptions, setSubscriptions] = useState<{ unsubscribe: () => void }[]>([]);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);
  const [reportsFilter, setReportsFilter] = useState('');
  
  // Ref map to track report elements for scroll-to-view functionality
  const reportRefsMap = useRef<Map<string, HTMLDivElement | null>>(new Map());
  
  // Function to scroll to a selected report
  const scrollToSelectedReport = useCallback((reportId: string) => {
    // Use requestAnimationFrame to ensure the layout has updated after selection
    requestAnimationFrame(() => {
      const reportElement = reportRefsMap.current.get(reportId);
      if (reportElement) {
        reportElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start', // Align to the top of the container
          inline: 'nearest'
        });
      }
    });
  }, []);

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
  const fetchReports = useCallback(async (currentAccountId: string, currentNextToken: string | null, reportConfigId?: string | null) => {
    if (currentNextToken) {
      setIsLoadingMore(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    try {
      let reportsResponse;
      
      if (reportConfigId) {
        // Fetch reports by report configuration ID
        reportsResponse = await getClient().graphql<ListReportsByConfigResponse>({
          query: LIST_REPORTS_BY_CONFIG,
          variables: {
            reportConfigurationId: reportConfigId,
            sortDirection: 'DESC', // Get newest first
            limit: 20, // Adjust limit as needed
            nextToken: currentNextToken,
          }
        });
        
        if ('data' in reportsResponse && reportsResponse.data?.listReportByReportConfigurationIdAndCreatedAt) {
          const fetchedItems = reportsResponse.data.listReportByReportConfigurationIdAndCreatedAt.items || [];
          const transformedItems = fetchedItems
            .map(transformReportData)
            .filter((item: unknown): item is ReportDisplayData => item !== null);


          setReports(prevReports => currentNextToken ? [...prevReports, ...transformedItems] : transformedItems);
          setNextToken(reportsResponse.data.listReportByReportConfigurationIdAndCreatedAt.nextToken);
        } else {
          setReports(prevReports => currentNextToken ? prevReports : []);
          setNextToken(null);
        }
      } else {
        // Fetch all reports by account ID
        reportsResponse = await getClient().graphql<ListReportsResponse>({
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


          setReports(prevReports => currentNextToken ? [...prevReports, ...transformedItems] : transformedItems);
          setNextToken(reportsResponse.data.listReportByAccountIdAndUpdatedAt.nextToken);
        } else {
          setReports(prevReports => currentNextToken ? prevReports : []);
          setNextToken(null);
        }
      }

      if (!dataHasLoadedOnce) {
        setDataHasLoadedOnce(true);
      }
    } catch (err: any) {
      console.error('Error fetching reports:', err);
      setError(`Error fetching reports: ${err.message}`);
      setReports(prevReports => currentNextToken ? prevReports : []); // Clear on error
      setNextToken(null);
    } finally {
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [dataHasLoadedOnce]); // Dependency array includes dataHasLoadedOnce

  // Add the effect for initial fetch when accountId is available
  useEffect(() => {
    if (accountId && !dataHasLoadedOnce) { // Only fetch initially if data hasn't loaded
      fetchReports(accountId, null, selectedReportConfiguration);
    }
  }, [accountId, dataHasLoadedOnce, selectedReportConfiguration, fetchReports]);

  // Refetch reports when selectedReportConfiguration changes
  useEffect(() => {
    if (accountId && dataHasLoadedOnce) {
      // Reset pagination and fetch new data
      setNextToken(null);
      fetchReports(accountId, null, selectedReportConfiguration);
    }
  }, [selectedReportConfiguration, accountId, dataHasLoadedOnce, fetchReports]);

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

    const subscriptionHandlers: { unsubscribe: () => void }[] = [];

    // Subscribe to new report creations
    try {
      const createReportSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_CREATE_REPORT,
        variables: { accountId }
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateReport: any } }) => {
          if (data?.onCreateReport) {
            const newReport = data.onCreateReport;
            
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
                id: newReport.reportConfiguration!.id,
                name: newReport.reportConfiguration!.name,
                description: newReport.reportConfiguration!.description
              } : null,
              task: newReport.task || null
            };
            
            
            // Use the manual transformation to ensure name is preserved
            setReports(prevReports => {
              const newReports = [manualTransformedReport, ...prevReports];
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
          if (data?.onUpdateReport) {
            const updatedReport = data.onUpdateReport;
            // Cast to any to avoid type issues with transformReportData
            const transformedReport = transformReportData(updatedReport as any);
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
            outputData = typeof block.output === 'string' ? parseOutputString(block.output) : block.output;
          } catch (err) {
            console.error('Error parsing block output:', err);
            outputData = block.output || {};
          }
          
          return {
            type: block.type || outputData.class || 'unknown', // Use API type first, then output.class as fallback
            config: outputData, // Use output as config
            output: outputData,
            log: block.log || undefined,
            name: block.name || undefined,
            position: block.position,
            attachedFiles: block.attachedFiles || undefined
          };
        });
        
        // Important log to verify block count
        
        // Force a state update by creating a new array
        setSelectedReportBlocks([...transformedBlocks]);
        
        // Create a new snapshot of the reports array with the updated report
        // This forces a re-render of the component tree
        setReports(prevReports => {
          return prevReports.map(r => {
            if (r.id === reportId) {
              // Keep this log to verify the report is being updated
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

    const blockSubscriptionHandlers: { unsubscribe: () => void }[] = [];

    // Subscribe to new report block creations
    try {
      const createBlockSubscription = (getClient().graphql({
        query: SUBSCRIBE_ON_CREATE_REPORT_BLOCK
      }) as unknown as { subscribe: Function }).subscribe({
        next: ({ data }: { data?: { onCreateReportBlock: { id: string, reportId: string, name?: string, position: number, output: any, log?: string } } }) => {
          // Important log to verify subscription is receiving events
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
      subscriptions.forEach(subscription => {
        try {
          subscription.unsubscribe();
        } catch (err) {
          console.error('Error unsubscribing on unmount:', err);
        }
      });
    };
  }, [subscriptions]);

  // Infinite scroll effect using Intersection Observer
  useEffect(() => {
    const currentRef = loadMoreRef.current;
    if (!currentRef || !nextToken || isLoadingMore || !accountId) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const first = entries[0];
        if (first.isIntersecting && !isLoadingMore) {
          fetchReports(accountId, nextToken, selectedReportConfiguration);
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(currentRef);

    return () => {
      if (currentRef) {
        observer.unobserve(currentRef);
      }
    };
  }, [nextToken, isLoadingMore, accountId, selectedReportConfiguration, fetchReports]);

  // Handle deep linking and browser navigation (similar to evaluations)
  useEffect(() => {
    const evalMatch = pathname.match(/\/lab\/reports\/([^\/]+)/);
    const idFromUrl = evalMatch ? evalMatch[1] : null;
    
    // This is the key change: we need to check explicitly if idFromUrl is null
    if (idFromUrl && idFromUrl !== selectedReportId) {
      setSelectedReportId(idFromUrl);
    } else if (!idFromUrl && selectedReportId !== null) {
      // Clear selectedReportId when URL no longer has a report ID
      setSelectedReportId(null);
      setIsFullWidth(false);
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
      
      // Scroll to the selected report after a brief delay to allow layout updates
      if (id) {
        setTimeout(() => {
          scrollToSelectedReport(id);
        }, 100);
      }
      
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

  // Delete handler
  const handleDelete = async (reportId: string) => {
    try {
      
      const currentClient = getClient();
      await currentClient.graphql({
        query: `
          mutation DeleteReport($input: DeleteReportInput!) {
            deleteReport(input: $input) {
              id
            }
          }
        `,
        variables: { 
          input: {
            id: reportId
          }
        }
      });
      
      // Remove the deleted report from the reports state
      setReports(prev => prev.filter(r => r.id !== reportId));
      
      // If currently selected report is deleted, close the detail view
      if (selectedReportId === reportId) {
        handleCloseReport();
      }
      
      toast.success("Report deleted successfully");
      return true;
    } catch (error) {
      console.error("Error deleting report:", error);
      toast.error("Failed to delete report", {
        description: "An unexpected error occurred."
      });
      return false;
    }
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
    }
  }, [reports]);

  // Memoized rendering of the selected report's details
  const renderSelectedReport = useMemo(() => {
    if (!selectedReportId) return null;
    const report = reports.find(r => r.id === selectedReportId);
    if (!report) return null; // Report might not be loaded yet

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
               <Button 
                 variant="ghost" 
                 size="icon" 
                 className="h-8 w-8 rounded-md bg-border"
                 aria-label="More options"
               >
                 <MoreHorizontal className="h-4 w-4" />
               </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
               <DropdownMenuItem onClick={() => copyLinkToClipboard(report.id)}>
                <Share className="mr-2 h-4 w-4" />
                <span>Share</span>
              </DropdownMenuItem>
              {report.reportConfiguration?.id && (
                <DropdownMenuItem onClick={() => router.push(`/lab/reports/edit/${report.reportConfiguration!.id}`)}>
                  <Settings className="mr-2 h-4 w-4" />
                  <span>Edit Configuration</span>
                </DropdownMenuItem>
              )}
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
        <ReportsDashboardSkeleton />
      </div>
    )
  }

  if (error && !dataHasLoadedOnce) { // Show error prominently if initial load failed
    return (
      <div className="space-y-4 p-4">
        <h1 className="text-2xl font-bold">Reports</h1>
        <div className="text-sm text-destructive">Error fetching reports: {error}</div>
        <Button onClick={() => accountId && fetchReports(accountId, null, selectedReportConfiguration)}>Retry</Button>
      </div>
    )
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="flex gap-2 items-center flex-wrap">
          <ReportConfigurationSelector
            selectedReportConfiguration={selectedReportConfiguration}
            setSelectedReportConfiguration={setSelectedReportConfiguration}
          />
          <FilterInput
            placeholder="Filter..."
            onFilterChange={setReportsFilter}
          />
        </div>

        {/* Buttons on top right */}
        <div className="flex-shrink-0 flex gap-2">
          <Button
            onClick={() => router.push('/lab/reports/edit')}
            variant="ghost"
            className="bg-card hover:bg-accent text-muted-foreground whitespace-nowrap"
          >
            <Pencil className="mr-2 h-4 w-4"/> Edit Configurations
          </Button>
          <RunReportButton />
        </div>
      </div>
      {error && <p className="text-xs text-destructive pb-2">{error}</p>}

      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        {/* Content area - uses the same base structure */}
        <div className="flex flex-1 min-h-0">
          {/* Left panel - grid content */}
          <motion.div 
            className="h-full overflow-auto overflow-x-visible"
            animate={{
              width: selectedReportId && !isNarrowViewport && isFullWidth 
                ? 0 
                : selectedReportId && !isNarrowViewport && !isFullWidth 
                  ? `${leftPanelWidth}%`
                  : '100%'
            }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            style={{
              flexShrink: 0,
              overflow: selectedReportId && !isNarrowViewport && isFullWidth ? 'hidden' : 'auto'
            }}
          >
            {/* Grid content or report detail for mobile */}
            <div className="@container space-y-3 overflow-visible">
              {isNarrowViewport && selectedReportId ? (
                // Mobile full-screen report view
                <div className="h-full">
                  {renderSelectedReport}
                </div>
              ) : (
                // Grid view
                <>
                  {!isLoading && reports.length === 0 && !error && (
                    <div className="text-sm text-muted-foreground p-4 text-center">No reports found for this account.</div>
                  )}
                  {reports.length > 0 && (
                    <motion.div 
                      className="grid grid-cols-1 gap-3"
                      layout
                      transition={{
                        layout: {
                          type: "spring",
                          stiffness: 300,
                          damping: 30,
                          duration: 0.6
                        }
                      }}
                    >
                      <AnimatePresence mode="popLayout">
                        {reports
                          .filter(report =>
                            !reportsFilter || (report.name && report.name.toLowerCase().includes(reportsFilter.toLowerCase()))
                          )
                          .map((report) => {
                          const clickHandler = getReportClickHandler(report.id);
                          
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
                            <motion.div
                              key={report.id}
                              layoutId={`report-${report.id}`}
                              layout
                              initial={{ opacity: 0 }}
                              animate={{ opacity: 1 }}
                              exit={{ 
                                opacity: 0,
                                transition: { duration: 0.2 }
                              }}
                              transition={{
                                layout: {
                                  type: "spring",
                                  stiffness: 300,
                                  damping: 30
                                },
                                opacity: { duration: 0.4 }
                              }}
                              onClick={clickHandler} 
                              className="cursor-pointer"
                              ref={(el) => {
                                reportRefsMap.current.set(report.id, el);
                              }}
                            >
                              <ReportTask
                                variant="grid"
                                task={taskData}
                                isSelected={report.id === selectedReportId}
                                onClick={clickHandler}
                                controlButtons={
                                  <DropdownMenu>
                                    <DropdownMenuTrigger asChild>
                                       <Button 
                                         variant="ghost" 
                                         size="icon" 
                                         className="h-8 w-8 rounded-md bg-border hover:bg-accent"
                                         aria-label="More options"
                                         onClick={(e) => e.stopPropagation()} // Prevent card click when clicking dropdown
                                       >
                                         <MoreHorizontal className="h-4 w-4" />
                                       </Button>
                                    </DropdownMenuTrigger>
                                    <DropdownMenuContent align="end">
                                       <DropdownMenuItem onClick={(e) => { e.stopPropagation(); copyLinkToClipboard(report.id); }}>
                                        <Share className="mr-2 h-4 w-4" />
                                        <span>Share</span>
                                      </DropdownMenuItem>
                                      {report.reportConfiguration?.id && (
                                        <DropdownMenuItem onClick={(e) => { e.stopPropagation(); router.push(`/lab/reports/edit/${report.reportConfiguration!.id}`); }}>
                                          <Settings className="mr-2 h-4 w-4" />
                                          <span>Edit Configuration</span>
                                        </DropdownMenuItem>
                                      )}
                                      <DropdownMenuItem onClick={(e) => { e.stopPropagation(); handleDelete(report.id); }}>
                                        <Trash2 className="mr-2 h-4 w-4" />
                                        <span>Delete</span>
                                      </DropdownMenuItem>
                                    </DropdownMenuContent>
                                  </DropdownMenu>
                                }
                              />
                            </motion.div>
                          );
                        })}
                        {/* Infinite scroll trigger and loading indicator */}
                        {nextToken && (
                          <div className="col-span-full">
                            {/* Invisible trigger element for intersection observer */}
                            <div ref={loadMoreRef} className="h-4" />
                            {/* Loading indicator */}
                            {isLoadingMore && (
                              <div className="flex justify-center p-4">
                                <div className="text-sm text-muted-foreground">Loading more reports...</div>
                              </div>
                            )}
                          </div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )}
                </>
              )}
            </div>
          </motion.div>

          {/* Divider for split view */}
          {selectedReportId && !isNarrowViewport && !isFullWidth && (
            <div
              className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
              onMouseDown={handleDragStart}
            >
              <div className="absolute inset-0 rounded-full transition-colors duration-150 
                group-hover:bg-accent" />
            </div>
          )}

          {/* Right panel - report detail view */}
          <AnimatePresence>
            {selectedReportId && !isNarrowViewport && (
              <motion.div
                key={`report-${selectedReportId}-solo`}
                initial={{ x: '100%', opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: '100%', opacity: 0 }}
                transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                className="h-full overflow-hidden"
                style={{ 
                  width: isFullWidth 
                    ? '100%' 
                    : `${100 - leftPanelWidth}%` 
                }}
              >
                {renderSelectedReport}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Share Modal */}
      <ShareResourceModal
        isOpen={isShareModalOpen}
        onClose={handleCloseShareModal}
        onShare={handleCreateShareLink}
        resourceType="Report"
        shareUrl={shareUrl}
      />
    </div>
  )
}

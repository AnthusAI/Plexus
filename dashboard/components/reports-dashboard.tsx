"use client"

import React, { useState, useEffect, useMemo, useCallback, useRef } from "react"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, MoreHorizontal, Trash2, Share, Pencil } from "lucide-react"
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
import type { GraphQLResult } from '@aws-amplify/api'
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
  icon: Pencil,
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

  return {
    id: report.id,
    name: report.name || (configInfo?.name) || `Report ${report.id.substring(0, 6)}`,
    createdAt: report.createdAt,
    updatedAt: report.updatedAt,
    reportConfiguration: configInfo,
    task: taskData as Task | null
  };
}

export default function ReportsDashboard({
  initialSelectedReportId = null,
}: {
  initialSelectedReportId?: string | null,
} = {}) {
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

  // Trigger initial fetch when accountId is available
  useEffect(() => {
    if (accountId && !dataHasLoadedOnce) { // Only fetch initially if data hasn't loaded
      fetchReports(accountId, null);
    }
  }, [accountId, dataHasLoadedOnce, fetchReports]); // Add fetchReports to dependencies


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

  // Memoized rendering of the selected report's details
  const renderSelectedReport = useMemo(() => {
    if (!selectedReportId) return null;
    const report = reports.find(r => r.id === selectedReportId);
    if (!report) return null; // Report might not be loaded yet

    console.log('Rendering selected report:', report);

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
            title: report.name || 'Report',
            name: report.name,
            configName: report.reportConfiguration?.name,
            configDescription: report.reportConfiguration?.description,
            createdAt: report.createdAt,
            updatedAt: report.updatedAt
          },
          stages: stages,
          status: report.task?.status as any || 'PENDING',
          currentStageName: currentStageName,
          errorMessage: report.task?.errorMessage || undefined
        }}
        onClick={() => {}} // No-op for detail view
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
      />
    );
  }, [selectedReportId, reports, isFullWidth, handleCloseReport, handleDelete, copyLinkToClipboard]); // Dependencies

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
          {/* Placeholder for Filters/Context */}
          <div>
            <h1 className="text-xl font-semibold">Reports</h1>
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          {/* Placeholder for Generate Button - Requires Report Config Selection */}
          {/* <TaskDispatchButton config={reportsConfig} context={{ reportConfigurationId: 'some-config-id' }}/> */}
          <Button disabled>
             <Pencil className="mr-2 h-4 w-4"/> Generate Report
          </Button>
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
                
                return (
                  <div key={report.id} onClick={clickHandler} className="cursor-pointer">
                    <ReportTask
                      variant="grid"
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
                          title: report.name || 'Report',
                          name: report.name,
                          configName: report.reportConfiguration?.name,
                          configDescription: report.reportConfiguration?.description,
                          createdAt: report.createdAt,
                          updatedAt: report.updatedAt
                        },
                        stages: stages,
                        status: report.task?.status as any || 'PENDING',
                        currentStageName: currentStageName
                      }}
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

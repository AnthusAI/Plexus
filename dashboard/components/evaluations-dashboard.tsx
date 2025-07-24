"use client"
import React from "react"
import { useState, useEffect, useMemo, useCallback, useRef } from "react"
import { useInView } from 'react-intersection-observer'
import { motion, AnimatePresence } from "framer-motion"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Square, Columns2, X, ChevronDown, ChevronUp, Info, MessageCircleMore, Plus, ThumbsUp, ThumbsDown, Trash2, MoreHorizontal, Eye, RefreshCw, Share, MessageSquareCode } from "lucide-react"
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
import { TimeRangeSelector } from "@/components/time-range-selector"
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion"
import ReactMarkdown from 'react-markdown'
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import Link from 'next/link'
import { FilterControl, FilterConfig } from "@/components/filter-control"
import { Progress } from "@/components/ui/progress"
import ScorecardContext from "@/components/ScorecardContext"
import { EvaluationDashboardSkeleton } from "@/components/loading-skeleton"
import { ModelListResult, AmplifyListResult, AmplifyGetResult } from '@/types/shared'
import { listFromModel, observeQueryFromModel, getFromModel, observeScoreResults } from "@/utils/amplify-helpers"
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter, useParams, usePathname } from 'next/navigation'
import { Observable } from 'rxjs'
import { getClient } from '@/utils/amplify-client'
import type { GraphQLResult, GraphQLSubscription } from '@aws-amplify/api'
import { TaskDispatchButton, evaluationsConfig } from '@/components/task-dispatch'
import { EvaluationCard, EvaluationGrid } from '@/features/evaluations'
import { useEvaluationSubscriptions, useTaskUpdates } from '@/features/evaluations'
import { formatStatus, getBadgeVariant, calculateProgress } from '@/features/evaluations'
import EvaluationTask from '@/components/EvaluationTask'
import { useMediaQuery } from "@/hooks/use-media-query"
import { CardButton } from "@/components/CardButton"
import { GraphQLResult as APIGraphQLResult } from '@aws-amplify/api-graphql'
import type { EvaluationTaskProps } from '@/components/EvaluationTask'
import type { TaskData } from '@/types/evaluation'
import { transformAmplifyTask } from '@/utils/data-operations'
import { AmplifyTask, ProcessedTask, Evaluation, TaskStageType, TaskSubscriptionEvent } from '@/utils/data-operations'
import { listRecentEvaluations, transformAmplifyTask as transformEvaluationData, standardizeScoreResults } from '@/utils/data-operations'
import { TaskDisplay } from "@/components/TaskDisplay"
import { getValueFromLazyLoader, unwrapLazyLoader } from '@/utils/data-operations'
import type { LazyLoader } from '@/utils/types'
import { observeRecentEvaluations, observeTaskUpdates, observeTaskStageUpdates } from '@/utils/subscriptions'
import { useEvaluationData } from '@/features/evaluations/hooks/useEvaluationData'
import { toast } from "sonner"
import { shareLinkClient, ShareLinkViewOptions } from "@/utils/share-link-client"
import { fetchAuthSession } from 'aws-amplify/auth'
import { ShareResourceModal } from "@/components/share-resource-modal"
import { EvaluationTasksGauges } from './EvaluationTasksGauges'

type TaskResponse = {
  items: Evaluation[]
  nextToken: string | null
}

type ScoreResultItem = {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  explanation?: string | null;
  trace?: any | null;
  itemId: string | null;
  createdAt?: string;
};

interface TaskStagesResponse {
  data?: {
    items: TaskStageType[];
  };
}

interface ScoreResultsResponse {
  items?: ScoreResult[];
}

interface RawTask {
  id: string;
  type: string;
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
  target: string;
  command: string;
  description?: string;
  dispatchStatus?: string;
  metadata?: any;
  createdAt?: string;
  startedAt?: string;
  completedAt?: string;
  estimatedCompletionAt?: string;
  errorMessage?: string;
  errorDetails?: any;
  currentStageId?: string;
  stages?: {
    data?: {
      items: TaskStageType[];
    };
  };
  celeryTaskId?: string;
  workerNodeId?: string;
}

interface RawTaskData {
  data?: RawTask;
}

const ACCOUNT_KEY = 'call-criteria'

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

const LIST_EVALUATIONS = `
  query ListEvaluationByAccountIdAndUpdatedAt(
    $accountId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
  ) {
    listEvaluationByAccountIdAndUpdatedAt(
      accountId: $accountId
      sortDirection: $sortDirection
      limit: $limit
    ) {
      items {
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
            feedbackItem {
              id
              editCommentValue
              initialAnswerValue
              finalAnswerValue
              editorName
              editedAt
            }
          }
        }
      }
      nextToken
    }
  }
`

interface GraphQLError {
  message: string;
  path?: string[];
}

interface ListAccountResponse {
  listAccounts: {
    items: Array<{
      id: string;
      key: string;
    }>;
  };
}

interface ListEvaluationResponse {
  listEvaluationByAccountIdAndUpdatedAt: {
    items: Schema['Evaluation']['type'][];
    nextToken: string | null;
  };
}

interface ScoreResult {
  id: string;
  value: string | number;
  confidence: number | null;
  metadata: any;
  explanation?: string | null;
  trace?: any | null;
  itemId: string | null;
  createdAt?: string;
}

export function transformEvaluation(evaluation: Schema['Evaluation']['type']) {
  console.debug('transformEvaluation input:', {
    evaluationId: evaluation?.id,
    hasTask: !!evaluation?.task,
    taskType: typeof evaluation?.task,
    taskData: evaluation?.task,
    taskKeys: evaluation?.task ? Object.keys(evaluation.task) : [],
    status: evaluation?.status,
    type: evaluation?.type
  });

  if (!evaluation) return null;

  // Unwrap the lazy loader and cast task data properly
  const rawTask = getValueFromLazyLoader(evaluation.task);
  // Cast through unknown first to avoid type overlap errors
  const taskData = ((rawTask ? rawTask : evaluation.task) as any) as AmplifyTask & { stages?: any };
  if (!taskData) {
    console.debug('No task data found in evaluation:', {
      evaluationId: evaluation.id,
      status: evaluation.status,
      type: evaluation.type
    });
  }

  // Get the score results
  const scoreResults = evaluation.scoreResults as unknown as {
    items?: Array<{
      id: string;
      value: string | number;
      confidence: number | null;
      metadata: any;
      itemId: string | null;
    }>;
  } | null;

  // Helper function to transform stages
  const transformStages = (stages: any): { items: TaskStageType[] } | undefined => {
    if (!stages) return undefined;

    // Get the items array from either format
    const stageItems = (stages.data && Array.isArray(stages.data.items)) ? stages.data.items : 
                      (Array.isArray(stages.items) ? stages.items : []);

    // Transform the stages without an extra nesting level
    return {
      items: stageItems.map((stage: any) => ({
        id: stage.id,
        name: stage.name,
        order: stage.order,
        status: stage.status,
        processedItems: stage.processedItems,
        totalItems: stage.totalItems,
        startedAt: stage.startedAt,
        completedAt: stage.completedAt,
        estimatedCompletionAt: stage.estimatedCompletionAt,
        statusMessage: stage.statusMessage
      }))
    };
  };

  // Transform score results to include trace field
  const transformScoreResults = (scoreResults: any) => {
    if (!scoreResults) return null;
    
    // Handle items array
    if (typeof scoreResults === 'object' && 'items' in scoreResults && Array.isArray(scoreResults.items)) {
      return {
        items: scoreResults.items.map((item: any) => ({
          id: item.id,
          value: item.value,
          confidence: item.confidence,
          metadata: item.metadata,
          explanation: item.explanation,
          trace: item.trace,
          itemId: item.itemId,
          createdAt: item.createdAt
        }))
      };
    }
    
    return scoreResults;
  };

  // Get stages from task data
  const rawStages = taskData?.stages;
  const transformedStages = transformStages(rawStages);

  console.debug('Processing evaluation data:', {
    evaluationId: evaluation.id,
    hasTaskData: !!taskData,
    taskType: typeof taskData,
    taskKeys: taskData ? Object.keys(taskData) : [],
    hasScoreResults: !!scoreResults?.items?.length,
    rawStages,
    rawStagesType: typeof rawStages,
    rawStagesKeys: rawStages ? Object.keys(rawStages) : [],
    rawStagesData: rawStages?.data,
    rawStagesItems: rawStages?.items,
    transformedStages,
    transformedStagesCount: transformedStages?.items?.length
  });

  // Transform the evaluation into the format expected by components
  const transformedEvaluation: Evaluation = {
    id: evaluation.id,
    type: evaluation.type,
    scorecard: evaluation.scorecard,
    score: evaluation.score,
    createdAt: evaluation.createdAt,
    metrics: typeof evaluation.metrics === 'string' ? 
      JSON.parse(evaluation.metrics) : evaluation.metrics,
    metricsExplanation: evaluation.metricsExplanation,
    accuracy: evaluation.accuracy,
    processedItems: evaluation.processedItems,
    totalItems: evaluation.totalItems,
    inferences: evaluation.inferences,
    cost: evaluation.cost,
    status: evaluation.status,
    elapsedSeconds: evaluation.elapsedSeconds,
    estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds,
    startedAt: evaluation.startedAt,
    errorMessage: evaluation.errorMessage,
    errorDetails: evaluation.errorDetails,
    confusionMatrix: typeof evaluation.confusionMatrix === 'string' ? 
      JSON.parse(evaluation.confusionMatrix) : evaluation.confusionMatrix,
    datasetClassDistribution: typeof evaluation.datasetClassDistribution === 'string' ?
      JSON.parse(evaluation.datasetClassDistribution) : evaluation.datasetClassDistribution,
    isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
    predictedClassDistribution: typeof evaluation.predictedClassDistribution === 'string' ?
      JSON.parse(evaluation.predictedClassDistribution) : evaluation.predictedClassDistribution,
    isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
    task: taskData ? ({
      ...taskData,
      stages: transformedStages
    } as AmplifyTask) : null,
    scoreResults: transformScoreResults(scoreResults)
  };

  console.debug('Final transformed evaluation:', {
    evaluationId: transformedEvaluation.id,
    hasTask: !!transformedEvaluation.task,
    taskType: typeof transformedEvaluation.task,
    taskKeys: transformedEvaluation.task ? Object.keys(transformedEvaluation.task) : [],
    taskStages: transformedEvaluation.task?.stages
  });

  return transformedEvaluation;
}

export default function EvaluationsDashboard({ 
  initialSelectedEvaluationId = null,
  initialSelectedScoreResultId = null
}: { 
  initialSelectedEvaluationId?: string | null,
  initialSelectedScoreResultId?: string | null
} = {}) {
  const { user } = useAuthenticator()
  const router = useRouter()
  const pathname = usePathname()
  const params = useParams()
  const [accountId, setAccountId] = useState<string | null>(null)
  const [selectedEvaluationId, setSelectedEvaluationId] = useState<string | null>(initialSelectedEvaluationId)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const [accountError, setAccountError] = useState<string | null>(null)
  const [dataHasLoadedOnce, setDataHasLoadedOnce] = useState(false)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })
  const [selectedScoreResultId, setSelectedScoreResultId] = useState<string | null>(initialSelectedScoreResultId)
  const [isShareModalOpen, setIsShareModalOpen] = useState(false)
  const [shareUrl, setShareUrl] = useState<string | null>(null)
  
  // Ref map to track evaluation elements for scroll-to-view functionality
  const evaluationRefsMap = useRef<Map<string, HTMLDivElement | null>>(new Map())
  
  // Function to scroll to a selected evaluation
  const scrollToSelectedEvaluation = useCallback((evaluationId: string) => {
    // Use requestAnimationFrame to ensure the layout has updated after selection
    requestAnimationFrame(() => {
      const evaluationElement = evaluationRefsMap.current.get(evaluationId);
      if (evaluationElement) {
        evaluationElement.scrollIntoView({
          behavior: 'smooth',
          block: 'start', // Align to the top of the container
          inline: 'nearest'
        });
      }
    });
  }, []);
  
  // Add this handler
  const handleScoreResultSelect = useCallback((id: string | null) => {
    setSelectedScoreResultId(id);
    
    // Update URL without triggering a navigation/re-render
    if (selectedEvaluationId) {
      const newPathname = id 
        ? `/lab/evaluations/${selectedEvaluationId}/score-results/${id}` 
        : `/lab/evaluations/${selectedEvaluationId}`;
      window.history.pushState(null, '', newPathname);
    }
  }, [selectedEvaluationId]);

  const copyLinkToClipboard = () => {
    if (!selectedEvaluationId || !accountId) return;
    setIsShareModalOpen(true);
  }

  // Handle deep linking - check if we're on the main evaluations page or a specific evaluation page
  useEffect(() => {
    // If we have an ID in the URL and we're on the main evaluations page
    if (params && 'id' in params) {
      // Set the evaluation ID
      setSelectedEvaluationId(params.id as string);
      
      // If we also have a score result ID, set that too
      if ('scoreResultId' in params) {
        setSelectedScoreResultId(params.scoreResultId as string);
      }
    }
  }, [params]);

  // Handle browser back/forward navigation with popstate event
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // Extract evaluation ID from URL if present
      const evalMatch = window.location.pathname.match(/\/lab\/evaluations\/([^\/]+)/);
      const idFromUrl = evalMatch ? evalMatch[1] : null;
      
      // Extract score result ID from URL if present
      const scoreResultMatch = window.location.pathname.match(/\/lab\/evaluations\/[^\/]+\/score-results\/([^\/]+)/);
      const scoreResultIdFromUrl = scoreResultMatch ? scoreResultMatch[1] : null;
      
      // Update the selected evaluation ID based on the URL
      setSelectedEvaluationId(idFromUrl);
      
      // Update the selected score result ID based on the URL
      setSelectedScoreResultId(scoreResultIdFromUrl);
    };

    // Add event listener for popstate (browser back/forward)
    window.addEventListener('popstate', handlePopState);
    
    // Clean up event listener on unmount
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, []);

  // Custom setter for selectedEvaluationId that handles both state and URL
  const handleSelectEvaluation = (id: string | null) => {
    // Only update state if the selected evaluation has changed
    if (id !== selectedEvaluationId) {
      setSelectedEvaluationId(id);
      
      // Clear the selected score result when changing evaluations
      setSelectedScoreResultId(null);
      
      // Update URL without triggering a navigation/re-render
      const newPathname = id ? `/lab/evaluations/${id}` : '/lab/evaluations';
      window.history.pushState(null, '', newPathname);
    }
  };

  // Handle closing the selected evaluation
  const handleCloseEvaluation = () => {
    console.log('handleCloseEvaluation called, clearing selectedEvaluationId:', selectedEvaluationId);
    setSelectedEvaluationId(null);
    setSelectedScoreResultId(null);
    setIsFullWidth(false);
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/evaluations');
  };

  // Fetch account ID
  useEffect(() => {
    const fetchAccountId = async () => {
      try {
        console.log('Fetching account ID...')
        const accountResponse = await getClient().graphql<ListAccountResponse>({
          query: LIST_ACCOUNTS,
          variables: {
            filter: { key: { eq: ACCOUNT_KEY } }
          }
        })

        if ('data' in accountResponse && accountResponse.data?.listAccounts?.items?.length) {
          const id = accountResponse.data.listAccounts.items[0].id
          console.log('Found account ID:', id)
          setAccountId(id)
        } else {
          console.warn('No account found with key:', ACCOUNT_KEY)
          setAccountError('No account found')
        }
      } catch (error) {
        console.error('Error fetching account:', error)
        setAccountError('Error fetching account')
      }
    }
    fetchAccountId()
  }, [])

  // Use the new hook for evaluation data
  const { evaluations, isLoading, error, refetch } = useEvaluationData({ 
    accountId,
    selectedScorecard,
    selectedScore
  });

  // Debug logging for scorecard and score selection
  useEffect(() => {
    console.debug('Evaluations dashboard filters:', {
      selectedScorecard,
      selectedScore,
      evaluationsCount: evaluations.length
    });
  }, [selectedScorecard, selectedScore, evaluations.length]);

  // Set dataHasLoadedOnce to true once data has loaded
  useEffect(() => {
    if (!isLoading && evaluations.length > 0 && !dataHasLoadedOnce) {
      setDataHasLoadedOnce(true);
    }
  }, [isLoading, evaluations, dataHasLoadedOnce]);

  // Refetch evaluations when filters change
  useEffect(() => {
    if (accountId) {
      refetch();
    }
  }, [accountId, selectedScorecard, selectedScore, refetch]);

  // Show loading state only on initial load, not when selecting evaluations
  const showLoading = isLoading && !dataHasLoadedOnce;

  // Combine errors from account fetching and evaluation data
  const combinedError = accountError || error;

  const handleDelete = async (evaluationId: string) => {
    try {
      const currentClient = getClient()
      await currentClient.graphql({
        query: `
          mutation DeleteEvaluation($input: DeleteEvaluationInput!) {
            deleteEvaluation(input: $input) {
              id
            }
          }
        `,
        variables: { 
          input: {
            id: evaluationId
          }
        }
      })
      if (selectedEvaluationId === evaluationId) {
        setSelectedEvaluationId(null)
      }
      return true
    } catch (error) {
      console.error('Error deleting evaluation:', error)
      return false
    }
  }

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

  // Memoize the renderSelectedTask function to prevent unnecessary re-renders
  const renderSelectedTask = useMemo(() => {
    if (!selectedEvaluationId) return null;
    const evaluation = evaluations.find((e: { id: string }) => e.id === selectedEvaluationId);
    if (!evaluation) return null;

    console.log('Rendering selected task:', {
      evaluationId: evaluation.id,
      hasScoreResults: !!evaluation.scoreResults,
      scoreResultsType: typeof evaluation.scoreResults,
      scoreResultsIsArray: Array.isArray(evaluation.scoreResults),
      scoreResultsCount: Array.isArray(evaluation.scoreResults) ? evaluation.scoreResults.length : 
                        (evaluation.scoreResults && typeof evaluation.scoreResults === 'object' && 'items' in evaluation.scoreResults ? 
                         (evaluation.scoreResults as any).items.length : 0),
      firstScoreResult: Array.isArray(evaluation.scoreResults) ? evaluation.scoreResults[0] : 
                       (evaluation.scoreResults && typeof evaluation.scoreResults === 'object' && 'items' in evaluation.scoreResults ? 
                        (evaluation.scoreResults as any).items[0] : undefined)
    });

    return (
      <TaskDisplay
        variant="detail"
        task={evaluation.task}
        evaluationData={{
          ...evaluation,
          // Pass the raw score results - they will be standardized in the components
          scoreResults: evaluation.scoreResults
        }}

        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseEvaluation}
        selectedScoreResultId={selectedScoreResultId}
        onSelectScoreResult={handleScoreResultSelect}
        onShare={copyLinkToClipboard}
        onDelete={handleDelete}
      />
    );
  }, [selectedEvaluationId, evaluations, isFullWidth, selectedScoreResultId, handleScoreResultSelect, copyLinkToClipboard, handleDelete, handleCloseEvaluation]);

  // Remove client-side filtering logic and use the filtered evaluations directly
  const filteredEvaluations = evaluations;

  const handleCreateShareLink = async (expiresAt: string, viewOptions: ShareLinkViewOptions) => {
    if (!selectedEvaluationId || !accountId) return;
    
    try {
      // Create a share link for the evaluation using shareLinkClient
      const { url } = await shareLinkClient.create({
        resourceType: 'Evaluation',
        resourceId: selectedEvaluationId,
        accountId: accountId,
        expiresAt,
        viewOptions
      });
      
      // Ensure URL is valid before attempting to copy
      if (!url) throw new Error("Generated URL is empty");
      
      // Store the URL in state
      setShareUrl(url);
      
      try {
        // Check for clipboard permissions first
        if (navigator.permissions && navigator.permissions.query) {
          const permissionStatus = await navigator.permissions.query({ name: 'clipboard-write' as PermissionName });
          if (permissionStatus.state === 'denied') {
            throw new Error("Clipboard permission denied");
          }
        }
        
        // Copy with proper await
        await navigator.clipboard.writeText(url);
        
        toast.success("Share link created and copied to clipboard", {
          description: "You can now share this evaluation with others"
        });
        
        // Close the modal after successful copy
        setIsShareModalOpen(false);
        
      } catch (clipboardError) {
        console.error("Clipboard error:", clipboardError);
        
        // Keep the share modal open so user can see and copy the URL
        toast.warning("Created share link, but couldn't copy to clipboard", {
          description: "The link is available in the share dialog",
          duration: 5000
        });
        
        // Keep the share modal open so user can see and copy the URL
        console.log("Setting modal to stay open after clipboard error");
        setIsShareModalOpen(true);
      }
    } catch (error) {
      console.error("Error creating share link:", error);
      toast.error("Failed to create share link", {
        description: "An error occurred while creating the share link"
      });
    }
  }

  // Update the modal close handler to be simpler since we're handling cleanup in the modal component
  const handleCloseShareModal = useCallback(() => {
    setIsShareModalOpen(false);
    setShareUrl(null); // Clear the share URL when closing the modal
  }, []);

  // Memoize the click handler for each evaluation to prevent unnecessary re-renders
  const getEvaluationClickHandler = useCallback((evaluationId: string) => {
    return (e?: React.MouseEvent | React.SyntheticEvent | any) => {
      // Prevent default if it's an event object
      if (e && typeof e.preventDefault === 'function') {
        e.preventDefault();
      }
      
      if (evaluationId !== selectedEvaluationId) {
        // Update state first
        setSelectedEvaluationId(evaluationId);
        
        // Clear the selected score result when changing evaluations
        setSelectedScoreResultId(null);
        
        // Then update URL without triggering a navigation/re-render
        const newPathname = `/lab/evaluations/${evaluationId}`;
        window.history.pushState(null, '', newPathname);
        
        // Scroll to the selected evaluation after a brief delay to allow layout updates
        setTimeout(() => {
          scrollToSelectedEvaluation(evaluationId);
        }, 100);
        
        if (isNarrowViewport) {
          setIsFullWidth(true);
        }
      }
    };
  }, [selectedEvaluationId, isNarrowViewport, scrollToSelectedEvaluation]);

  if (showLoading) {
    return (
      <div>
        <div className="mb-4 text-sm text-muted-foreground">
          {combinedError ? `Error: ${combinedError}` : ''}
        </div>
        <EvaluationDashboardSkeleton />
      </div>
    )
  }

  if (combinedError) {
    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center">
          <h1 className="text-2xl font-bold">Evaluations</h1>
        </div>
        <div className="text-sm text-destructive">Error: {combinedError}</div>
      </div>
    )
  }

  return (
    <div className="@container flex flex-col h-full p-3 overflow-hidden">
      {/* Fixed header */}
      <div className="flex @[600px]:flex-row flex-col @[600px]:items-center @[600px]:justify-between items-stretch gap-3 pb-3 flex-shrink-0">
        <div className="@[600px]:flex-grow w-full">
          <ScorecardContext 
            selectedScorecard={selectedScorecard}
            setSelectedScorecard={setSelectedScorecard}
            selectedScore={selectedScore}
            setSelectedScore={setSelectedScore}
            skeletonMode={showLoading}
          />
        </div>
        
        {/* TaskDispatchButton on top right */}
        <div className="flex-shrink-0">
          <TaskDispatchButton config={evaluationsConfig} />
        </div>
      </div>
      
      <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
        <AnimatePresence mode="popLayout">
          <motion.div 
            key="evaluations-layout"
            className="flex flex-1 min-h-0"
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ 
              type: "spring", 
              stiffness: 300, 
              damping: 30,
              opacity: { duration: 0.2 }
            }}
          >
            {/* Left panel - grid content */}
            <motion.div 
              className={`${selectedEvaluationId && !isNarrowViewport && isFullWidth ? 'hidden' : 'flex-1'} h-full overflow-auto`}
              style={selectedEvaluationId && !isNarrowViewport && !isFullWidth ? {
                width: `${leftPanelWidth}%`
              } : undefined}
              layout
              transition={{ 
                type: "spring", 
                stiffness: 300, 
                damping: 30 
              }}
            >
            <div className="@container space-y-3 overflow-visible">
              {/* EvaluationTasksGauges at the top - only show when not in mobile selected evaluation view */}
              {!(selectedEvaluationId && isNarrowViewport) && (
                <EvaluationTasksGauges />
              )}
              
              {filteredEvaluations.length === 0 ? (
                <div className="text-sm text-muted-foreground">No evaluations found</div>
              ) : (
                <div className={`
                  grid gap-3
                  ${selectedEvaluationId && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
                `}>
                  {filteredEvaluations.map((evaluation: any) => {
                    const clickHandler = getEvaluationClickHandler(evaluation.id);
                    return (
                      <div 
                        key={evaluation.id} 
                        onClick={clickHandler}
                        ref={(el) => {
                          evaluationRefsMap.current.set(evaluation.id, el);
                        }}
                      >
                        <TaskDisplay
                          variant="grid"
                          task={evaluation.task}
                          evaluationData={{
                            ...evaluation,
                            // Pass the raw score results - they will be standardized in the components
                            scoreResults: evaluation.scoreResults
                          }}
                          isSelected={evaluation.id === selectedEvaluationId}
                          onClick={clickHandler}
                          extra={true}
                          selectedScoreResultId={selectedScoreResultId}
                          onSelectScoreResult={handleScoreResultSelect}
                        />
                      </div>
                    );
                  })}
                  <div ref={ref} className="h-4" />
                </div>
              )}
            </div>
            </motion.div>

            {/* Divider for split view */}
            {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
              <div
                className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
                onMouseDown={handleDragStart}
              >
                <div className="absolute inset-0 rounded-full transition-colors duration-150 
                  group-hover:bg-accent" />
              </div>
            )}

            {/* Right panel - evaluation detail view */}
            <AnimatePresence>
              {selectedEvaluationId && !isNarrowViewport && !isFullWidth && (
                <motion.div 
                  key={`evaluation-detail-${selectedEvaluationId}`}
                  className="h-full overflow-hidden flex-shrink-0"
                  style={{ width: `${100 - leftPanelWidth}%` }}
                  initial={{ width: 0, opacity: 0 }}
                  animate={{ 
                    width: `${100 - leftPanelWidth}%`, 
                    opacity: 1 
                  }}
                  exit={{ 
                    width: 0, 
                    opacity: 0 
                  }}
                  transition={{ 
                    type: "spring", 
                    stiffness: 300, 
                    damping: 30 
                  }}
                >
                  {renderSelectedTask}
                </motion.div>
              )}
            </AnimatePresence>

          </motion.div>
        </AnimatePresence>
        
        {/* Full-screen view for mobile or full-width mode */}
        {selectedEvaluationId && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 z-50 overflow-y-auto">
            {renderSelectedTask}
          </div>
        )}
      </div>
      
      <ShareResourceModal 
        isOpen={isShareModalOpen}
        onClose={handleCloseShareModal}
        onShare={handleCreateShareLink}
        resourceType="Evaluation"
        shareUrl={shareUrl}
      />
    </div>
  )
}

// Add TaskStageSubscriptionEvent type
type TaskStageSubscriptionEvent = {
  type: 'create' | 'update';
  data: {
    stageId?: string;
    taskId?: string;
    name?: string;
    status?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED';
    processedItems?: number;
    totalItems?: number;
    startedAt?: string;
    completedAt?: string;
    estimatedCompletionAt?: string;
    statusMessage?: string;
  } | null;
};

// Update the merge functions to properly handle the LazyLoader type
function mergeTaskUpdate(evaluations: Evaluation[], taskData: TaskSubscriptionEvent['data']): Evaluation[] {
  if (!evaluations || !taskData) {
    console.warn('mergeTaskUpdate called with invalid data:', { hasEvaluations: !!evaluations, hasTaskData: !!taskData });
    return evaluations || [];
  }

  return evaluations.map(evaluation => {
    // Skip if evaluation is null or doesn't have a task
    if (!evaluation?.task) {
      return evaluation;
    }

    const task = getValueFromLazyLoader(evaluation.task);
    if (!task?.id || !taskData?.id || task.id !== taskData.id) {
      return evaluation;
    }

    // Create updated task with new data, preserving all existing fields
    const updatedTask = {
      ...task,
      status: taskData.status,
      startedAt: taskData.startedAt,
      completedAt: taskData.completedAt,
      stages: taskData.stages
    };

    // Return updated evaluation while preserving all other fields
    return {
      ...evaluation,
      task: updatedTask as AmplifyTask,
      // Explicitly preserve score results
      scoreResults: evaluation.scoreResults
    };
  });
}

function mergeTaskStageUpdate(
  evaluations: Evaluation[], 
  stageData: TaskStageType,
  taskId: string
): Evaluation[] {
  if (!evaluations || !stageData || !taskId) {
    console.warn('mergeTaskStageUpdate called with invalid data:', { 
      hasEvaluations: !!evaluations, 
      hasStageData: !!stageData,
      taskId 
    });
    return evaluations || [];
  }

  return evaluations.map(evaluation => {
    // Skip if evaluation is null or doesn't have a task
    if (!evaluation?.task) {
      return evaluation;
    }

    const task = getValueFromLazyLoader(evaluation.task);
    // Check if this is the task we're looking for
    if (!task || task.id !== taskId) {
      return evaluation;
    }

    const stages = getValueFromLazyLoader(task.stages);
    if (!stages?.data?.items) {
      // If no stages exist yet, create new stages array
      const updatedStages = {
        data: {
          items: [stageData]
        }
      };

      const updatedTask = {
        ...task,
        stages: updatedStages
      };

      // Return updated evaluation while preserving all other fields
      return {
        ...evaluation,
        task: updatedTask as AmplifyTask,
        // Explicitly preserve score results
        scoreResults: evaluation.scoreResults
      };
    }

    // Find if this stage already exists
    const stageIndex = stages.data.items.findIndex(
      (stage: TaskStageType) => stage?.id === stageData.id || stage?.name === stageData.name
    );

    const updatedStages = {
      data: {
        items: stageIndex === -1 
          ? [...stages.data.items, stageData] // Add new stage
          : stages.data.items.map((stage: TaskStageType, index: number) => // Update existing stage
              index === stageIndex ? { ...stage, ...stageData } : stage
            )
      }
    };

    // Create updated task with new stages
    const updatedTask = {
      ...task,
      stages: updatedStages
    };

    // Return updated evaluation while preserving all other fields
    return {
      ...evaluation,
      task: updatedTask as AmplifyTask,
      // Explicitly preserve score results
      scoreResults: evaluation.scoreResults
    };
  });
}

"use client"

import { useState, useEffect } from 'react'
import { useInView } from 'react-intersection-observer'
import { formatTimeAgo } from '@/utils/format-time'
import { formatDuration } from '@/utils/format-duration'
import { TaskStageConfig } from '@/components/ui/task-status'
import { Schema } from '@/amplify/data/resource'
import { listRecentTasks, updateTask } from '@/utils/amplify-api'
import { useMediaQuery } from '@/hooks/use-media-query'
import { Task, TaskHeader, TaskContent, type BaseTaskProps } from '@/components/Task'
import { Activity, Square, X, MoreHorizontal, RefreshCw, FlaskConical, FlaskRound, TestTubes } from 'lucide-react'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter, usePathname, useParams } from 'next/navigation'
import ScorecardContext from "@/components/ScorecardContext"
import { TaskDispatchButton, activityConfig } from "@/components/task-dispatch"
import { CardButton } from "@/components/CardButton"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { toast } from 'sonner'
import EvaluationTask, { type EvaluationTaskProps, type EvaluationTaskData } from '@/components/EvaluationTask'
import { observeRecentTasks } from '@/utils/subscriptions'
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'
import { ActivityDashboardSkeleton } from '@/components/loading-skeleton'

type TaskStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

// Add this query after the imports
const LIST_TASKS = `
  query ListTaskByAccountIdAndUpdatedAt(
    $accountId: String!
    $sortDirection: ModelSortDirection
    $limit: Int
  ) {
    listTaskByAccountIdAndUpdatedAt(
      accountId: $accountId
      sortDirection: $sortDirection
      limit: $limit
    ) {
      items {
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
        scorecardId
        scoreId
        celeryTaskId
        workerNodeId
        scorecard {
          id
          name
        }
        score {
          id
          name
        }
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
        evaluation {
          id
          type
          metrics
          metricsExplanation
          inferences
          accuracy
          cost
          status
          startedAt
          elapsedSeconds
          estimatedRemainingSeconds
          totalItems
          processedItems
          errorMessage
          errorDetails
          confusionMatrix
          scoreGoal
          datasetClassDistribution
          isDatasetClassDistributionBalanced
          predictedClassDistribution
          isPredictedClassDistributionBalanced
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
      nextToken
    }
  }
`

// Helper to get evaluation icon based on type
function getEvaluationIcon(type: string) {
  switch (type.toLowerCase()) {
    case 'accuracy':
      return <FlaskConical className="h-6 w-6" />
    case 'consistency':
      return <FlaskRound className="h-6 w-6" />
    case 'alignment':
      return <TestTubes className="h-6 w-6" />
    default:
      return <FlaskConical className="h-6 w-6" />
  }
}

function transformTaskToActivity(task: ProcessedTask) {
  if (!task || !task.id) {
    throw new Error('Invalid task: task or task.id is null')
  }

  // Parse metadata for task info - ensure we have a default empty object
  let metadata: Record<string, unknown> = {}
  try {
    if (typeof task.metadata === 'string' && task.metadata) {
      metadata = JSON.parse(task.metadata)
    } else if (task.metadata && typeof task.metadata === 'object') {
      metadata = task.metadata
    }
  } catch (e) {
    console.warn('Failed to parse task metadata:', e)
  }

  // Transform stages if present
  const stages = (task.stages || [])
    .sort((a: ProcessedTask['stages'][0], b: ProcessedTask['stages'][0]) => a.order - b.order)
    .map((stage: ProcessedTask['stages'][0]): TaskStageConfig => {
      // When a task fails, preserve the original status of incomplete stages
      // Only stages that actually completed should show as completed
      const status = stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

      // Only include startedAt if the stage actually started (status is RUNNING, COMPLETED, or FAILED)
      const startedAt = (status === 'RUNNING' || status === 'COMPLETED' || status === 'FAILED') 
        ? stage.startedAt ?? undefined 
        : undefined

      // Only set processedItems if the stage has actually started processing
      const processedItems = (status === 'RUNNING' || status === 'COMPLETED')
        ? stage.processedItems ?? 0  // Default to 0 instead of undefined
        : 0

      // Only set totalItems if we have a valid value
      const totalItems = stage.totalItems ?? undefined

      return {
        key: stage.name,
        label: stage.name,
        color: status === 'COMPLETED' ? 'bg-primary' :
               status === 'RUNNING' ? 'bg-secondary' :
               status === 'FAILED' ? 'bg-false' :
               'bg-neutral',
        name: stage.name,
        order: stage.order,
        status,
        processedItems,
        totalItems,
        startedAt,
        completedAt: stage.completedAt ?? undefined,
        estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
        statusMessage: stage.statusMessage ?? undefined
      }
    })

  // Get current stage info
  const currentStage = stages.find(s => s.status === 'RUNNING') || stages[stages.length - 1];
  
  // Ensure we have a valid timestamp for the time field
  const timeStr = task.createdAt || new Date().toISOString()

  // Ensure we have valid scorecard and score data
  const scorecard = task.scorecard?.name ?? '-'
  const score = task.score?.name ?? '-'

  // Get evaluation data if this is an evaluation task
  const evaluation = task.evaluation
  let evaluationData: EvaluationTaskData | undefined = undefined;
  
  if (evaluation) {
    try {

      // Parse metrics if it's a string
      let parsedMetrics = [];
      try {
        if (typeof evaluation.metrics === 'string') {
          parsedMetrics = JSON.parse(evaluation.metrics);
        } else if (Array.isArray(evaluation.metrics)) {
          parsedMetrics = evaluation.metrics;
        }
      } catch (e) {
        console.error('Error parsing metrics:', e);
      }

      // Parse confusion matrix if it's a string
      let parsedConfusionMatrix = null;
      try {
        if (typeof evaluation.confusionMatrix === 'string') {
          parsedConfusionMatrix = JSON.parse(evaluation.confusionMatrix);
        } else if (evaluation.confusionMatrix) {
          parsedConfusionMatrix = evaluation.confusionMatrix;
        }
      } catch (e) {
        console.error('Error parsing confusion matrix:', e);
      }

      // Parse dataset class distribution if it's a string
      let parsedDatasetClassDistribution = null;
      try {
        if (typeof evaluation.datasetClassDistribution === 'string') {
          parsedDatasetClassDistribution = JSON.parse(evaluation.datasetClassDistribution);
        } else if (evaluation.datasetClassDistribution) {
          parsedDatasetClassDistribution = evaluation.datasetClassDistribution;
        }
      } catch (e) {
        console.error('Error parsing dataset class distribution:', e);
      }

      // Parse predicted class distribution if it's a string
      let parsedPredictedClassDistribution = null;
      try {
        if (typeof evaluation.predictedClassDistribution === 'string') {
          parsedPredictedClassDistribution = JSON.parse(evaluation.predictedClassDistribution);
        } else if (evaluation.predictedClassDistribution) {
          parsedPredictedClassDistribution = evaluation.predictedClassDistribution;
        }
      } catch (e) {
        console.error('Error parsing predicted class distribution:', e);
      }

      evaluationData = {
        id: evaluation.id,
        title: `${scorecard} - ${score}`,
        command: task.command,
        metrics: parsedMetrics,
        metricsExplanation: evaluation.metricsExplanation || null,
        accuracy: typeof evaluation.accuracy === 'number' ? evaluation.accuracy : null,
        processedItems: Number(evaluation.processedItems) || currentStage?.processedItems || 0,
        totalItems: Number(evaluation.totalItems) || currentStage?.totalItems || 0,
        progress: evaluation.processedItems && evaluation.totalItems ? 
          (Number(evaluation.processedItems) / Number(evaluation.totalItems)) * 100 : 0,
        inferences: Number(evaluation.inferences) || 0,
        cost: evaluation.cost ?? null,
        status: evaluation.status || task.status,
        elapsedSeconds: evaluation.elapsedSeconds ?? null,
        estimatedRemainingSeconds: evaluation.estimatedRemainingSeconds ?? null,
        startedAt: evaluation.startedAt || task.startedAt || undefined,
        errorMessage: evaluation.errorMessage || task.errorMessage,
        errorDetails: evaluation.errorDetails,
        confusionMatrix: parsedConfusionMatrix,
        scoreGoal: evaluation.scoreGoal,
        datasetClassDistribution: parsedDatasetClassDistribution,
        isDatasetClassDistributionBalanced: evaluation.isDatasetClassDistributionBalanced,
        predictedClassDistribution: parsedPredictedClassDistribution,
        isPredictedClassDistributionBalanced: evaluation.isPredictedClassDistributionBalanced,
        scoreResults: evaluation.scoreResults?.map((result: {
          id: string;
          value: string | number;
          confidence: number | null;
          metadata: any;
          explanation: string | null;
          itemId: string | null;
        }) => ({
          id: result.id,
          value: result.value,
          confidence: result.confidence,
          metadata: result.metadata,
          explanation: result.explanation,
          itemId: result.itemId,
          trace: null
        })) || [],
        task: {
          id: task.id,
          accountId: '',
          type: task.type,
          command: task.command,
          status: task.status,
          target: task.target,
          startedAt: task.startedAt,
          completedAt: task.completedAt,
          dispatchStatus: undefined,
          celeryTaskId: task.celeryTaskId,
          workerNodeId: task.workerNodeId,
          stages: {
            items: stages.map(stage => ({
              id: stage.name,
              name: stage.name,
              order: stage.order || 0,
              status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
              processedItems: stage.processedItems,
              totalItems: stage.totalItems,
              startedAt: stage.startedAt,
              completedAt: stage.completedAt,
              estimatedCompletionAt: stage.estimatedCompletionAt,
              statusMessage: stage.statusMessage
            }))
          }
        }
      }

    } catch (error) {
      console.error('Error transforming evaluation data:', error, {
        evaluationId: evaluation.id,
        metrics: evaluation.metrics,
        confusionMatrix: evaluation.confusionMatrix,
        datasetClassDistribution: evaluation.datasetClassDistribution,
        predictedClassDistribution: evaluation.predictedClassDistribution
      });
    }
  }

  const result: EvaluationTaskProps['task'] = {
    id: task.id,
    type: String((metadata as any)?.type || task.type),
    scorecard,
    score,
    time: timeStr,
    description: task.command,
    data: evaluationData || {
      id: task.id,
      title: `${scorecard} - ${score}`,
      command: task.command,
      accuracy: (metadata as any)?.accuracy ?? null,
      metrics: (metadata as any)?.metrics ?? [],
      metricsExplanation: null,
      processedItems: currentStage?.processedItems ?? 0,
      totalItems: currentStage?.totalItems ?? 0,
      progress: currentStage?.processedItems && currentStage.totalItems ? 
        (currentStage.processedItems / currentStage.totalItems) * 100 : 0,
      inferences: (metadata as any)?.inferences ?? 0,
      cost: (metadata as any)?.cost ?? null,
      status: task.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      elapsedSeconds: (metadata as any)?.elapsedSeconds ?? null,
      estimatedRemainingSeconds: (metadata as any)?.estimatedRemainingSeconds ?? null,
      startedAt: task.startedAt,
      errorMessage: task.errorMessage,
      errorDetails: task.errorDetails,
      confusionMatrix: (metadata as any)?.confusionMatrix,
      datasetClassDistribution: (metadata as any)?.datasetClassDistribution ?? undefined,
      isDatasetClassDistributionBalanced: (metadata as any)?.isDatasetClassDistributionBalanced ?? null,
      predictedClassDistribution: (metadata as any)?.predictedClassDistribution ?? undefined,
      isPredictedClassDistributionBalanced: (metadata as any)?.isPredictedClassDistributionBalanced ?? null,
      scoreResults: [],
      task: {
        id: task.id,
        accountId: '',
        type: task.type,
        command: task.command,
        status: task.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
        target: task.target,
        startedAt: task.startedAt,
        completedAt: task.completedAt,
        dispatchStatus: undefined,
        celeryTaskId: task.celeryTaskId,
        workerNodeId: task.workerNodeId,
        stages: {
          items: stages.map(stage => ({
            id: stage.name,
            name: stage.name,
            order: stage.order || 0,
            status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
            processedItems: stage.processedItems,
            totalItems: stage.totalItems,
            startedAt: stage.startedAt,
            completedAt: stage.completedAt,
            estimatedCompletionAt: stage.estimatedCompletionAt,
            statusMessage: stage.statusMessage
          }))
        }
      }
    },
    stages,
    currentStageName: currentStage?.name,
    processedItems: currentStage?.processedItems ?? 0,
    totalItems: currentStage?.totalItems ?? 0,
    startedAt: task.startedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    status: task.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    statusMessage: currentStage?.statusMessage,
    errorMessage: task.status === 'FAILED' && task.errorMessage ? task.errorMessage : undefined,
    dispatchStatus: undefined,
    celeryTaskId: task.celeryTaskId,
    workerNodeId: task.workerNodeId
  }

  return result
}

export default function ActivityDashboard({ 
  initialSelectedTaskId = null 
}: { 
  initialSelectedTaskId?: string | null 
} = {}) {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams();
  
  // State hooks
  const [displayedTasks, setDisplayedTasks] = useState<ReturnType<typeof transformTaskToActivity>[]>([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [recentTasks, setRecentTasks] = useState<ProcessedTask[]>([])
  const [selectedTask, setSelectedTask] = useState<string | null>(initialSelectedTaskId)
  const [isFullWidth, setIsFullWidth] = useState(!!initialSelectedTaskId)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })

  // Handle deep linking - check if we're on a specific task page
  useEffect(() => {
    // If we have an ID in the URL and we're on the task detail page
    if (params && 'id' in params && pathname === `/lab/tasks/${params.id}`) {
      setSelectedTask(params.id as string);
      if (isNarrowViewport) {
        setIsFullWidth(true);
      }
    }
  }, [params, pathname, isNarrowViewport]);

  // Handle browser back/forward navigation with popstate event
  useEffect(() => {
    const handlePopState = (event: PopStateEvent) => {
      // Extract task ID from URL if present
      const match = window.location.pathname.match(/\/lab\/tasks\/([^\/]+)$/);
      const idFromUrl = match ? match[1] : null;
      
      // Update the selected task ID based on the URL
      setSelectedTask(idFromUrl);
      if (idFromUrl && isNarrowViewport) {
        setIsFullWidth(true);
      } else if (!idFromUrl && isNarrowViewport) {
        setIsFullWidth(false);
      }
    };

    // Add event listener for popstate (browser back/forward)
    window.addEventListener('popstate', handlePopState);
    
    // Clean up event listener on unmount
    return () => {
      window.removeEventListener('popstate', handlePopState);
    };
  }, [isNarrowViewport]);

  // Custom setter for selectedTask that handles both state and URL
  const handleSelectTask = (id: string | null) => {
    // Only update state if the selected task has changed
    if (id !== selectedTask) {
      setSelectedTask(id);
      
      // Update URL without triggering a navigation/re-render
      const newPathname = id ? `/lab/tasks/${id}` : '/lab/activity';
      window.history.pushState(null, '', newPathname);
      
      if (id && isNarrowViewport) {
        setIsFullWidth(true);
      }
    }
  };

  // Handle closing the selected task
  const handleCloseTask = () => {
    setSelectedTask(null);
    setIsFullWidth(false);
    
    // Update URL without triggering a navigation/re-render
    window.history.pushState(null, '', '/lab/activity');
  };

  // Add authentication check
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.push('/');
      return;
    }
  }, [authStatus, router]);

  // Initial data load
  const fetchRecentTasks = async () => {
    try {
      const { tasks } = await listRecentTasks();
      console.warn('Initial data load complete:', {
        count: tasks.length,
        taskIds: tasks.map((item: ProcessedTask) => item.id),
        taskDetails: tasks.map((item: ProcessedTask) => ({
          id: item.id,
          status: item.status,
          type: item.type
        }))
      });
      setRecentTasks(tasks);
      setIsInitialLoading(false);
    } catch (error) {
      console.error('Error loading initial data:', error);
      setIsInitialLoading(false);
    }
  };

  useEffect(() => {
    fetchRecentTasks();

    // Set up real-time subscription
    console.log('Setting up real-time task subscription');
    const subscription = observeRecentTasks().subscribe({
      next: ({ data: processedTask }) => {
        if (processedTask) {
          setRecentTasks(prev => {
            const taskIndex = prev.findIndex(t => t.id === processedTask.id);
            if (taskIndex !== -1) {
              // Update existing task
              const updatedTasks = [...prev];
              updatedTasks[taskIndex] = processedTask;
              return updatedTasks;
            } else {
              // Add new task at the beginning
              return [processedTask, ...prev].slice(0, 12);
            }
          });
        }
      },
      error: (error) => {
        console.error('Task subscription error:', error);
      }
    });

    return () => {
      console.log('Cleaning up task subscription');
      subscription.unsubscribe();
    };
  }, []);

  // Handle task updates
  useEffect(() => {
    const transformed = recentTasks.map(transformTaskToActivity);
    
    // Sort tasks: use createdAt for in-progress tasks, updatedAt for completed ones
    const sorted = [...transformed].sort((a, b) => {
      // For completed/failed tasks, sort by updatedAt
      if ((a.status === 'COMPLETED' || a.status === 'FAILED') && 
          (b.status === 'COMPLETED' || b.status === 'FAILED')) {
        return new Date(b.time).getTime() - new Date(a.time).getTime()
      }
      // For in-progress tasks or mixing in-progress with completed, sort by createdAt
      return new Date(b.time).getTime() - new Date(a.time).getTime()
    });

    const filtered = sorted.filter(task => {
      if (!selectedScorecard && !selectedScore) return true;
      if (selectedScorecard && task.scorecard !== selectedScorecard) return false;
      if (selectedScore && task.score !== selectedScore) return false;
      return true;
    });

    // Compare with previous state to avoid unnecessary updates
    setDisplayedTasks(prevTasks => {
      // If lengths are different, definitely need to update
      if (!prevTasks || prevTasks.length !== filtered.length) {
        return filtered;
      }

      // Check if any task's data has meaningfully changed
      const hasChanges = filtered.some((task, index) => {
        const prevTask = prevTasks[index];
        if (!prevTask || prevTask.id !== task.id) return true;

        // Check for changes in progress-related fields
        const prevStage = prevTask.stages?.find(s => s.status === 'RUNNING');
        const currentStage = task.stages?.find(s => s.status === 'RUNNING');

        if (prevStage && currentStage) {
          return (
            prevStage.processedItems !== currentStage.processedItems ||
            prevStage.totalItems !== currentStage.totalItems ||
            prevStage.status !== currentStage.status
          );
        }

        return (
          prevTask.status !== task.status ||
          prevTask.processedItems !== task.processedItems ||
          prevTask.totalItems !== task.totalItems
        );
      });

      return hasChanges ? filtered : prevTasks;
    });
  }, [recentTasks, selectedScorecard, selectedScore]);

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

  const renderSelectedTask = () => {
    if (!selectedTask) return null
    const task = displayedTasks.find(t => t.id === selectedTask)
    if (!task) return null

    console.debug('Rendering selected task in Activity Dashboard:', {
      taskId: task.id,
      type: task.type,
      command: task.description || task.data?.command,
      isEvaluation: task.type.toLowerCase().includes('evaluation'),
      commandDisplay: 'full' // Verify we're setting this correctly
    });

    const handleAnnounceAgain = async () => {
      console.log('Announcing task again:', task.id)
      try {
        // First update the main task record - reset all timing and error fields
        console.log('Resetting task:', task.id, 'Current status:', task.status)
        const updatedTask = await updateTask(task.id, {
          dispatchStatus: undefined,
          workerNodeId: null,
          startedAt: null,
          estimatedCompletionAt: null,
          completedAt: null,
          currentStageId: null, // Reset current stage
          status: 'PENDING', // Reset task status
          errorMessage: null, // Reset error fields
          errorDetails: null,
          stdout: null, // Reset output fields
          stderr: null,
          celeryTaskId: null // Reset task tracking fields
        }, 'Task')
        console.log('Task update result:', updatedTask)

        // Then update each stage separately - reset all timing, progress, and error fields
        if (task.stages) {
          for (const stage of task.stages) {
            console.log('Resetting stage:', stage.name, 'Current status:', stage.status)
            const updatedStage = await updateTask(`${task.id}#${stage.name}`, {
              status: 'PENDING',
              startedAt: null,
              estimatedCompletionAt: null,
              completedAt: null,
              processedItems: 0,
              totalItems: stage.totalItems || null, // Preserve total items if it exists
              statusMessage: "Not started"
            }, 'TaskStage')
            console.log('Stage update result:', updatedStage)
          }
        }

        if (updatedTask) {
          toast.success('Task re-announced successfully')
        } else {
          toast.error('Failed to re-announce task')
        }
      } catch (error) {
        console.error('Error re-announcing task:', error)
        toast.error('Error re-announcing task')
      }
    }

    const controlButtons = (
      <DropdownMenu>
        <DropdownMenuTrigger>
          <CardButton
            icon={MoreHorizontal}
            onClick={() => {}}
            aria-label="More options"
          />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleAnnounceAgain}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Announce Again
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    )

    if (task.type.toLowerCase().includes('evaluation')) {
      return (
        <EvaluationTask
          variant="detail"
          task={task}
          controlButtons={controlButtons}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={handleCloseTask}
          commandDisplay="full"
        />
      )
    }

    return (
      <Task
        variant="detail"
        task={task}
        controlButtons={controlButtons}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        onClose={handleCloseTask}
        renderHeader={TaskHeader}
        renderContent={(props) => <TaskContent {...props} />}
        commandDisplay="full"
      />
    )
  }

  // Early return for unauthenticated state
  if (authStatus !== 'authenticated') {
    return null;
  }

  // Show loading skeleton during initial load
  if (isInitialLoading) {
    return <ActivityDashboardSkeleton />
  }

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="mb-3 flex justify-between items-start">
        <ScorecardContext 
          selectedScorecard={selectedScorecard}
          setSelectedScorecard={setSelectedScorecard}
          selectedScore={selectedScore}
          setSelectedScore={setSelectedScore}
        />
        <TaskDispatchButton config={activityConfig} />
      </div>
      <div className="flex h-full">
        <div 
          className={`
            ${selectedTask && !isNarrowViewport && !isFullWidth ? '' : 'w-full'}
            ${selectedTask && !isNarrowViewport && isFullWidth ? 'hidden' : ''}
            h-full overflow-y-auto overflow-x-hidden @container
          `}
          style={selectedTask && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          <div className={`
            grid gap-3
            ${selectedTask && !isNarrowViewport && !isFullWidth ? 'grid-cols-1' : 'grid-cols-1 @[640px]:grid-cols-2'}
          `}>
            {displayedTasks.map((task) => (
              <div 
                key={task.id} 
                onClick={() => {
                  handleSelectTask(task.id)
                }}
              >
                {task.type.toLowerCase().includes('evaluation') ? (
                  <EvaluationTask
                    variant="grid"
                    task={task}
                    isSelected={task.id === selectedTask}
                    onClick={() => {
                      handleSelectTask(task.id)
                    }}
                  />
                ) : (
                  <Task
                    variant="grid"
                    task={task}
                    isSelected={task.id === selectedTask}
                    onClick={() => {
                      handleSelectTask(task.id)
                    }}
                    renderHeader={TaskHeader}
                    renderContent={(props) => <TaskContent {...props} />}
                  />
                )}
              </div>
            ))}
            <div ref={ref} />
          </div>
        </div>

        {selectedTask && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
            onMouseDown={handleDragStart}
          >
            <div className="absolute inset-0 rounded-full transition-colors duration-150 
              group-hover:bg-accent" />
          </div>
        )}

        {selectedTask && !isNarrowViewport && !isFullWidth && (
          <div 
            className="h-full overflow-hidden"
            style={{ width: `${100 - leftPanelWidth}%` }}
          >
            {renderSelectedTask()}
          </div>
        )}

        {selectedTask && (isNarrowViewport || isFullWidth) && (
          <div className="fixed inset-0 bg-background z-50">
            {renderSelectedTask()}
          </div>
        )}
      </div>
    </div>
  )
}

"use client"

import { useState, useEffect } from 'react'
import { useInView } from 'react-intersection-observer'
import { formatTimeAgo } from '@/utils/format-time'
import { formatDuration } from '@/utils/format-duration'
import { TaskStatus, TaskStageConfig } from '@/components/ui/task-status'
import { Schema } from '@/amplify/data/resource'
import { listRecentTasks, observeRecentTasks, updateTask } from '@/utils/data-operations'
import { useMediaQuery } from '@/hooks/use-media-query'
import { Task, TaskHeader, TaskContent, type BaseTaskProps } from '@/components/Task'
import { Activity, Square, X, MoreHorizontal, RefreshCw, FlaskConical, FlaskRound, TestTubes } from 'lucide-react'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter } from 'next/navigation'
import ScorecardContext from "@/components/ScorecardContext"
import { TaskDispatchButton, activityConfig } from "@/components/task-dispatch"
import { CardButton } from "@/components/CardButton"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { toast } from 'sonner'
import EvaluationTask, { type EvaluationTaskProps, type EvaluationTaskData } from '@/components/EvaluationTask'

// Import the types from data-operations
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'

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
  let metadata = {}
  try {
    metadata = task.metadata ? JSON.parse(task.metadata) : {}
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

  const result: EvaluationTaskProps['task'] = {
    id: task.id,
    type: String((metadata as any)?.type || task.type),
    scorecard,
    score,
    time: timeStr,
    description: task.command,
    data: {
      id: task.id,
      title: `${scorecard} - ${score}`,
      command: task.command,
      accuracy: (metadata as any)?.accuracy ?? null,
      metrics: (metadata as any)?.metrics ?? [],
      processedItems: currentStage?.processedItems ?? 0,
      totalItems: currentStage?.totalItems ?? 0,
      progress: currentStage?.processedItems && currentStage.totalItems ? 
        (currentStage.processedItems / currentStage.totalItems) * 100 : 0,
      inferences: (metadata as any)?.inferences ?? 0,
      cost: (metadata as any)?.cost ?? null,
      status: task.status,
      elapsedSeconds: (metadata as any)?.elapsedSeconds ?? null,
      estimatedRemainingSeconds: (metadata as any)?.estimatedRemainingSeconds ?? null,
      startedAt: task.startedAt ?? undefined,
      errorMessage: task.errorMessage,
      errorDetails: (metadata as any)?.errorDetails ?? null,
      task: {
        id: task.id,
        accountId: '',
        type: task.type,
        command: task.command,
        status: task.status,
        target: task.target,
        startedAt: task.startedAt,
        completedAt: task.completedAt,
        dispatchStatus: task.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
        celeryTaskId: task.celeryTaskId,
        workerNodeId: task.workerNodeId,
        stages: { items: stages }
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
    dispatchStatus: task.dispatchStatus === 'DISPATCHED' ? 'DISPATCHED' : undefined,
    celeryTaskId: task.celeryTaskId,
    workerNodeId: task.workerNodeId
  }

  return result
}

export default function ActivityDashboard() {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  
  // State hooks
  const [displayedTasks, setDisplayedTasks] = useState<ReturnType<typeof transformTaskToActivity>[]>([])
  const [isInitialLoading, setIsInitialLoading] = useState(true)
  const [recentTasks, setRecentTasks] = useState<ProcessedTask[]>([])
  const [selectedTask, setSelectedTask] = useState<string | null>(null)
  const [isFullWidth, setIsFullWidth] = useState(false)
  const [leftPanelWidth, setLeftPanelWidth] = useState(50)
  const [selectedScorecard, setSelectedScorecard] = useState<string | null>(null)
  const [selectedScore, setSelectedScore] = useState<string | null>(null)
  const isNarrowViewport = useMediaQuery("(max-width: 768px)")
  const { ref, inView } = useInView({
    threshold: 0,
  })

  // Add authentication check
  useEffect(() => {
    if (authStatus === 'unauthenticated') {
      router.push('/');
      return;
    }
  }, [authStatus, router]);

  // Initial data load
  useEffect(() => {
    async function loadInitialData() {
      console.warn('Starting initial data load');
      try {
        const tasks = await listRecentTasks(12);
        console.warn('Initial data load complete:', {
          count: tasks.length,
          taskIds: tasks.map(task => task.id),
          taskDetails: tasks.map(task => ({
            id: task.id,
            scorecard: task.scorecard,
            score: task.score
          }))
        });
        setRecentTasks(tasks);
        setIsInitialLoading(false);
      } catch (error) {
        console.error('Error loading initial data:', error);
        setIsInitialLoading(false);
      }
    }

    loadInitialData();

    // Set up real-time subscription
    console.log('Setting up real-time task subscription');
    const subscription = observeRecentTasks(12).subscribe({
      next: ({ items, isSynced }) => {
        setRecentTasks(items);
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
    console.debug('Processing recentTasks for display:', {
      count: recentTasks.length,
      taskIds: recentTasks.map(task => task.id),
      taskDetails: recentTasks.map(task => ({
        id: task.id,
        status: task.status,
        stages: task.stages?.map(s => ({
          name: s.name,
          status: s.status,
          processedItems: s.processedItems,
          totalItems: s.totalItems
        }))
      }))
    });

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

    console.log('Rendering selected task:', task.id)

    const handleAnnounceAgain = async () => {
      console.log('Announcing task again:', task.id)
      try {
        // First update the main task record - reset all timing and error fields
        console.log('Resetting task:', task.id, 'Current status:', task.status)
        const updatedTask = await updateTask(task.id, {
          dispatchStatus: 'PENDING',
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
              statusMessage: "Not started",
              errorMessage: null, // Reset error fields if they exist
              errorDetails: null,
              metadata: null, // Reset any stage-specific metadata
              progress: null, // Reset any progress tracking
              elapsedTime: null, // Reset timing information
              estimatedTimeRemaining: null,
              lastUpdateTime: null
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
          onClose={() => {
            setSelectedTask(null)
            setIsFullWidth(false)
          }}
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
        onClose={() => {
          setSelectedTask(null)
          setIsFullWidth(false)
        }}
        renderHeader={TaskHeader}
        renderContent={(props) => <TaskContent {...props} />}
      />
    )
  }

  // Early return for unauthenticated state
  if (authStatus !== 'authenticated') {
    return null;
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
            h-full overflow-auto
          `}
          style={selectedTask && !isNarrowViewport && !isFullWidth ? {
            width: `${leftPanelWidth}%`
          } : undefined}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {displayedTasks.map((task) => (
              <div 
                key={task.id} 
                onClick={() => {
                  setSelectedTask(task.id)
                  if (isNarrowViewport) {
                    setIsFullWidth(true)
                  }
                }}
              >
                {task.type.toLowerCase().includes('evaluation') ? (
                  <EvaluationTask
                    variant="grid"
                    task={task}
                    isSelected={task.id === selectedTask}
                    onClick={() => {
                      setSelectedTask(task.id)
                      if (isNarrowViewport) {
                        setIsFullWidth(true)
                      }
                    }}
                  />
                ) : (
                  <Task
                    variant="grid"
                    task={task}
                    isSelected={task.id === selectedTask}
                    onClick={() => {
                      setSelectedTask(task.id)
                      if (isNarrowViewport) {
                        setIsFullWidth(true)
                      }
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

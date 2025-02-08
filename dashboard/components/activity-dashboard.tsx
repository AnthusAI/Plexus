"use client"

import { useState, useEffect } from 'react'
import { useInView } from 'react-intersection-observer'
import { formatTimeAgo } from '@/utils/format-time'
import { formatDuration } from '@/utils/format-duration'
import { TaskStatus, TaskStageConfig } from '@/components/ui/task-status'
import { Schema } from '@/amplify/data/resource'
import { listRecentTasks, observeRecentTasks } from '@/utils/data-operations'
import { useMediaQuery } from '@/hooks/use-media-query'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Activity } from 'lucide-react'
import { useAuthenticator } from '@aws-amplify/ui-react'
import { useRouter } from 'next/navigation'
import ScorecardContext from "@/components/ScorecardContext"
import { TaskDispatchButton } from "@/components/task-dispatch-button"

// Import the types from data-operations
import type { AmplifyTask, ProcessedTask } from '@/utils/data-operations'

function transformTaskToActivity(task: ProcessedTask) {
  if (!task || !task.id) {
    throw new Error('Invalid task: task or task.id is null')
  }

  // Parse metadata for task info
  const metadata = task.metadata ? JSON.parse(task.metadata) : {}

  // Transform stages if present
  const stages = (task.stages || [])
    .sort((a: ProcessedTask['stages'][0], b: ProcessedTask['stages'][0]) => a.order - b.order)
    .map((stage: ProcessedTask['stages'][0]): TaskStageConfig => ({
      key: stage.name,
      label: stage.name,
      color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
      name: stage.name,
      order: stage.order,
      status: stage.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
      processedItems: stage.processedItems ?? undefined,
      totalItems: stage.totalItems ?? undefined,
      startedAt: stage.startedAt ?? undefined,
      completedAt: stage.completedAt ?? undefined,
      estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
      statusMessage: stage.statusMessage ?? undefined
    }))

  // Get current stage info - highest order non-completed stage, or last stage if all completed
  const currentStage = stages.length > 0 ? 
    stages.reduce((current: TaskStageConfig | null, stage: TaskStageConfig) => {
      // If we haven't found a stage yet, use this one
      if (!current) return stage
      
      // If this stage is RUNNING, it should be the current stage
      if (stage.status === 'RUNNING') return stage
      
      // If current stage is RUNNING, keep it
      if (current.status === 'RUNNING') return current
      
      // If neither stage is RUNNING, prefer the earliest PENDING stage
      if (stage.status === 'PENDING' && current.status === 'PENDING') {
        return stage.order < current.order ? stage : current
      }
      
      // If one stage is PENDING and the other isn't, prefer the PENDING stage
      if (stage.status === 'PENDING') return stage
      if (current.status === 'PENDING') return current
      
      // If all stages are completed, use the last one
      if (stage.status === 'COMPLETED' && stage === stages[stages.length - 1] && 
          stages.every((s: TaskStageConfig) => s.order < stage.order ? s.status === 'COMPLETED' : true)) {
        return stage
      }
      
      return current
    }, null) : null

  // Ensure we have a valid timestamp for the time field
  const timeStr = task.createdAt || new Date().toISOString()

  return {
    id: task.id,
    type: String(metadata.type || task.type),
    scorecard: metadata.scorecard?.toString() ?? '',
    score: metadata.score?.toString() ?? '',
    time: timeStr,
    command: task.command,
    stages,
    currentStageName: currentStage?.name,
    processedItems: currentStage?.processedItems ?? 0,
    totalItems: currentStage?.totalItems ?? 0,
    startedAt: task.startedAt ?? undefined,
    estimatedCompletionAt: task.estimatedCompletionAt ?? undefined,
    completedAt: task.completedAt ?? undefined,
    status: task.status as 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED',
    stageConfigs: stages,
    statusMessage: currentStage?.statusMessage ?? undefined,
    data: {
      id: task.id,
      title: metadata.type || task.type,
      command: task.command
    }
  }
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

  useEffect(() => {
    const transformed = recentTasks.map(transformTaskToActivity)
    const filtered = transformed.filter(task => {
      if (!selectedScorecard && !selectedScore) return true;
      if (selectedScorecard && task.scorecard !== selectedScorecard) return false;
      if (selectedScore && task.score !== selectedScore) return false;
      return true;
    })
    setDisplayedTasks(filtered)
  }, [recentTasks, selectedScorecard, selectedScore])

  useEffect(() => {
    const subscription = observeRecentTasks(12).subscribe({
      next: ({ items, isSynced }) => {
        setRecentTasks(items)
        if (isSynced) {
          setIsInitialLoading(false)
        }
      },
      error: (error) => {
        console.error('Error in task subscription:', error)
        setIsInitialLoading(false)
      }
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

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

    return (
      <div className="bg-card rounded-lg p-4 h-full overflow-auto">
        <Task
          variant="detail"
          task={task}
          isFullWidth={isFullWidth}
          onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
          onClose={() => {
            setSelectedTask(null)
            setIsFullWidth(false)
          }}
          renderHeader={(props) => (
            <TaskHeader {...props}>
              <div className="flex justify-end w-full">
                <Activity className="h-6 w-6" />
              </div>
            </TaskHeader>
          )}
          renderContent={(props) => <TaskContent {...props} />}
        />
      </div>
    )
  }

  // Early return for unauthenticated state
  if (authStatus !== 'authenticated') {
    return null;
  }

  return (
    <div className="flex flex-col h-full p-1.5">
      <div className="mb-3 flex justify-between items-center">
        <ScorecardContext 
          selectedScorecard={selectedScorecard}
          setSelectedScorecard={setSelectedScorecard}
          selectedScore={selectedScore}
          setSelectedScore={setSelectedScore}
        />
        <TaskDispatchButton />
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
                className="bg-card rounded-lg p-3 cursor-pointer hover:bg-accent/50 transition-colors"
                onClick={() => {
                  setSelectedTask(task.id)
                  if (isNarrowViewport) {
                    setIsFullWidth(true)
                  }
                }}
              >
                <Task
                  variant="grid"
                  task={task}
                  renderHeader={(props) => (
                    <TaskHeader {...props}>
                      <div className="flex justify-end w-full">
                        <Activity className="h-6 w-6" />
                      </div>
                    </TaskHeader>
                  )}
                  renderContent={(props) => <TaskContent {...props} />}
                />
              </div>
            ))}
            <div ref={ref} />
          </div>
        </div>

        {selectedTask && !isNarrowViewport && !isFullWidth && (
          <div
            className="w-2 relative cursor-col-resize flex-shrink-0 group"
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

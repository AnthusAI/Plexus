"use client"

import React, { useEffect, useState, useRef } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { StandardSection } from '@/components/landing/StandardSection'
import { TaskStageConfig } from '@/components/ui/task-status'
import { BaseTaskData } from '@/types/base'
import { cn } from '@/lib/utils'

const TOTAL_ITEMS = 100
const DEMO_DURATION = 20000 // 20 seconds total
const PROCESS_INTERVAL = 100 // Update every 100ms

const demoStages: TaskStageConfig[] = [
  {
    key: 'Setup',
    label: 'Setup',
    color: 'bg-primary',
    name: 'Setup',
    order: 1,
    status: 'PENDING',
    processedItems: 0,
    totalItems: TOTAL_ITEMS,
    startedAt: undefined,
    completedAt: undefined,
    estimatedCompletionAt: undefined,
    statusMessage: 'Loading AI models...'
  },
  {
    key: 'Running',
    label: 'Running',
    color: 'bg-secondary',
    name: 'Running',
    order: 2,
    status: 'PENDING',
    processedItems: 0,
    totalItems: TOTAL_ITEMS,
    startedAt: undefined,
    completedAt: undefined,
    estimatedCompletionAt: undefined,
    statusMessage: 'Processing items...'
  },
  {
    key: 'Finalizing',
    label: 'Finalizing',
    color: 'bg-primary',
    name: 'Finalizing',
    order: 3,
    status: 'PENDING',
    processedItems: 0,
    totalItems: TOTAL_ITEMS,
    startedAt: undefined,
    completedAt: undefined,
    estimatedCompletionAt: undefined,
    statusMessage: 'Computing metrics...'
  }
]

interface TaskDemoProps {
  startDelay?: number
  onComplete?: () => void
  className?: string
  taskId: string
  shouldStart?: boolean
}

interface TaskProgress {
  itemsProcessed: number
  totalProcessingSteps: number
  itemsPerStep: number
  currentItems: number
}

const TaskDemoBase = ({ 
  startDelay = 0, 
  onComplete, 
  className,
  taskId,
  shouldStart = true
}: TaskDemoProps) => {
  const [currentStage, setCurrentStage] = useState<string>('Setup')
  const [startTime, setStartTime] = useState<string | null>(null)
  const [estimatedEndTime, setEstimatedEndTime] = useState<string | null>(null)
  const [completedTime, setCompletedTime] = useState<string | null>(null)
  const [status, setStatus] = useState<'PENDING' | 'RUNNING' | 'COMPLETED'>('PENDING')
  const [stages, setStages] = useState(demoStages)
  const [currentProgress, setCurrentProgress] = useState(0)
  
  const processIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const progressRef = useRef<TaskProgress>({
    itemsProcessed: 0,
    totalProcessingSteps: 0,
    itemsPerStep: 0,
    currentItems: 0
  })

  useEffect(() => {
    // Don't start if shouldStart is false or if this task has already started
    if (!shouldStart || startTime !== null) return

    // Start the demo after the delay
    const startTimeout = setTimeout(() => {
      const startDemo = () => {
        const now = new Date()
        const endTime = new Date(now.getTime() + DEMO_DURATION)
        
        // Set the start time once and only once at the very beginning
        const taskStartTime = now.toISOString()
        setStartTime(taskStartTime)
        setEstimatedEndTime(endTime.toISOString())
        setStatus('RUNNING')

        // Reset progress
        progressRef.current = {
          itemsProcessed: 0,
          totalProcessingSteps: 0,
          itemsPerStep: 0,
          currentItems: 0
        }
        setCurrentProgress(0)

        // Update stages for initialization
        setStages(prev => prev.map(stage => ({
          ...stage,
          status: stage.name === 'Setup' ? 'RUNNING' : 'PENDING',
          startedAt: stage.name === 'Setup' ? taskStartTime : undefined,
          processedItems: stage.name === 'Setup' ? 0 : undefined,
          totalItems: stage.name === 'Setup' ? TOTAL_ITEMS : undefined,
          statusMessage: stage.name === 'Setup' ? 'Loading AI models...' : stage.statusMessage
        })))

        // Initialize stage messages
        const initDuration = DEMO_DURATION * 0.15 // 3 seconds
        const processingDuration = DEMO_DURATION * 0.6 // 12 seconds
        const finalizingDuration = DEMO_DURATION * 0.25 // 5 seconds

        const initMessageTimeout = setTimeout(() => {
          setStages(prev => prev.map(stage => ({
            ...stage,
            statusMessage: stage.name === 'Setup' ? 'Post-load testing...' : stage.statusMessage,
            processedItems: stage.name === 'Setup' ? TOTAL_ITEMS : undefined
          })))
        }, initDuration * 0.5)

        // Initialize stage completion
        const initCompleteTimeout = setTimeout(() => {
          const stageTime = new Date()
          setStages(prev => prev.map(stage => ({
            ...stage,
            status: stage.name === 'Setup' ? 'COMPLETED' : 
                    stage.name === 'Running' ? 'RUNNING' : 'PENDING',
            completedAt: stage.name === 'Setup' ? stageTime.toISOString() : undefined,
            startedAt: stage.name === 'Running' ? taskStartTime : stage.startedAt,
            processedItems: stage.name === 'Running' ? 0 : stage.processedItems,
            totalItems: stage.name === 'Running' ? TOTAL_ITEMS : stage.totalItems,
            statusMessage: stage.name === 'Running' ? 'Starting to process items...' : stage.statusMessage
          })))
          setCurrentStage('Running')

          // Initialize progress tracking
          progressRef.current = {
            itemsProcessed: 0,
            totalProcessingSteps: processingDuration / PROCESS_INTERVAL,
            itemsPerStep: TOTAL_ITEMS / (processingDuration / PROCESS_INTERVAL),
            currentItems: 0
          }

          // Start processing items
          processIntervalRef.current = setInterval(() => {
            progressRef.current.itemsProcessed = Math.min(
              progressRef.current.itemsProcessed + progressRef.current.itemsPerStep,
              TOTAL_ITEMS
            )
            progressRef.current.currentItems = Math.floor(progressRef.current.itemsProcessed)
            setCurrentProgress(progressRef.current.currentItems)

            // Update status message and progress for the Running stage
            setStages(prev => prev.map(stage => 
              stage.name === 'Running' 
                ? { 
                    ...stage, 
                    processedItems: progressRef.current.currentItems,
                    statusMessage: getStatusMessage(progressRef.current.currentItems / TOTAL_ITEMS)
                  } 
                : stage
            ))
          }, PROCESS_INTERVAL)
        }, initDuration)

        // Finalizing stage
        const finalizingTimeout = setTimeout(() => {
          if (processIntervalRef.current) {
            clearInterval(processIntervalRef.current)
            processIntervalRef.current = null
          }
          const stageTime = new Date()
          progressRef.current.currentItems = TOTAL_ITEMS
          setCurrentProgress(TOTAL_ITEMS) // Ensure we hit 100%
          setStages(prev => prev.map(stage => ({
            ...stage,
            status: stage.name === 'Finalizing' ? 'RUNNING' : 
                    stage.name === 'Running' ? 'COMPLETED' : stage.status,
            completedAt: stage.name === 'Running' ? stageTime.toISOString() : undefined,
            startedAt: stage.name === 'Finalizing' ? taskStartTime : stage.startedAt,
            processedItems: stage.name === 'Running' ? TOTAL_ITEMS : undefined,
            totalItems: stage.name === 'Running' ? TOTAL_ITEMS : undefined,
            statusMessage: stage.name === 'Finalizing' ? 'Starting finalization process...' : stage.statusMessage
          })))
          setCurrentStage('Finalizing')

          // Finalizing stage messages
          const finalizing1Timeout = setTimeout(() => {
            setStages(prev => prev.map(stage => ({
              ...stage,
              statusMessage: stage.name === 'Finalizing' ? 'Aggregating results...' : stage.statusMessage
            })))
          }, finalizingDuration * 0.3)

          const finalizing2Timeout = setTimeout(() => {
            setStages(prev => prev.map(stage => ({
              ...stage,
              statusMessage: stage.name === 'Finalizing' ? 'Preparing final report...' : stage.statusMessage
            })))
          }, finalizingDuration * 0.6)

          const finalizing3Timeout = setTimeout(() => {
            setStages(prev => prev.map(stage => ({
              ...stage,
              statusMessage: stage.name === 'Finalizing' ? 'Saving results...' : stage.statusMessage
            })))
          }, finalizingDuration * 0.8)

          return () => {
            clearTimeout(finalizing1Timeout)
            clearTimeout(finalizing2Timeout)
            clearTimeout(finalizing3Timeout)
          }
        }, initDuration + processingDuration)

        // Helper function to get status message based on progress
        function getStatusMessage(progress: number): string {
          if (progress < 0.25) {
            return 'Starting processing...'
          } else if (progress < 0.6) {
            return 'Processing items...'
          } else if (progress < 0.90) {
            return 'Cruising...'
          } else {
            return 'Completing final items...'
          }
        }

        // Complete
        const completeTimeout = setTimeout(() => {
          const stageTime = new Date()
          setCompletedTime(stageTime.toISOString())
          setStages(prev => prev.map(stage => ({
            ...stage,
            status: 'COMPLETED',
            completedAt: stage.name === 'Finalizing' ? stageTime.toISOString() : stage.completedAt,
            statusMessage: stage.name === 'Finalizing' ? 'Task completed successfully' : stage.statusMessage
          })))
          setStatus('COMPLETED')
          onComplete?.()
        }, DEMO_DURATION)

        return () => {
          if (processIntervalRef.current) {
            clearInterval(processIntervalRef.current)
            processIntervalRef.current = null
          }
          clearTimeout(initMessageTimeout)
          clearTimeout(initCompleteTimeout)
          clearTimeout(finalizingTimeout)
          clearTimeout(completeTimeout)
        }
      }

      const cleanup = startDemo()
      return () => cleanup()
    }, startDelay)

    return () => {
      clearTimeout(startTimeout)
      if (processIntervalRef.current) {
        clearInterval(processIntervalRef.current)
        processIntervalRef.current = null
      }
    }
  }, [startDelay, shouldStart])

  const demoTask = {
    id: taskId,
    type: 'Scorecard Evaluation',
    scorecard: 'ABC, Inc Scorecard',
    score: 'DNC Requested?',
    time: startTime!,  // Use the original start time, it will always be set
    description: 'plexus evaluate accuracy --scorecard abc-inc-scorecard --score "DNC Requested?"',
    stages: stages.map(stage => ({
      ...stage,
      key: stage.name,
      label: stage.name,
      color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
      order: stage.order || 0,
      processedItems: stage.processedItems || 0,
      totalItems: stage.totalItems || TOTAL_ITEMS,
      startedAt: stage.startedAt,
      completedAt: stage.completedAt,
      estimatedCompletionAt: stage.estimatedCompletionAt,
      statusMessage: stage.statusMessage || ''
    })),
    currentStageName: currentStage,
    processedItems: currentProgress,
    totalItems: TOTAL_ITEMS,
    startedAt: startTime!,  // Use the original start time, it will always be set
    estimatedCompletionAt: estimatedEndTime!,  // Use the original estimated end time
    completedAt: completedTime || undefined,
    status,
    data: {
      id: taskId,
      title: 'Demo Task',
      command: 'plexus evaluate accuracy --scorecard abc-inc-scorecard --score "DNC Requested?"'
    } as BaseTaskData,
    dispatchStatus: undefined,
    celeryTaskId: undefined,
    workerNodeId: undefined,
    errorMessage: undefined
  }

  return (
    <div className={cn(
      'transition-all duration-500 ease-in-out',
      className
    )}>
      <Task
        variant="detail"
        task={demoTask}
        renderHeader={(props) => <TaskHeader {...props} />}
        renderContent={(props) => <TaskContent {...props} />}
      />
    </div>
  )
}

export const TaskDemo = React.memo(TaskDemoBase) 
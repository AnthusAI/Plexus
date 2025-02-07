"use client"

import React, { useEffect, useState, useRef } from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { StandardSection } from '@/components/landing/StandardSection'
import { TaskStageConfig } from '@/components/ui/task-status'
import { BaseTaskData } from '@/types/base'
import { cn } from '@/lib/utils'

const demoStages: TaskStageConfig[] = [
  {
    key: 'Initializing',
    label: 'Initializing',
    color: 'bg-primary',
    name: 'Initializing',
    order: 0,
    status: 'PENDING',
    statusMessage: 'Preparing task execution...'
  },
  {
    key: 'Processing',
    label: 'Processing',
    color: 'bg-secondary',
    name: 'Processing',
    order: 1,
    status: 'PENDING',
    statusMessage: 'Starting item processing...'
  },
  {
    key: 'Finalizing',
    label: 'Finalizing',
    color: 'bg-primary',
    name: 'Finalizing',
    order: 2,
    status: 'PENDING',
    statusMessage: 'Waiting to finalize...'
  }
]

const TOTAL_ITEMS = 100
const DEMO_DURATION = 20000 // 20 seconds total
const PROCESS_INTERVAL = 100 // Update every 100ms

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
  const [currentStage, setCurrentStage] = useState<string>('Initializing')
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
          status: stage.name === 'Initializing' ? 'RUNNING' : 'PENDING',
          startedAt: taskStartTime,  // Use the same start time for all stages
          statusMessage: stage.name === 'Initializing' ? 'Loading models...' : stage.statusMessage
        })))

        // Stage timing
        const initDuration = DEMO_DURATION * 0.15 // 3 seconds
        const processingDuration = DEMO_DURATION * 0.6 // 12 seconds
        const finalizingDuration = DEMO_DURATION * 0.25 // 5 seconds

        // Initialize stage messages
        const initMessageTimeout = setTimeout(() => {
          setStages(prev => prev.map(stage => ({
            ...stage,
            statusMessage: stage.name === 'Initializing' ? 'Post-load testing...' : stage.statusMessage
          })))
        }, initDuration * 0.5)

        // Initialize stage completion
        const initCompleteTimeout = setTimeout(() => {
          const stageTime = new Date()
          setStages(prev => prev.map(stage => ({
            ...stage,
            status: stage.name === 'Initializing' ? 'COMPLETED' : 
                    stage.name === 'Processing' ? 'RUNNING' : 'PENDING',
            completedAt: stage.name === 'Initializing' ? stageTime.toISOString() : undefined,
            startedAt: taskStartTime,  // Keep using the original start time
            statusMessage: stage.name === 'Processing' ? 'Starting to process items...' : stage.statusMessage
          })))
          setCurrentStage('Processing')

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

            // Update status message based on progress without updating all stages
            const progress = progressRef.current.currentItems / TOTAL_ITEMS
            let statusMessage = ''
            if (progress < 0.25) {
              statusMessage = 'Starting processing...'
            } else if (progress < 0.6) {
              statusMessage = 'Processing items...'
            } else if (progress < 0.90) {
              statusMessage = 'Cruising...'
            } else {
              statusMessage = 'Completing final items...'
            }

            setStages(prev => prev.map(stage => 
              stage.name === 'Processing' 
                ? { ...stage, statusMessage } 
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
                    stage.name === 'Processing' ? 'COMPLETED' : stage.status,
            completedAt: stage.name === 'Processing' ? stageTime.toISOString() : undefined,
            startedAt: taskStartTime,  // Keep using the original start time
            statusMessage: stage.name === 'Finalizing' ? 'Starting finalization process...' : stage.statusMessage,
            processedItems: stage.name === 'Finalizing' ? undefined : stage.processedItems,
            totalItems: stage.name === 'Finalizing' ? undefined : stage.totalItems
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
    stages,
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
    } as BaseTaskData
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
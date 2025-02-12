import { useEffect } from 'react'
import { getClient } from '@/utils/amplify-client'
import { TaskData, TaskStage } from '@/types/tasks/evaluation'
import { GET_TASK_QUERY } from '../graphql/queries'
import type { GraphQLResult } from '@aws-amplify/api'

interface GetTaskResponse {
  getTask: TaskData
}

interface TaskStageWithUI extends TaskStage {
  key: string
  label: string
  color: string
}

interface UseTaskUpdatesProps {
  taskId: string | null
  onTaskUpdate: (task: TaskData) => void
}

export function useTaskUpdates({ taskId, onTaskUpdate }: UseTaskUpdatesProps) {
  useEffect(() => {
    if (!taskId) return

    const currentClient = getClient()

    // Function to fetch full task data
    const fetchTaskData = async () => {
      try {
        const result = await currentClient.graphql({
          query: GET_TASK_QUERY,
          variables: { id: taskId }
        }) as GraphQLResult<GetTaskResponse>

        if (result.data?.getTask) {
          const updatedTask = result.data.getTask
          
          // Transform stages for TaskStatus component
          const transformedStages = updatedTask.stages?.items?.map((stage: TaskStage): TaskStageWithUI => ({
            key: stage.name,
            label: stage.name,
            color: stage.name.toLowerCase() === 'processing' ? 'bg-secondary' : 'bg-primary',
            name: stage.name,
            order: stage.order,
            status: stage.status,
            processedItems: stage.processedItems ?? undefined,
            totalItems: stage.totalItems ?? undefined,
            startedAt: stage.startedAt ?? undefined,
            completedAt: stage.completedAt ?? undefined,
            estimatedCompletionAt: stage.estimatedCompletionAt ?? undefined,
            statusMessage: stage.statusMessage ?? undefined,
            id: stage.id
          })) || []

          // Get current stage info
          const currentStage = transformedStages.length > 0 ? 
            transformedStages.reduce((current: TaskStageWithUI | null, stage: TaskStageWithUI) => {
              if (!current) return stage
              
              if (updatedTask.status === 'COMPLETED') {
                return stage.order > current.order ? stage : current
              }
              
              if (stage.status === 'RUNNING') return stage
              if (current.status === 'RUNNING') return current
              
              if (stage.status === 'PENDING' && current.status === 'PENDING') {
                return stage.order < current.order ? stage : current
              }
              
              if (stage.status === 'PENDING') return stage
              if (current.status === 'PENDING') return current
              
              return stage.order > current.order ? stage : current
            }, null) : null

          const normalizedTask: TaskData = {
            ...updatedTask,
            stages: {
              items: transformedStages,
              nextToken: null
            },
            processedItems: currentStage?.processedItems ?? 0,
            totalItems: currentStage?.totalItems ?? 0
          }

          onTaskUpdate(normalizedTask)
        }
      } catch (error) {
        console.error('Error fetching task data:', error)
      }
    }

    // Initial fetch
    fetchTaskData()

    // Set up polling interval for updates
    const interval = setInterval(fetchTaskData, 5000)

    return () => {
      clearInterval(interval)
    }
  }, [taskId, onTaskUpdate])
} 
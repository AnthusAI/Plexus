import { useEffect } from 'react'
import { getClient } from '@/utils/amplify-client'
import { Schema } from '@/amplify/data/resource'
import { transformEvaluation } from '../utils/transform'
import { 
  EVALUATION_UPDATE_SUBSCRIPTION, 
  TASK_UPDATE_SUBSCRIPTION, 
  TASK_STAGE_UPDATE_SUBSCRIPTION 
} from '../graphql/queries'

interface UseEvaluationSubscriptionsProps {
  accountId: string | null
  onEvaluationUpdate: (evaluation: Schema['Evaluation']['type']) => void
  onEvaluationCreate: (evaluation: Schema['Evaluation']['type']) => void
  onEvaluationDelete: (evaluationId: string) => void
}

export function useEvaluationSubscriptions({
  accountId,
  onEvaluationUpdate,
  onEvaluationCreate,
  onEvaluationDelete
}: UseEvaluationSubscriptionsProps) {
  useEffect(() => {
    if (!accountId) return

    const currentClient = getClient()
    const subscriptions: { unsubscribe: () => void }[] = []

    // Subscribe to evaluation updates
    const evaluationSub = (currentClient.graphql({
      query: EVALUATION_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateEvaluation: Schema['Evaluation']['type'] } }) => {
        if (data?.onUpdateEvaluation) {
          const updatedEvaluation = transformEvaluation(data.onUpdateEvaluation)
          if (updatedEvaluation) {
            onEvaluationUpdate(updatedEvaluation)
          }
        }
      },
      error: (error: Error) => {
        console.error('Error in evaluation update subscription:', error)
      }
    })
    subscriptions.push(evaluationSub)

    // Subscribe to task updates
    const taskSub = (currentClient.graphql({
      query: TASK_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTask: any } }) => {
        if (data?.onUpdateTask) {
          const updatedTask = data.onUpdateTask
          console.log('Task update received:', {
            taskId: updatedTask.id,
            status: updatedTask.status,
            stageCount: updatedTask.stages?.items?.length
          })
        }
      },
      error: (error: Error) => {
        console.error('Error in task update subscription:', error)
      }
    })
    subscriptions.push(taskSub)

    // Subscribe to task stage updates
    const stageSub = (currentClient.graphql({
      query: TASK_STAGE_UPDATE_SUBSCRIPTION
    }) as unknown as { subscribe: Function }).subscribe({
      next: ({ data }: { data?: { onUpdateTaskStage: any } }) => {
        if (data?.onUpdateTaskStage) {
          console.log('Stage update received:', {
            stageId: data.onUpdateTaskStage.id,
            taskId: data.onUpdateTaskStage.taskId,
            status: data.onUpdateTaskStage.status
          })
        }
      },
      error: (error: Error) => {
        console.error('Error in task stage update subscription:', error)
      }
    })
    subscriptions.push(stageSub)

    return () => {
      subscriptions.forEach(sub => sub.unsubscribe())
    }
  }, [accountId, onEvaluationUpdate, onEvaluationCreate, onEvaluationDelete])
} 
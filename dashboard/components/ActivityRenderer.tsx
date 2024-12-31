import React from 'react'
import { ActivityData, isEvaluationActivity, ScoringJobTaskData, EvaluationTaskData, OptimizationActivity } from '@/types/tasks'
import { BaseTaskProps } from '@/components/Task'
import EvaluationTaskComponent from '@/components/EvaluationTask'
import AlertTask from '@/components/AlertTask'
import ReportTask from '@/components/ReportTask'
import OptimizationTask from '@/components/OptimizationTask'
import FeedbackTask from '@/components/FeedbackTask'
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask'
import ScoringJobTask from '@/components/ScoringJobTask'

interface ActivityRendererProps {
  activity: ActivityData
  isFullWidth: boolean
  onClose: () => void
  onToggleFullWidth: () => void
}

type ScoringJobTaskProps = BaseTaskProps<ScoringJobTaskData>
type EvaluationTaskProps = BaseTaskProps<EvaluationTaskData>

const ActivityRenderer: React.FC<ActivityRendererProps> = ({
  activity,
  isFullWidth,
  onClose,
  onToggleFullWidth
}) => {
  switch (activity.type) {
    case 'Scoring Job':
      return (
        <ScoringJobTask 
          variant="detail" 
          task={{
            ...activity,
            data: {
              ...activity.data,
              status: activity.data?.status || 'pending',
              completedItems: activity.data?.completedItems || 0,
              totalItems: activity.data?.totalItems || 0
            }
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    case 'Evaluation completed':
    case 'Evaluation started':
      return isEvaluationActivity(activity) ? (
        <EvaluationTaskComponent
          variant="detail"
          task={{
            ...activity,
            data: {
              ...activity.data,
              status: activity.data?.status || 'pending'
            }
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      ) : null
    case 'Alert':
      return (
        <AlertTask 
          variant="detail" 
          task={{
            ...activity,
            data: {
              ...activity.data,
              iconType: activity.data?.iconType || 'info'
            }
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    case 'Report':
      return (
        <ReportTask 
          variant="detail" 
          task={activity}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    case 'Optimization started':
      return renderOptimizationTask(activity)
    case 'Feedback queue started':
    case 'Feedback queue completed':
      return (
        <FeedbackTask 
          variant="detail" 
          task={activity}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    case 'Score updated':
      return (
        <ScoreUpdatedTask 
          variant="detail" 
          task={activity}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
    default:
      return null
  }
}

const renderOptimizationTask = (activity: OptimizationActivity) => {
  return (
    <OptimizationTask
      variant="detail"
      task={activity}
      isFullWidth={false}
      onToggleFullWidth={() => {}}
      onClose={() => {}}
    />
  )
}

export default ActivityRenderer 
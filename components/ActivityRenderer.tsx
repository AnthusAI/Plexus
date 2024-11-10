import React from 'react'
import { ActivityData, isExperimentActivity, ScoringJobTaskData, ExperimentTaskData } from '@/types/tasks'
import { BaseTaskProps } from '@/components/Task'
import ExperimentTaskComponent from '@/components/ExperimentTask'
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
type ExperimentTaskProps = BaseTaskProps<ExperimentTaskData>

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
    case 'Experiment completed':
    case 'Experiment started':
      return isExperimentActivity(activity) ? (
        <ExperimentTaskComponent
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
      return (
        <OptimizationTask
          variant="detail"
          task={{
            ...activity,
            data: {
              ...activity.data,
              progress: activity.data?.progress || 0,
              accuracy: activity.data?.accuracy || 0,
              numberComplete: activity.data?.numberComplete || 0,
              numberTotal: activity.data?.numberTotal || 0,
              eta: activity.data?.eta || '00:00:00',
              elapsedTime: activity.data?.elapsedTime || '00:00:00',
              estimatedTimeRemaining: activity.data?.estimatedTimeRemaining || '00:00:00',
              processedItems: activity.data?.processedItems || 0,
              totalItems: activity.data?.totalItems || 0,
              before: activity.data?.before || { outerRing: [], innerRing: [] },
              after: activity.data?.after || { outerRing: [], innerRing: [] }
            }
          }}
          isFullWidth={isFullWidth}
          onToggleFullWidth={onToggleFullWidth}
          onClose={onClose}
        />
      )
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

export default ActivityRenderer 
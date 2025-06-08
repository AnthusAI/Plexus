import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { ListChecks, MoveUpRight } from 'lucide-react'
import BeforeAfterGauges from './BeforeAfterGauges'
import { BaseTaskData } from '@/types/base'

interface ScoreUpdatedTaskData extends BaseTaskData {
  before: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
  after: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
}

interface ScoreUpdatedTaskProps extends BaseTaskProps<ScoreUpdatedTaskData> {}

const ScoreUpdatedTask: React.FC<ScoreUpdatedTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const data = task.data as ScoreUpdatedTaskData
  const gaugeVariant = variant === 'nested' ? 'detail' : variant

  const visualization = React.useMemo(() => (
    <div className="w-full max-w-full">
      <BeforeAfterGauges
        title={task.description || 'Metric'}
        before={data.before?.innerRing[0]?.value ?? 0}
        after={data.after?.innerRing[0]?.value ?? 0}
        variant={gaugeVariant}
        backgroundColor="var(--gauge-background)"
      />
    </div>
  ), [data.before, data.after, task.description, variant])

  return (
    <Task 
      variant={variant} 
      task={task} 
      onClick={onClick} 
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
                            <ListChecks className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
}

export default ScoreUpdatedTask

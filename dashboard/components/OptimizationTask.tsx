import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from './Task'
import { Sparkles } from 'lucide-react'
import BeforeAfterGauges from './BeforeAfterGauges'
import { ProgressBar } from '@/components/ui/progress-bar'

interface OptimizationTaskData {
  id: string
  title: string
  progress: number
  accuracy: number
  numberComplete: number
  numberTotal: number
  eta: string
  processedItems: number
  totalItems: number
  before: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
  after: {
    outerRing: Array<{ category: string; value: number; fill: string }>
    innerRing: Array<{ category: string; value: number; fill: string }>
  }
  elapsedTime: string
  estimatedTimeRemaining: string
  elapsedSeconds: number | null
  estimatedRemainingSeconds: number | null
}

interface OptimizationTaskProps extends BaseTaskProps<OptimizationTaskData> {}

const OptimizationTask: React.FC<OptimizationTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const data = task.data as OptimizationTaskData
  const gaugeVariant = variant === 'nested' ? 'detail' : variant

  const visualization = (
    <div className="flex flex-col items-center w-full">
      <BeforeAfterGauges
        title={task.description || 'Metric'}
        before={data.before?.innerRing[0]?.value ?? 0}
        after={data.after?.innerRing[0]?.value ?? 0}
        variant={gaugeVariant}
        backgroundColor="var(--gauge-background)"
      />
      {data && (
        <div className="mt-4 w-full">
          <ProgressBar 
            progress={data.progress ?? 0}
            elapsedTime={data.elapsedTime}
            processedItems={data.numberComplete}
            totalItems={data.numberTotal}
            estimatedTimeRemaining={data.eta}
            color="primary"
          />
        </div>
      )}
    </div>
  )

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
            <Sparkles className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization} />
      )}
    />
  )
}

export default OptimizationTask

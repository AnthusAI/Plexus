import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { FlaskConical } from 'lucide-react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'
import TaskProgress from './TaskProgress'

interface ExperimentTaskData {
  accuracy?: number
  progress?: number
  elapsedTime?: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
  processingRate?: number
}

// Export this interface
export interface ExperimentTaskProps extends Omit<TaskComponentProps, 'renderHeader' | 'renderContent'> {
  task: {
    id: number;
    type: string;
    scorecard: string;
    score: string;
    time: string;
    summary: string;
    description?: string;
    data?: ExperimentTaskData;
  };
}

const ExperimentTask: React.FC<ExperimentTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
}) => {
  const data = task.data as ExperimentTaskData

  const innerPieData = [
    { name: 'Positive', value: data?.accuracy || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data?.accuracy || 0), fill: 'var(--false)' }
  ]

  const outerPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  const visualization = (
    <div className="h-[120px] w-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={innerPieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={40}
            fill="#8884d8"
            strokeWidth={0}
          />
          <Pie
            data={outerPieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={45}
            outerRadius={55}
            fill="#82ca9d"
            strokeWidth={0}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )

  return (
    <Task 
      variant={variant} 
      task={task} 
      onClick={onClick} 
      controlButtons={controlButtons}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <FlaskConical className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && (
            <TaskProgress 
              progress={data.progress ?? 0}
              elapsedTime={data.elapsedTime ?? ''}
              processedItems={data.processedItems ?? 0}
              totalItems={data.totalItems ?? 0}
              estimatedTimeRemaining={data.estimatedTimeRemaining ?? ''}
              processingRate={data.processingRate ?? 0}
            />
          )}
        </TaskContent>
      )}
    />
  )
}

export default ExperimentTask

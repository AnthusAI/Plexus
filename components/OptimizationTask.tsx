import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Sparkles } from 'lucide-react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'
import TaskProgress from './TaskProgress'

interface OptimizationTaskData {
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  estimatedTimeRemaining?: string
  processingRate?: number
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
}

const OptimizationTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({
  variant,
  task,
  onClick,
  controlButtons,
}) => {
  const data = task.data as OptimizationTaskData

  const beforeInnerPieData = [
    { name: 'Positive', value: data?.before?.innerRing[0]?.value || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data?.before?.innerRing[0]?.value || 0), fill: 'var(--false)' }
  ]

  const beforeOuterPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  const afterInnerPieData = [
    { name: 'Positive', value: data?.after?.innerRing[0]?.value || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data?.after?.innerRing[0]?.value || 0), fill: 'var(--false)' }
  ]

  const afterOuterPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  const visualization = (
    <div className="flex space-x-4">
      <div className="h-[120px] w-[120px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={beforeInnerPieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={40}
              fill="#8884d8"
              strokeWidth={0}
            />
            <Pie
              data={beforeOuterPieData}
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
      <div className="h-[120px] w-[120px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={afterInnerPieData}
              dataKey="value"
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={40}
              fill="#8884d8"
              strokeWidth={0}
            />
            <Pie
              data={afterOuterPieData}
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
            <Sparkles className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && (
            <TaskProgress 
              progress={data.progress ?? 0}
              elapsedTime={data.elapsedTime ?? ''}
              processedItems={data.numberComplete ?? 0}
              totalItems={data.numberTotal ?? 0}
              estimatedTimeRemaining={data.estimatedTimeRemaining ?? ''}
              processingRate={data.processingRate ?? 0}
            />
          )}
        </TaskContent>
      )}
    />
  )
}

export default OptimizationTask


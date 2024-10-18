import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { ListTodo, MoveUpRight } from 'lucide-react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'

interface ScoreUpdatedTaskData {
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
}

// Move PieChartComponent outside the main component
const PieChartComponent: React.FC<{
  innerData: Array<{ name: string; value: number; fill: string }>
  outerData: Array<{ name: string; value: number; fill: string }>
  label: string
}> = React.memo(({ innerData, outerData, label }) => (
  <div className="text-center">
    <div className="text-sm font-medium mb-1">{label}</div>
    <div className="h-[70px] w-[70px] sm:h-[80px] sm:w-[80px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={innerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={24}
            fill="#8884d8"
            strokeWidth={0}
            paddingAngle={0}
          />
          <Pie
            data={outerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={28}
            outerRadius={35}
            fill="#82ca9d"
            strokeWidth={0}
            paddingAngle={0}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  </div>
))

const ScoreUpdatedTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({ variant, task, onClick, controlButtons }) => {
  const data = task.data as ScoreUpdatedTaskData

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

  const visualization = React.useMemo(() => (
    <div className="flex flex-col items-center w-full mt-4 xs:mt-0">
      <div className="flex space-x-4">
        <PieChartComponent
          innerData={beforeInnerPieData}
          outerData={beforeOuterPieData}
          label="Before"
        />
        <PieChartComponent
          innerData={afterInnerPieData}
          outerData={afterOuterPieData}
          label="After"
        />
      </div>
    </div>
  ), [beforeInnerPieData, beforeOuterPieData, afterInnerPieData, afterOuterPieData])

  const customSummary = (
    <div className="flex items-center">
      <span>{data?.before?.innerRing[0]?.value ?? 0}%</span>
      <MoveUpRight className="h-6 w-6 mx-1" />
      <span>{data?.after?.innerRing[0]?.value ?? 0}%</span>
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
            <ListTodo className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent 
          {...props} 
          visualization={visualization}
          customSummary={customSummary}
        />
      )}
    />
  )
}

export default ScoreUpdatedTask

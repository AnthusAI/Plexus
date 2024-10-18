import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { Progress } from '@/components/ui/progress'
import { Sparkles, MoveUpRight } from 'lucide-react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'

interface AnalysisTaskData {
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
  progress?: number
  elapsedTime?: string
  numberComplete?: number
  numberTotal?: number
  eta?: string
}

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

const AnalysisTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({ variant, task, onClick, controlButtons }) => {
  const data = task.data as AnalysisTaskData

  const beforeInnerPieData = React.useMemo(() => [
    { name: 'Positive', value: data?.before?.innerRing[0]?.value || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data?.before?.innerRing[0]?.value || 0), fill: 'var(--false)' }
  ], [data?.before?.innerRing])

  const beforeOuterPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  const afterInnerPieData = React.useMemo(() => [
    { name: 'Positive', value: data?.after?.innerRing[0]?.value || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data?.after?.innerRing[0]?.value || 0), fill: 'var(--false)' }
  ], [data?.after?.innerRing])

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
  ), [beforeInnerPieData, afterInnerPieData])

  const customSummary = React.useMemo(() => (
    <div className="flex items-center">
      <span>{data?.before?.innerRing[0]?.value ?? 0}%</span>
      <MoveUpRight className="h-5 w-5 mx-1" />
      <span>{data?.after?.innerRing[0]?.value ?? 0}%</span>
    </div>
  ), [data?.before?.innerRing, data?.after?.innerRing])

  return (
    <Task 
      variant={variant} 
      task={task} 
      onClick={onClick} 
      controlButtons={controlButtons}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <Sparkles className="h-5 w-5" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent 
          {...props} 
          visualization={visualization}
          customSummary={customSummary}
        >
          {data && (
            <div className="mt-4">
              <div className="flex justify-between text-xs mb-1">
                <div className="font-semibold">Progress: {data.progress}%</div>
                <div>{data.elapsedTime}</div>
              </div>
              <Progress value={data.progress} className="w-full h-4" />
              <div className="flex justify-between text-xs mt-1">
                <div>{data.numberComplete}/{data.numberTotal}</div>
                <div>ETA: {data.eta}</div>
              </div>
            </div>
          )}
        </TaskContent>
      )}
    />
  )
}

export default AnalysisTask

import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { ListTodo, MoveUpRight } from 'lucide-react'
import BeforeAfterGauges from './BeforeAfterGauges'

interface ScoreUpdatedTaskData {
  before?: {
    innerRing: Array<{ value: number }>
  }
  after?: {
    innerRing: Array<{ value: number }>
  }
}

const ScoreUpdatedTask: React.FC<
  Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>
> = ({ variant, task, onClick, controlButtons }) => {
  const data = task.data as ScoreUpdatedTaskData

  const visualization = React.useMemo(() => (
    <div className="w-full">
      <BeforeAfterGauges
        title={task.scorecard}
        before={data.before?.innerRing[0]?.value ?? 0}
        after={data.after?.innerRing[0]?.value ?? 0}
        variant={variant}
        backgroundColor="var(--background)"
      />
    </div>
  ), [data.before, data.after, task.scorecard, variant])

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
        <TaskContent {...props}>
          <div className="flex flex-col w-full gap-4">
            {visualization}
            {customSummary}
          </div>
        </TaskContent>
      )}
    />
  )
}

export default ScoreUpdatedTask

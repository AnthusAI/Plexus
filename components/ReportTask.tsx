import React from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { FileText } from 'lucide-react'

const ReportTask: React.FC<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = ({ variant, task, onClick, controlButtons }) => {
  const visualization = (
    <div className="flex items-center justify-center h-[120px] w-[120px]">
      {/* Add any specific visualization for ReportTask here */}
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
            <FileText className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent 
          {...props} 
          visualization={visualization}
        >
          {/* Additional content can be added here if needed */}
        </TaskContent>
      )}
    />
  )
}

export default ReportTask

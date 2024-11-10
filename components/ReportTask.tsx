import React from 'react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { FileText } from 'lucide-react'
import { ReportTaskData } from '@/types/tasks'
import { BaseTaskProps } from '@/components/Task'

interface ReportTaskProps extends BaseTaskProps<ReportTaskData> {}

const ReportTask: React.FC<ReportTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  const visualization = (
    <div className="flex items-center justify-center h-[120px] w-[120px]">
      <FileText className="h-6 w-6 text-primary" />
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

import React from 'react'
import { Task, TaskHeader, TaskContent, BaseTaskProps } from '@/components/Task'
import { FileBarChart, Clock } from 'lucide-react'
import { format, formatDistanceToNow } from 'date-fns'
import { Timestamp } from '@/components/ui/timestamp'

// Define the data structure for report tasks
export interface ReportTaskData {
  id: string;
  title: string; // Required by BaseTaskData
  name?: string | null;
  configName?: string | null;
  configDescription?: string | null;
  createdAt?: string | null;
  /** 
   * Last updated timestamp of the report - used for displaying the "last updated" time 
   * This is preferred over task.time when available
   */
  updatedAt?: string | null;
}

// Props for the ReportTask component
export interface ReportTaskProps extends BaseTaskProps<ReportTaskData> {}

const ReportTask: React.FC<ReportTaskProps> = ({ 
  variant, 
  task, 
  onClick, 
  controlButtons,
  isFullWidth,
  onToggleFullWidth,
  onClose
}) => {
  // Format the timestamp for detail view display
  const formattedDetailTimestamp = task.data?.updatedAt 
    ? format(new Date(task.data.updatedAt), 'MMM d, yyyy h:mm a')
    : '';

  // Helper to check if a value exists and is not empty
  const getValueOrEmpty = (value: string | null | undefined): string => {
    return value && value.trim() !== '' ? value : '';
  };

  // Explicitly set the name and description in the correct order
  // name = Report name (from report.name)
  // description = Report configuration description
  const reportName = task.data?.configName || 'Report';
  const reportDescription = getValueOrEmpty(task.data?.configDescription);

  // Create a properly typed data object
  const reportData: ReportTaskData = {
    id: task.data?.id || task.id,
    title: task.data?.title || reportName,
    name: task.data?.name || null,
    configName: task.data?.configName || null,
    configDescription: task.data?.configDescription || null,
    createdAt: task.data?.createdAt || null,
    updatedAt: task.data?.updatedAt || null
  };

  return (
    <Task 
      variant={variant} 
      task={{
        ...task,
        // Explicitly set name and description in the right order
        name: reportName, 
        description: reportDescription,
        // Empty scorecard and score to prevent automatic generation
        scorecard: '',
        score: '',
        // Use properly typed data object
        data: reportData
      }}
      onClick={onClick} 
      controlButtons={controlButtons}
      isFullWidth={isFullWidth}
      onToggleFullWidth={onToggleFullWidth}
      onClose={onClose}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <FileBarChart className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} hideTaskStatus={true}>
          {/* Removed redundant "Last updated" timestamp section */}
        </TaskContent>
      )}
    />
  )
}

export default ReportTask

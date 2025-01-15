import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Activity } from 'lucide-react'

const meta = {
  title: 'Tasks/Task',
  component: Task,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Task>

export default meta
type Story = StoryObj<typeof Task>

const createTask = (id: string, overrides = {}) => ({
  id,
  type: 'Sample Task',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  summary: 'Task Summary',
  description: 'Task Description',
  ...overrides
})

const TaskStoryHeader = (props: any) => (
  <TaskHeader {...props}>
    <div className="flex justify-end w-full">
      <Activity className="h-6 w-6" />
    </div>
  </TaskHeader>
)

const TaskStoryContent = (props: any) => (
  <TaskContent {...props} />
)

export const Starting: Story = {
  args: {
    variant: 'grid',
    task: createTask('starting', {
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'RUNNING',
          processedItems: 20,
          totalItems: 100,
          statusMessage: 'Loading data from database...'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Processing data...'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing...'
        }
      ],
      currentStageName: 'Initialization',
      status: 'RUNNING',
      elapsedTime: '15s',
      estimatedTimeRemaining: '2m 45s',
      summary: 'Starting task execution'
    }),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Processing: Story = {
  args: {
    variant: 'grid',
    task: createTask('processing', {
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Analyzing metrics and trends...'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing...'
        }
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      elapsedTime: '1m 30s',
      estimatedTimeRemaining: '1m 15s',
      summary: 'Processing data'
    }),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Finishing: Story = {
  args: {
    variant: 'grid',
    task: createTask('finishing', {
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Analysis complete'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'RUNNING',
          processedItems: 80,
          totalItems: 100,
          statusMessage: 'Generating output...'
        }
      ],
      currentStageName: 'Finishing',
      status: 'RUNNING',
      elapsedTime: '2m 45s',
      estimatedTimeRemaining: '15s',
      summary: 'Finalizing task'
    }),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Complete: Story = {
  args: {
    variant: 'grid',
    task: createTask('complete', {
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Analysis complete'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Task completed successfully'
        }
      ],
      currentStageName: 'Finishing',
      status: 'COMPLETED',
      elapsedTime: '3m 0s',
      summary: 'Task completed'
    }),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Failed: Story = {
  args: {
    variant: 'grid',
    task: createTask('failed', {
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'FAILED',
          processedItems: 50,
          totalItems: 100,
          statusMessage: 'Error processing data: insufficient data'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing...'
        }
      ],
      currentStageName: 'Processing',
      status: 'FAILED',
      elapsedTime: '1m 45s',
      summary: 'Task failed'
    }),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Detail = {
  args: {
    variant: 'detail',
    task: Starting.args.task,
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (Story) => (
      <div className="w-[600px]">
        <Story />
      </div>
    ),
  ],
}

export const DetailFullWidth = {
  args: {
    ...Detail.args,
    isFullWidth: true,
  },
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <div className="w-full h-screen p-4">
        <Story />
      </div>
    ),
  ],
}

export const NoProgress = {
  args: {
    variant: 'grid',
    task: Processing.args.task,
    showProgress: false,
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Starting</div>
        <Task {...Starting.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Processing</div>
        <Task {...Processing.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Finishing</div>
        <Task {...Finishing.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <Task {...Complete.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <Task {...Failed.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">No Progress</div>
        <Task {...NoProgress.args} />
      </div>
    </div>
  ),
}
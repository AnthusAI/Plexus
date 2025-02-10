import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Task, TaskHeader, TaskContent, TaskComponentProps, BaseTaskProps } from '../components/Task'
import { Activity } from 'lucide-react'

const meta = {
  title: 'Tasks/Task',
  component: Task,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Task>

export default meta
type Story = StoryObj<TaskComponentProps<unknown>>

const createTask = (id: string, overrides = {}) => ({
  id,
  type: 'Sample Task',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  description: 'Task Description',
  ...overrides
})

const TaskStoryHeader = (props: BaseTaskProps<unknown>) => (
  <TaskHeader {...props}>
    <div className="flex justify-end w-full">
      <Activity className="h-6 w-6" />
    </div>
  </TaskHeader>
)

const TaskStoryContent = (props: BaseTaskProps<unknown>) => (
  <TaskContent {...props} />
)

const baseArgs: Omit<TaskComponentProps<unknown>, 'task'> = {
  variant: 'grid',
  renderHeader: TaskStoryHeader,
  renderContent: TaskStoryContent,
  showProgress: true,
  isFullWidth: false,
  isLoading: false,
}

const sampleStages = [
  {
    key: 'Initializing',
    label: 'Initializing',
    color: 'bg-primary',
    name: 'Initializing',
    order: 0,
    status: 'COMPLETED' as const,
    processedItems: 100,
    totalItems: 100,
    statusMessage: 'Data loaded'
  },
  {
    key: 'Processing',
    label: 'Processing',
    color: 'bg-secondary',
    name: 'Processing',
    order: 1,
    status: 'RUNNING' as const,
    processedItems: 45,
    totalItems: 100,
    statusMessage: 'Processing activity data...'
  },
  {
    key: 'Finalizing',
    label: 'Finalizing',
    color: 'bg-primary',
    name: 'Finalizing',
    order: 2,
    status: 'PENDING' as const,
    processedItems: 0,
    totalItems: 100,
    statusMessage: 'Finalizing...'
  }
]

const stories = {
  Starting: {
    args: {
      ...baseArgs,
      task: createTask('starting', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        statusMessage: 'Initializing task...'
      }),
    },
  },
  Announced: {
    args: {
      ...baseArgs,
      showPreExecutionStages: true,
      task: createTask('announced', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        dispatchStatus: 'DISPATCHED',
        celeryTaskId: '',
        statusMessage: 'Activity announced...'
      }),
    },
  },
  Claimed: {
    args: {
      ...baseArgs,
      showPreExecutionStages: true,
      task: createTask('claimed', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        dispatchStatus: 'DISPATCHED',
        celeryTaskId: 'task-123',
        statusMessage: 'Activity claimed.'
      }),
    },
  },
} as const

export const Starting: Story = stories.Starting
export const Announced: Story = stories.Announced
export const Claimed: Story = stories.Claimed

export const Initializing: Story = {
  args: {
    ...baseArgs,
    task: createTask('initializing', {
      stages: [
        {
          ...sampleStages[0],
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Loading data...'
        },
        sampleStages[1],
        sampleStages[2]
      ],
      currentStageName: 'Initializing',
      status: 'RUNNING',
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
  },
}

export const Running: Story = {
  args: {
    ...baseArgs,
    task: createTask('running', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        sampleStages[2]
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
  },
}

export const NoStages: Story = {
  args: {
    ...baseArgs,
    task: createTask('nostages', {
      stages: [],
      currentStageName: 'Processing',
      processedItems: 45,
      totalItems: 100,
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s',
      status: 'RUNNING',
      statusMessage: 'Fetching report list...'
    }),
  },
}

export const Finalizing: Story = {
  args: {
    ...baseArgs,
    task: createTask('finalizing', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Processing complete'
        },
        {
          ...sampleStages[2],
          status: 'RUNNING',
          statusMessage: 'Generating final report...'
        }
      ],
      currentStageName: 'Finalizing',
      status: 'RUNNING',
      elapsedTime: '4m 45s'
    }),
  },
}

export const Complete: Story = {
  args: {
    ...baseArgs,
    task: createTask('complete', {
      stages: sampleStages.map(stage => ({
        ...stage,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
      })),
      currentStageName: 'Complete',
      status: 'COMPLETED',
      elapsedTime: '5m 0s'
    }),
  },
}

export const Failed: Story = {
  args: {
    ...baseArgs,
    task: createTask('failed', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'FAILED',
          processedItems: 50,
          totalItems: 100,
          statusMessage: 'Error: Insufficient data for report generation'
        },
        sampleStages[2]
      ],
      currentStageName: 'Processing',
      status: 'FAILED',
      elapsedTime: '2m 15s'
    }),
  },
}

export const NoProgress: Story = {
  args: {
    ...baseArgs,
    task: createTask('noprogress', {
      stages: [
        {
          name: 'Initializing',
          order: 0,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 1,
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        {
          name: 'Finalizing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing...'
        }
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
    showProgress: false,
  },
}

export const Detail: Story = {
  args: {
    variant: 'detail',
    task: createTask('1', {
      type: 'Starting',
      description: 'Task is starting...'
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[600px]">
        <StoryFn />
      </div>
    )
  ]
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

export const Demo = {
  render: () => {
    const storyList = [
      { title: 'Starting', args: stories.Starting.args },
      { title: 'Announced', args: stories.Announced.args },
      { title: 'Claimed', args: stories.Claimed.args },
      { title: 'Initializing', args: Initializing.args },
      { title: 'Running', args: Running.args },
      { title: 'No Stages', args: NoStages.args },
      { title: 'Finalizing', args: Finalizing.args },
      { title: 'Complete', args: Complete.args },
      { title: 'Failed', args: Failed.args },
      { title: 'No Progress', args: NoProgress.args },
    ].filter((story): story is { title: string; args: TaskComponentProps<unknown> } => 
      story.args !== undefined
    )

    return (
      <div className="space-y-8">
        {storyList.map(({ title, args }) => (
          <div key={title}>
            <div className="text-sm text-muted-foreground mb-2">{title}</div>
            <Task {...args} />
          </div>
        ))}
      </div>
    )
  },
}
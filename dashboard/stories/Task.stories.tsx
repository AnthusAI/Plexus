import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Task, TaskHeader, TaskContent, TaskComponentProps, BaseTaskProps } from '../components/Task'
import { Activity } from 'lucide-react'
import { BaseTaskData } from '@/types/base'

interface TaskStoryData extends BaseTaskData {
  id: string
  title: string
  description?: string
  command?: string
  elapsedTime?: string
  estimatedTimeRemaining?: string
}

const meta = {
  title: 'Tasks/Task',
  component: Task,
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    commandDisplay: {
      control: 'select',
      options: ['hide', 'show', 'full'],
      defaultValue: 'show',
      description: 'Controls how to display the command'
    },
    statusMessageDisplay: {
      control: 'select',
      options: ['always', 'never', 'error-only'],
      defaultValue: 'always',
      description: 'Controls when to display the status message'
    }
  }
} satisfies Meta<typeof Task>

export default meta
type Story = StoryObj<TaskComponentProps<TaskStoryData>>

const createTask = (id: string, overrides = {}) => ({
  id,
  type: 'Sample Task',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  description: 'Task Description',
  command: 'python process_data.py --input data.csv --output results.json',
  data: {
    id,
    title: 'Sample Task',
    description: 'Task Description',
    command: 'python process_data.py --input data.csv --output results.json'
  },
  ...overrides
})

const TaskStoryHeader = (props: BaseTaskProps<TaskStoryData>) => (
  <TaskHeader {...props}>
    <div className="flex justify-end w-full">
      <Activity className="h-6 w-6" />
    </div>
  </TaskHeader>
)

const TaskStoryContent = (props: BaseTaskProps<TaskStoryData>) => (
  <TaskContent {...props} />
)

const baseArgs: Omit<TaskComponentProps<TaskStoryData>, 'task'> = {
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

export const DetailFullWidth: Story = {
  args: {
    ...Detail.args,
    isFullWidth: true,
  },
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story: React.ComponentType) => (
      <div className="w-full h-screen p-4">
        <Story />
      </div>
    ),
  ],
}

export const DetailWithFullCommand: Story = {
  args: {
    variant: 'detail',
    task: createTask('command-test', {
      type: 'Test Task',
      command: 'python process_data.py --input /very/long/path/to/input/data.csv --output /another/very/long/path/to/output/results.json --config /path/to/config.yaml --verbose --debug --log-level INFO --batch-size 1000 --workers 4 --additional-param value --another-param "some value with spaces" --yet-another-param=123',
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
    commandDisplay: 'full'
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[800px]">
        <StoryFn />
      </div>
    )
  ]
}

export const Command: Story = {
  render: () => {
    const longCommand = 'python process_data.py --input /very/long/path/to/input/data.csv --output /another/very/long/path/to/output/results.json --config /path/to/config.yaml --verbose --debug --log-level INFO --batch-size 1000 --workers 4'
    
    const variants: Array<{
      title: string;
      args: TaskComponentProps<TaskStoryData>;
    }> = [
      {
        title: 'Hidden Command',
        args: {
          ...baseArgs,
          commandDisplay: 'hide',
          task: createTask('command-hidden', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      },
      {
        title: 'Single Line (Truncated)',
        args: {
          ...baseArgs,
          commandDisplay: 'show',
          task: createTask('command-single', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      },
      {
        title: 'Full Command (Wrapped)',
        args: {
          ...baseArgs,
          commandDisplay: 'full',
          task: createTask('command-full', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      }
    ]

    return (
      <div className="space-y-8">
        {variants.map(({ title, args }) => (
          <div key={title}>
            <div className="text-sm text-muted-foreground mb-2">{title}</div>
            <Task {...args} />
          </div>
        ))}
      </div>
    )
  }
}

export const StatusMessageAlwaysShown: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'always',
    task: createTask('status-always', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
  },
}

export const StatusMessageNeverShown: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'never',
    task: createTask('status-never', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
  },
}

export const StatusMessageErrorOnly: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'error-only',
    task: createTask('status-error', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'FAILED',
      processedItems: 45,
      totalItems: 100,
      errorMessage: 'Failed to process data: Invalid format'
    }),
  },
}

export const StatusMessageErrorOnlyWithoutError: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'error-only',
    task: createTask('status-error-no-error', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'This message should not be shown'
    }),
  },
}
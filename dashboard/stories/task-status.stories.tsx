import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import { TaskStatus, TaskStageConfig, TaskStatusProps } from '../components/ui/task-status'
import { Radio, Triangle } from 'lucide-react'

const meta = {
  title: 'Progress Bars/TaskStatus',
  component: TaskStatus,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof TaskStatus>

export default meta
type Story = StoryObj<typeof TaskStatus>

const sampleStages: TaskStageConfig[] = [
  {
    key: 'Initializing',
    label: 'Initializing',
    color: 'bg-primary',
    name: 'Initializing',
    order: 0,
    status: 'COMPLETED',
    startedAt: new Date(Date.now() - 300000).toISOString(),
    completedAt: new Date(Date.now() - 240000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() - 240000).toISOString(),
  },
  {
    key: 'Processing',
    label: 'Processing',
    color: 'bg-secondary',
    name: 'Processing',
    order: 1,
    status: 'RUNNING',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 240000).toISOString(),
    completedAt: new Date(Date.now() - 60000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() - 60000).toISOString(),
  },
  {
    key: 'Finalizing',
    label: 'Finalizing',
    color: 'bg-primary',
    name: 'Finalizing',
    order: 2,
    status: 'PENDING',
    startedAt: new Date(Date.now() - 60000).toISOString(),
    completedAt: new Date(Date.now() - 1000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() - 1000).toISOString(),
  }
]

export const Default: Story = {
  args: {
    stages: sampleStages,
    currentStageName: 'Processing',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 300000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() + 300000).toISOString(),
    status: 'RUNNING',
    stageConfigs: sampleStages,
    command: 'plexus command demo',
    statusMessage: 'Processing item 45 of 100...',
  },
}

export const NoProgress: Story = {
  args: {
    stages: sampleStages,
    currentStageName: 'Processing',
    startedAt: new Date(Date.now() - 300000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() + 300000).toISOString(),
    status: 'RUNNING',
    stageConfigs: sampleStages,
    command: 'plexus command demo',
    statusMessage: 'Processing...',
  },
}

export const Failed: Story = {
  args: {
    stages: sampleStages,
    currentStageName: 'Processing',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 300000).toISOString(),
    completedAt: new Date(Date.now() - 100000).toISOString(),
    status: 'FAILED',
    stageConfigs: sampleStages,
    command: 'plexus command demo',
    statusMessage: 'Error: Something went wrong',
  },
}

export const NoStages: Story = {
  args: {
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 300000).toISOString(),
    estimatedCompletionAt: new Date(Date.now() + 300000).toISOString(),
    status: 'RUNNING',
    command: 'plexus command demo',
    statusMessage: 'Processing item 45 of 100...',
  },
}

export const PreExecution: Story = {
  args: {
    status: 'PENDING',
    showPreExecutionStages: true,
    dispatchStatus: 'PENDING',
    celeryTaskId: undefined,
    workerNodeId: undefined,
  },
}

export const PreExecutionAnnounced: Story = {
  args: {
    status: 'PENDING',
    showPreExecutionStages: true,
    dispatchStatus: 'PENDING',
    celeryTaskId: 'task-123',
    workerNodeId: undefined,
  },
}

export const PreExecutionClaimed: Story = {
  args: {
    status: 'PENDING',
    showPreExecutionStages: true,
    dispatchStatus: 'PENDING',
    celeryTaskId: 'task-123',
    workerNodeId: 'worker-1',
  },
}

export const Completed: Story = {
  args: {
    stages: sampleStages,
    currentStageName: 'Finalizing',
    processedItems: 100,
    totalItems: 100,
    startedAt: new Date(Date.now() - 300000).toISOString(),
    completedAt: new Date(Date.now() - 100000).toISOString(),
    status: 'COMPLETED',
    stageConfigs: sampleStages,
    command: 'plexus command demo',
    statusMessage: 'Processing complete',
  },
}

export const All: Story = {
  render: () => (
    <div className="space-y-4">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Default</div>
        <TaskStatus {...(Default.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">No Progress</div>
        <TaskStatus {...(NoProgress.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Pre-execution</div>
        <TaskStatus {...(PreExecution.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Pre-execution (Announced)</div>
        <TaskStatus {...(PreExecutionAnnounced.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Pre-execution (Claimed)</div>
        <TaskStatus {...(PreExecutionClaimed.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Completed</div>
        <TaskStatus {...(Completed.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <TaskStatus {...(Failed.args as Required<TaskStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">No Stages</div>
        <TaskStatus {...(NoStages.args as Required<TaskStatusProps>)} />
      </div>
    </div>
  )
} 
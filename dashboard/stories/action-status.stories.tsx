import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import { ActionStatus, ActionStageConfig, ActionStatusProps } from '../components/ui/action-status'
import { Radio, Triangle } from 'lucide-react'

const meta = {
  title: 'Progress Bars/ActionStatus',
  component: ActionStatus,
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
} satisfies Meta<typeof ActionStatus>

export default meta
type Story = StoryObj<typeof ActionStatus>

const sampleStages: ActionStageConfig[] = [
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

export const Starting: Story = {
  args: {
    showStages: true,
    stages: [],
    stageConfigs: [],
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    command: 'plexus report generate --type monthly',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status message
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Initializing task...')).toBeInTheDocument()
    
    // Verify starting state
    await expect(canvas.getByText('Starting...')).toBeInTheDocument()
    
    // Verify radio icon is present and pulsing
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-pulse')
    
    // Verify empty segmented progress bar is shown
    const progressBar = canvas.getByRole('list')
    await expect(progressBar).toBeInTheDocument()
    await expect(progressBar.children).toHaveLength(0)
  }
}

export const Announced: Story = {
  args: {
    showStages: true,
    stages: [],
    stageConfigs: [],
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    dispatchStatus: 'DISPATCHED',
    celeryTaskId: '',
    showPreExecutionStages: true,
    command: 'plexus report generate --type monthly',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status message
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Initializing task...')).toBeInTheDocument()
    
    // Verify announced state
    await expect(canvas.getByText('Activity announced...')).toBeInTheDocument()
    
    // Verify concierge bell icon is present and jiggling
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-jiggle')
  }
}

export const Claimed: Story = {
  args: {
    showStages: true,
    stages: [],
    stageConfigs: [],
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    dispatchStatus: 'DISPATCHED',
    celeryTaskId: 'task-123',
    showPreExecutionStages: true,
    command: 'plexus report generate --type monthly',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status message
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Initializing task...')).toBeInTheDocument()
    
    // Verify claimed state
    await expect(canvas.getByText('Activity claimed.')).toBeInTheDocument()
    
    // Verify hand icon is present and waving
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-wave')
  }
}

export const Initializing: Story = {
  args: {
    showStages: true,
    stages: sampleStages,
    stageConfigs: sampleStages,
    currentStageName: 'Initializing',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 135000).toISOString(), // 2m 15s ago
    estimatedCompletionAt: new Date(Date.now() + 165000).toISOString(), // 2m 45s from now
    status: 'RUNNING',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Loading data...'
  }
}

export const Running: Story = {
  args: {
    showStages: true,
    stages: sampleStages,
    stageConfigs: sampleStages,
    currentStageName: 'Processing',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 135000).toISOString(), // 2m 15s ago
    estimatedCompletionAt: new Date(Date.now() + 165000).toISOString(), // 2m 45s from now
    status: 'RUNNING',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Processing activity data...'
  }
}

export const NoStages: Story = {
  args: {
    showStages: false,
    stages: sampleStages,
    stageConfigs: sampleStages,
    currentStageName: 'Processing',
    processedItems: 45,
    totalItems: 100,
    startedAt: new Date(Date.now() - 135000).toISOString(), // 2m 15s ago
    estimatedCompletionAt: new Date(Date.now() + 165000).toISOString(), // 2m 45s from now
    status: 'RUNNING',
    command: 'plexus report list',
    statusMessage: 'Fetching report list...'
  }
}

export const Finalizing: Story = {
  args: {
    showStages: true,
    stages: sampleStages.map(stage => ({
      ...stage,
      status: stage.name === 'Finalizing' ? 'RUNNING' as const : 'COMPLETED' as const
    })),
    stageConfigs: sampleStages,
    currentStageName: 'Finalizing',
    processedItems: 100,
    totalItems: 100,
    startedAt: new Date(Date.now() - 285000).toISOString(), // 4m 45s ago
    status: 'RUNNING',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Generating PDF report...'
  }
}

export const Complete: Story = {
  args: {
    showStages: true,
    stages: sampleStages.map(stage => ({
      ...stage,
      status: 'COMPLETED' as const,
      startedAt: new Date(Date.now() - 300000).toISOString(),
      completedAt: new Date(Date.now() - 1000).toISOString(),
      estimatedCompletionAt: new Date(Date.now() - 1000).toISOString()
    })),
    stageConfigs: sampleStages.map(stage => ({
      ...stage,
      status: 'COMPLETED' as const,
      startedAt: new Date(Date.now() - 300000).toISOString(),
      completedAt: new Date(Date.now() - 1000).toISOString(),
      estimatedCompletionAt: new Date(Date.now() - 1000).toISOString()
    })),
    currentStageName: 'Complete',
    processedItems: 100,
    totalItems: 100,
    startedAt: new Date(Date.now() - 300000).toISOString(), // 5m ago
    estimatedCompletionAt: new Date(Date.now() - 1000).toISOString(), // Just completed
    status: 'COMPLETED',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Report generated successfully'
  }
}

export const Failed: Story = {
  args: {
    showStages: true,
    stages: [
      ...sampleStages.map(stage => ({
        ...stage,
        status: 'COMPLETED' as const,
        startedAt: new Date(Date.now() - 135000).toISOString(),
        completedAt: new Date(Date.now() - 1000).toISOString(),
        estimatedCompletionAt: new Date(Date.now() - 1000).toISOString()
      })),
      {
        key: 'Complete',
        label: 'Complete',
        color: 'bg-false',
        name: 'Complete',
        order: 3,
        status: 'FAILED' as const,
        startedAt: new Date(Date.now() - 135000).toISOString(),
        completedAt: new Date(Date.now() - 1000).toISOString(),
        estimatedCompletionAt: new Date(Date.now() - 1000).toISOString()
      }
    ],
    stageConfigs: sampleStages.map(stage => ({
      ...stage,
      status: 'COMPLETED' as const,
      startedAt: new Date(Date.now() - 135000).toISOString(),
      completedAt: new Date(Date.now() - 1000).toISOString(),
      estimatedCompletionAt: new Date(Date.now() - 1000).toISOString()
    })),
    currentStageName: 'Complete',
    startedAt: new Date(Date.now() - 135000).toISOString(), // 2m 15s ago
    estimatedCompletionAt: new Date(Date.now() - 1000).toISOString(), // Just failed
    status: 'FAILED',
    errorLabel: 'Failed',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Error: Insufficient data for report generation'
  }
}


export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Starting</div>
        <ActionStatus {...(Starting.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Announced</div>
        <ActionStatus {...(Announced.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Claimed</div>
        <ActionStatus {...(Claimed.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Initializing</div>
        <ActionStatus {...(Initializing.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Running</div>
        <ActionStatus {...(Running.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Finalizing</div>
        <ActionStatus {...(Finalizing.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <ActionStatus {...(Complete.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <ActionStatus {...(Failed.args as Required<ActionStatusProps>)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">No Stages</div>
        <ActionStatus {...(NoStages.args as Required<ActionStatusProps>)} />
      </div>
    </div>
  )
} 
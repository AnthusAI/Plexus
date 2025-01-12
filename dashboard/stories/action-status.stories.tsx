import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import { ActionStatus, ActionStageConfig, ActionStatusProps } from '../components/ui/action-status'

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
    name: 'Startup',
    order: 0,
    status: 'COMPLETED',
  },
  {
    name: 'Processing',
    order: 1,
    status: 'RUNNING',
    processedItems: 45,
    totalItems: 100,
  },
  {
    name: 'Finalizing',
    order: 2,
    status: 'PENDING',
  },
  {
    name: 'Complete',
    order: 3,
    status: 'PENDING',
  }
]

const defaultStageConfigs = [
  { key: 'Startup', label: 'Startup', color: 'bg-primary' },
  { key: 'Processing', label: 'Processing', color: 'bg-secondary' },
  { key: 'Finalizing', label: 'Finalizing', color: 'bg-primary' },
  { key: 'Complete', label: 'Complete', color: 'bg-true' }
]

const baseArgs = {
  showStages: true as const,
  stages: sampleStages,
  stageConfigs: defaultStageConfigs,
  currentStageName: 'Processing',
  processedItems: 45,
  totalItems: 100,
  elapsedTime: '2m 15s',
  estimatedTimeRemaining: '2m 45s',
  status: 'RUNNING' as const
}

export const Running: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify stage labels are present
    await expect(canvas.getByText('Startup')).toBeInTheDocument()
    await expect(canvas.getByText('Processing')).toBeInTheDocument()
    await expect(canvas.getByText('Finalizing')).toBeInTheDocument()
    await expect(canvas.getByText('Complete')).toBeInTheDocument()
    
    // Verify progress information
    await expect(canvas.getByText('45%')).toBeInTheDocument()
    
    // Verify time information
    await expect(canvas.getByText(/Elapsed: 2m 15s/)).toBeInTheDocument()
    await expect(canvas.getByText('ETA:')).toBeInTheDocument()
    await expect(canvas.getByText('2m 45s')).toBeInTheDocument()
  }
}

export const NoStages: Story = {
  args: {
    ...baseArgs,
    showStages: false,
  }
}

export const Finalizing: Story = {
  args: {
    ...baseArgs,
    stages: [
      { ...sampleStages[0], status: 'COMPLETED' },
      { ...sampleStages[1], status: 'COMPLETED' },
      { ...sampleStages[2], status: 'RUNNING' },
      { ...sampleStages[3], status: 'PENDING' }
    ],
    currentStageName: 'Finalizing',
    processedItems: 100,
    totalItems: 100,
    elapsedTime: '4m 45s',
    status: 'RUNNING' as const
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify completed stages have primary color
    const startupSegment = canvas.getByText('Startup').closest('div')
    const finalizingSegment = canvas.getByText('Finalizing').closest('div')
    await expect(startupSegment).toHaveClass('bg-primary')
    await expect(finalizingSegment).toHaveClass('bg-primary')
    
    // Verify progress
    await expect(canvas.getByText('100%')).toBeInTheDocument()
    await expect(canvas.getByText(/Elapsed: 4m 45s/)).toBeInTheDocument()
  }
}

export const Complete: Story = {
  args: {
    ...baseArgs,
    stages: sampleStages.map(s => ({ ...s, status: 'COMPLETED' as const })),
    currentStageName: 'Complete',
    processedItems: 100,
    totalItems: 100,
    elapsedTime: '5m 0s',
    status: 'COMPLETED' as const
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify all stages are completed
    const completeSegment = canvas.getByText('Complete').closest('div')
    await expect(completeSegment).toHaveClass('bg-true')
    
    // Verify final progress state
    await expect(canvas.getByText('100%')).toBeInTheDocument()
    await expect(canvas.getByText(/Elapsed: 5m 0s/)).toBeInTheDocument()
    await expect(canvas.getByText('Done')).toBeInTheDocument()
  }
}

export const Failed: Story = {
  args: {
    ...baseArgs,
    stageConfigs: defaultStageConfigs,
    stages: [
      { name: 'Startup', order: 0, status: 'COMPLETED' },
      { name: 'Processing', order: 1, status: 'COMPLETED' },
      { name: 'Finalizing', order: 2, status: 'COMPLETED' },
      { name: 'Complete', order: 3, status: 'FAILED' }
    ],
    currentStageName: 'Complete',
    elapsedTime: '2m 15s',
    status: 'FAILED' as const,
    errorLabel: 'Failed'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify stage progression
    await expect(canvas.getByText('Startup')).toBeInTheDocument()
    await expect(canvas.getByText('Processing')).toBeInTheDocument()
    await expect(canvas.getByText('Finalizing')).toBeInTheDocument()
    
    // Verify error state
    const failedSegment = canvas.getByText('Failed')
    await expect(failedSegment).toBeInTheDocument()
    const failedContainer = failedSegment.closest('div')
    await expect(failedContainer).toHaveClass('bg-false')
  }
}

export const Pending: Story = {
  args: {
    ...baseArgs,
    stages: sampleStages.map(s => ({ ...s, status: 'PENDING' as const })),
    processedItems: 0,
    status: 'PENDING' as const
  }
}

export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Pending</div>
        <ActionStatus {...(Pending.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Running</div>
        <ActionStatus {...(Running.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Finalizing</div>
        <ActionStatus {...(Finalizing.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <ActionStatus {...(Complete.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <ActionStatus {...(Failed.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">No Stages</div>
        <ActionStatus {...(NoStages.args as ActionStatusProps)} />
      </div>
    </div>
  )
} 
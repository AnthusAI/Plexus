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
  }
]

const defaultStageConfigs = [
  { key: 'Startup', label: 'Startup', color: 'bg-primary' },
  { key: 'Processing', label: 'Processing', color: 'bg-secondary' },
  { key: 'Finalizing', label: 'Finalizing', color: 'bg-primary' }
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
  status: 'RUNNING' as const,
  command: 'plexus report generate --type monthly',
  statusMessage: 'Processing activity data...'
}

export const Running: Story = {
  args: baseArgs,
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status message
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Processing activity data...')).toBeInTheDocument()
    
    // Verify stage labels and states
    await expect(canvas.getByText('Startup')).toBeInTheDocument()
    await expect(canvas.getByText('Processing')).toBeInTheDocument()
    await expect(canvas.getByText('Finalizing')).toBeInTheDocument()
    
    // Verify progress information
    await expect(canvas.getByText('45')).toBeInTheDocument()
    await expect(canvas.getByText('/')).toBeInTheDocument()
    await expect(canvas.getByText('100')).toBeInTheDocument()
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
    command: 'plexus report list',
    statusMessage: 'Fetching report list...'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status are shown
    await expect(canvas.getByText('plexus report list')).toBeInTheDocument()
    await expect(canvas.getByText('Fetching report list...')).toBeInTheDocument()
    
    // Verify progress information is shown without stages
    await expect(canvas.getByText('45%')).toBeInTheDocument()
    await expect(canvas.getByText('45')).toBeInTheDocument()
    await expect(canvas.getByText('100')).toBeInTheDocument()
    
    // Verify timing information
    await expect(canvas.getByText(/Elapsed: 2m 15s/)).toBeInTheDocument()
    await expect(canvas.getByText('2m 45s')).toBeInTheDocument()
    
    // Verify stages are not shown
    const stagesContainer = canvas.queryByRole('list')
    await expect(stagesContainer).not.toBeInTheDocument()
  }
}

export const Finalizing: Story = {
  args: {
    ...baseArgs,
    stages: [
      { ...sampleStages[0], status: 'COMPLETED' },
      { ...sampleStages[1], status: 'COMPLETED' },
      { ...sampleStages[2], status: 'RUNNING' },
    ],
    currentStageName: 'Finalizing',
    processedItems: 100,
    totalItems: 100,
    elapsedTime: '4m 45s',
    status: 'RUNNING' as const,
    command: 'plexus report generate --type monthly',
    statusMessage: 'Generating PDF report...'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Generating PDF report...')).toBeInTheDocument()
    
    // Verify stage progression
    const startupSegment = canvas.getByText('Startup').closest('div')
    const processingSegment = canvas.getByText('Processing').closest('div')
    const finalizingSegment = canvas.getByText('Finalizing').closest('div')
    
    await expect(startupSegment).toHaveClass('bg-primary')
    await expect(processingSegment).toHaveClass('bg-secondary')
    await expect(finalizingSegment).toHaveClass('bg-primary')
    
    // Verify progress state
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
    status: 'COMPLETED' as const,
    command: 'plexus report generate --type monthly',
    statusMessage: 'Report generated successfully'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and status
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Report generated successfully')).toBeInTheDocument()
    
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
    errorLabel: 'Failed',
    command: 'plexus report generate --type monthly',
    statusMessage: 'Error: Insufficient data for report generation'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify command and error message
    await expect(canvas.getByText('plexus report generate --type monthly')).toBeInTheDocument()
    await expect(canvas.getByText('Error: Insufficient data for report generation')).toBeInTheDocument()
    
    // Verify stage progression
    await expect(canvas.getByText('Startup')).toBeInTheDocument()
    await expect(canvas.getByText('Processing')).toBeInTheDocument()
    await expect(canvas.getByText('Finalizing')).toBeInTheDocument()
    
    // Verify error state
    const failedSegment = canvas.getByText('Failed')
    await expect(failedSegment).toBeInTheDocument()
    const failedContainer = failedSegment.closest('div')
    await expect(failedContainer).toHaveClass('bg-false')
    
    // Verify progress bar shows error state
    const progressBar = canvas.getByRole('progressbar')
    await expect(progressBar).toHaveClass('bg-false')
    
    // Verify timing information is preserved
    await expect(canvas.getByText(/Elapsed: 2m 15s/)).toBeInTheDocument()
  }
}

export const Pending: Story = {
  args: {
    ...baseArgs,
    stages: sampleStages.map(s => ({ ...s, status: 'PENDING' as const })),
    processedItems: 0,
    status: 'PENDING' as const,
    currentStageName: 'Startup'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Verify all stages are in pending state
    await expect(canvas.getByText('Startup')).toBeInTheDocument()
    await expect(canvas.getByText('Processing')).toBeInTheDocument()
    await expect(canvas.getByText('Finalizing')).toBeInTheDocument()
    
    // Verify initial progress state
    await expect(canvas.getByText('0')).toBeInTheDocument()
    await expect(canvas.getByText('100')).toBeInTheDocument()
    await expect(canvas.getByText('0%')).toBeInTheDocument()
    
    // Verify no progress has been made
    const progressBar = canvas.getByRole('progressbar')
    await expect(progressBar).toHaveAttribute('style', expect.stringContaining('width: 0%'))
  }
}

export const PreExecution: Story = {
  args: {
    ...baseArgs,
    showPreExecutionStages: true,
    dispatchStatus: '',
    celeryTaskId: '',
    workerNodeId: '',
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    stages: sampleStages.map(s => ({ ...s, status: 'PENDING' })),
    currentStageName: undefined
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Activity not yet announced...')).toBeInTheDocument()
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-pulse')
  }
}

export const Announced: Story = {
  args: {
    ...baseArgs,
    showPreExecutionStages: true,
    dispatchStatus: 'DISPATCHED',
    celeryTaskId: '',
    workerNodeId: '',
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    stages: sampleStages.map(s => ({ ...s, status: 'PENDING' })),
    currentStageName: undefined
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Activity announced...')).toBeInTheDocument()
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-pulse')
  }
}

export const Claimed: Story = {
  args: {
    ...baseArgs,
    showPreExecutionStages: true,
    dispatchStatus: 'DISPATCHED',
    celeryTaskId: 'task-123',
    workerNodeId: '',
    status: 'PENDING',
    processedItems: 0,
    totalItems: 100,
    stages: sampleStages.map(s => ({ ...s, status: 'PENDING' })),
    currentStageName: undefined
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Activity claimed.')).toBeInTheDocument()
    const icon = canvas.getByRole('img', { hidden: true })
    await expect(icon).toHaveClass('animate-bounce')
  }
}

export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Pre-Execution</div>
        <ActionStatus {...(PreExecution.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Announced</div>
        <ActionStatus {...(Announced.args as ActionStatusProps)} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Claimed</div>
        <ActionStatus {...(Claimed.args as ActionStatusProps)} />
      </div>
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
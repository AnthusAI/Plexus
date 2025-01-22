import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { BatchJobProgressBar } from '../components/ui/batch-job-progress-bar'

const meta = {
  title: 'Progress Bars/BatchJobProgressBar',
  component: BatchJobProgressBar,
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
} satisfies Meta<typeof BatchJobProgressBar>

export default meta
type Story = StoryObj<typeof BatchJobProgressBar>

export const Open: Story = {
  args: {
    status: 'OPEN'
  }
}

export const Closed: Story = {
  args: {
    status: 'CLOSED'
  }
}

export const Processing: Story = {
  args: {
    status: 'RUNNING'
  }
}

export const Complete: Story = {
  args: {
    status: 'COMPLETED'
  }
}

export const Failed: Story = {
  args: {
    status: 'FAILED'
  }
}

export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Open</div>
        <BatchJobProgressBar status="OPEN" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Closed</div>
        <BatchJobProgressBar status="CLOSED" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Processing</div>
        <BatchJobProgressBar status="RUNNING" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <BatchJobProgressBar status="COMPLETED" />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <BatchJobProgressBar status="FAILED" />
      </div>
    </div>
  )
} 
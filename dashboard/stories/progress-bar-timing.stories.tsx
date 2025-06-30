import React from "react"
import type { Meta, StoryObj } from '@storybook/react'
import { ProgressBarTiming } from '../components/ui/progress-bar-timing'

const meta = {
  title: 'General/Components/ProgressBarTiming',
  component: ProgressBarTiming,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProgressBarTiming>

export default meta
type Story = StoryObj<typeof ProgressBarTiming>

export const InProgress = {
  args: {
    elapsedTime: "2m 30s",
    estimatedTimeRemaining: "1m 15s",
    isInProgress: true,
    isFocused: false,
  },
}

export const Focused = {
  args: {
    elapsedTime: "2m 30s",
    estimatedTimeRemaining: "1m 15s",
    isInProgress: true,
    isFocused: true,
  },
}

export const Complete = {
  args: {
    elapsedTime: "5m 0s",
    estimatedTimeRemaining: "0s",
    isInProgress: false,
    isFocused: false,
  },
}

export const ElapsedOnly = {
  args: {
    elapsedTime: "2m 30s",
    isInProgress: true,
    isFocused: false,
  },
}

export const EstimatedOnly = {
  args: {
    estimatedTimeRemaining: "1m 15s",
    isInProgress: true,
    isFocused: false,
  },
}

export const Demo = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">In Progress</div>
        <ProgressBarTiming {...InProgress.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Focused</div>
        <ProgressBarTiming {...Focused.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <ProgressBarTiming {...Complete.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Elapsed Time Only</div>
        <ProgressBarTiming {...ElapsedOnly.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Estimated Time Only</div>
        <ProgressBarTiming {...EstimatedOnly.args} />
      </div>
    </div>
  ),
} 
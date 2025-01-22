import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SegmentedProgressBar, SegmentConfig } from '../components/ui/segmented-progress-bar'

const meta = {
  title: 'Progress Bars/SegmentedProgressBar',
  component: SegmentedProgressBar,
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
} satisfies Meta<typeof SegmentedProgressBar>

export default meta
type Story = StoryObj<typeof SegmentedProgressBar>

const sampleSegments: SegmentConfig[] = [
  { key: 'start', label: 'Start', color: 'bg-primary' },
  { key: 'middle', label: 'Middle', color: 'bg-secondary' },
  { key: 'end', label: 'End', color: 'bg-true' }
]

const baseArgs = {
  segments: sampleSegments,
  error: false
} as const

export const AtStart: Story = {
  args: {
    ...baseArgs,
    currentSegment: 'start'
  }
}

export const InMiddle: Story = {
  args: {
    ...baseArgs,
    currentSegment: 'middle'
  }
}

export const AtEnd: Story = {
  args: {
    ...baseArgs,
    currentSegment: 'end'
  }
}

export const WithError: Story = {
  args: {
    ...baseArgs,
    currentSegment: 'end',
    error: true,
    errorLabel: 'Error'
  }
}

export const WithCustomErrorLabel: Story = {
  args: {
    ...baseArgs,
    currentSegment: 'end',
    error: true,
    errorLabel: 'Failed'
  }
}

export const CustomColors: Story = {
  args: {
    segments: [
      { key: 'one', label: 'One', color: 'bg-blue-500' },
      { key: 'two', label: 'Two', color: 'bg-green-500' },
      { key: 'three', label: 'Three', color: 'bg-purple-500' }
    ],
    currentSegment: 'two',
    error: false
  }
}

export const Demo: Story = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">At Start</div>
        <SegmentedProgressBar {...AtStart.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">In Middle</div>
        <SegmentedProgressBar {...InMiddle.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">At End</div>
        <SegmentedProgressBar {...AtEnd.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">With Error</div>
        <SegmentedProgressBar {...WithError.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">With Custom Error Label</div>
        <SegmentedProgressBar {...WithCustomErrorLabel.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Custom Colors</div>
        <SegmentedProgressBar {...CustomColors.args} />
      </div>
    </div>
  )
} 
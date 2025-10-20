import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import MetricsSummary from '@/components/MetricsSummary'
import { Card } from '@/components/ui/card'

const meta = {
  title: 'General/Components/MetricsSummary',
  component: MetricsSummary,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof MetricsSummary>

export default meta
type Story = StoryObj<typeof MetricsSummary>

const otherMetricsSegments = [
  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
  { start: 60, end: 85, color: 'var(--gauge-converging)' },
  { start: 85, end: 100, color: 'var(--gauge-great)' }
]

export const Default: Story = {
  args: {
    gauge: {
      value: 85,
      label: 'Accuracy',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    evaluationUrl: '/lab/evaluations/abc123'
  },
  render: (args) => (
    <Card className="bg-card p-4 w-[200px]">
      <MetricsSummary {...args} />
    </Card>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Accuracy')).toBeInTheDocument()
  }
}

export const HighAccuracy: Story = {
  args: {
    gauge: {
      value: 95,
      label: 'Accuracy',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    evaluationUrl: '/lab/evaluations/abc123'
  },
  render: (args) => (
    <Card className="bg-card p-4 w-[200px]">
      <MetricsSummary {...args} />
    </Card>
  )
}

export const LowAccuracy: Story = {
  args: {
    gauge: {
      value: 55,
      label: 'Accuracy',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    evaluationUrl: '/lab/evaluations/abc123'
  },
  render: (args) => (
    <Card className="bg-card p-4 w-[200px]">
      <MetricsSummary {...args} />
    </Card>
  )
}

export const RecentEvaluation: Story = {
  args: {
    gauge: {
      value: 82,
      label: 'Accuracy',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    evaluationUrl: '/lab/evaluations/recent123'
  },
  render: (args) => (
    <Card className="bg-card p-4 w-[200px]">
      <MetricsSummary {...args} />
    </Card>
  )
}

export const SmallDataset: Story = {
  args: {
    gauge: {
      value: 78,
      label: 'Accuracy',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    evaluationUrl: '/lab/evaluations/small123'
  },
  render: (args) => (
    <Card className="bg-card p-4 w-[200px]">
      <MetricsSummary {...args} />
    </Card>
  )
}

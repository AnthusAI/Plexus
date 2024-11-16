import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import MetricsGauges from '@/components/MetricsGauges'

const meta = {
  title: 'Visualization/MetricsGauges',
  component: MetricsGauges,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof MetricsGauges>

export default meta
type Story = StoryObj<typeof MetricsGauges>

const otherMetricsSegments = [
  { start: 0, end: 60, color: 'var(--gauge-inviable)' },
  { start: 60, end: 85, color: 'var(--gauge-converging)' },
  { start: 85, end: 100, color: 'var(--gauge-great)' }
]

const createGaugeConfig = (accuracy: number) => ({
  gauges: [{
    value: accuracy,
    label: 'Accuracy',
    backgroundColor: 'var(--gauge-background)',
  }]
})

const createDetailGaugeConfig = (
  accuracy: number,
  sensitivity: number,
  specificity: number,
  precision: number
) => ({
  gauges: [
    {
      value: accuracy,
      label: 'Accuracy',
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: precision,
      label: 'Precision',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
      priority: true
    },
    {
      value: sensitivity,
      label: 'Sensitivity',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
    {
      value: specificity,
      label: 'Specificity',
      segments: otherMetricsSegments,
      backgroundColor: 'var(--gauge-background)',
    },
  ]
})

export const Grid: Story = {
  args: {
    ...createGaugeConfig(75),
    variant: 'grid'
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('Accuracy')).toBeInTheDocument()
    await expect(canvas.getByText('75%')).toBeInTheDocument()
  }
}

export const Detail: Story = {
  args: {
    ...createDetailGaugeConfig(92, 89, 95, 91),
    variant: 'detail',
    metricsExplanation: "This experiment uses accuracy as the primary metric, along with precision and sensitivity to provide a complete picture of model performance across all classes."
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    await expect(canvas.getByText('Accuracy')).toBeInTheDocument()
    await expect(canvas.getByText('Sensitivity')).toBeInTheDocument()
    await expect(canvas.getByText('Specificity')).toBeInTheDocument()
    await expect(canvas.getByText('Precision')).toBeInTheDocument()
    
    await expect(canvas.getByText('92%')).toBeInTheDocument()
    await expect(canvas.getByText('89%')).toBeInTheDocument()
    await expect(canvas.getByText('95%')).toBeInTheDocument()
    await expect(canvas.getByText('91%')).toBeInTheDocument()
  }
}

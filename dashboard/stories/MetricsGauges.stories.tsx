import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { expect, within } from '@storybook/test'
import MetricsGauges from '@/components/MetricsGauges'
import { Card } from '@/components/ui/card'

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
  render: (args) => (
    <Card>
      <MetricsGauges {...args} />
    </Card>
  ),
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
    metricsExplanation: "This evaluation uses accuracy as the primary metric, along with precision and sensitivity to provide a complete picture of model performance across all classes."
  },
  render: (args) => (
    <Card>
      <MetricsGauges {...args} />
    </Card>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // First verify all labels are present
    await expect(canvas.getByText('Accuracy')).toBeInTheDocument()
    await expect(canvas.getByText('Sensitivity')).toBeInTheDocument()
    await expect(canvas.getByText('Specificity')).toBeInTheDocument()
    await expect(canvas.getByText('Precision')).toBeInTheDocument()

    // Get all gauge containers
    const gauges = canvas.getAllByTestId('gauge-container')
    
    // Check each gauge has correct value
    const accuracyGauge = gauges.find(g => within(g).queryByText('Accuracy'))
    const sensitivityGauge = gauges.find(g => within(g).queryByText('Sensitivity'))
    const specificityGauge = gauges.find(g => within(g).queryByText('Specificity'))
    const precisionGauge = gauges.find(g => within(g).queryByText('Precision'))

    await expect(within(accuracyGauge!).getByText('92%', { selector: '.text-\\[2\\.25rem\\]' })).toBeInTheDocument()
    await expect(within(sensitivityGauge!).getByText('89%', { selector: '.text-\\[2\\.25rem\\]' })).toBeInTheDocument()
    await expect(within(specificityGauge!).getByText('95%', { selector: '.text-\\[2\\.25rem\\]' })).toBeInTheDocument()
    await expect(within(precisionGauge!).getByText('91%', { selector: '.text-\\[2\\.25rem\\]' })).toBeInTheDocument()
  }
}

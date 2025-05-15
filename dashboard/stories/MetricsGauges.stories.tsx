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

const alignmentSegments = [
  { start: 0, end: 50, color: 'var(--gauge-inviable)' },      // Negative values (-1 to 0)
  { start: 50, end: 60, color: 'var(--gauge-converging)' },   // Low alignment (0 to 0.2)
  { start: 60, end: 75, color: 'var(--gauge-almost)' },       // Moderate alignment (0.2 to 0.5)
  { start: 75, end: 90, color: 'var(--gauge-viable)' },       // Good alignment (0.5 to 0.8)
  { start: 90, end: 100, color: 'var(--gauge-great)' }        // Excellent alignment (0.8 to 1.0)
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

const createAlignmentGaugeConfig = (
  alignment: number,
  alignmentTarget: number,
  accuracy: number,
  precision: number,
  recall: number
) => ({
  gauges: [
    {
      value: alignment,
      target: alignmentTarget,
      label: 'Alignment',
      segments: alignmentSegments,
      min: -1,
      max: 1,
      valueUnit: '',
      decimalPlaces: 2,
      backgroundColor: 'var(--gauge-background)',
      information: "Gwet's AC1 is an advanced agreement coefficient that measures inter-rater reliability, accounting for chance agreement more effectively than other metrics. Values range from -1 (complete disagreement) to 1 (perfect agreement), with 0 indicating random agreement. Values above 0.8 generally indicate strong agreement between multiple assessors."
    },
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
      value: recall,
      label: 'Recall',
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
    <Card className="bg-card-light p-6">
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
    <Card className="bg-card-light p-6">
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

export const DetailWithTarget: Story = {
  args: {
    ...createAlignmentGaugeConfig(0.82, 0.92, 88, 85, 82),
    variant: 'detail'
  },
  render: (args) => (
    <Card className="bg-card-light p-6">
      <MetricsGauges {...args} />
    </Card>
  ),
  play: async ({ canvasElement, args }) => {
    const canvas = within(canvasElement)
    
    // First verify all labels are present
    await expect(canvas.getByText('Alignment')).toBeInTheDocument()
    await expect(canvas.getByText('Accuracy')).toBeInTheDocument()
    await expect(canvas.getByText('Precision')).toBeInTheDocument()
    await expect(canvas.getByText('Recall')).toBeInTheDocument()

    // Get all gauge containers
    const gauges = canvas.getAllByTestId('gauge-container')
    
    // Check the alignment gauge has the correct value and target
    const alignmentGauge = gauges.find(g => within(g).queryByText('Alignment'))
    await expect(within(alignmentGauge!).getByText('0.76')).toBeInTheDocument()
    
    // Test that there are two needles in the gauge (current value and target)
    const svg = within(alignmentGauge!).getByText('0.76').closest('svg')
    const needles = svg?.querySelectorAll('path[d^="M 0,-"]')
    await expect(needles?.length).toBeGreaterThanOrEqual(2)
    
    // If ticks are shown, check for the target tick mark
    if (args.variant === 'detail') {
      const targetValue = canvas.getByText('0.92')
      await expect(targetValue).toBeInTheDocument()
    }
  }
}

export const DetailWithSelectedGauge: Story = {
  args: {
    ...createDetailGaugeConfig(92, 89, 95, 91),
    variant: 'detail',
    selectedIndex: 0,
    metricsExplanation: "This evaluation uses accuracy as the primary metric, along with precision and sensitivity to provide a complete picture of model performance across all classes."
  },
  render: (args) => (
    <Card className="bg-card-light p-6">
      <MetricsGauges {...args} />
    </Card>
  )
}

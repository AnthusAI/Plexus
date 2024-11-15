import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Gauge } from '../components/gauge'

export default {
  title: 'Visualization/Gauge',
  component: Gauge,
  tags: ['autodocs'],
} satisfies Meta<typeof Gauge>

type Story = StoryObj<typeof Gauge>

export const Default: Story = {
  args: {
    value: 75,
    title: 'Accuracy'
  }
}

export const Priority: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    priority: true
  }
}

export const CustomSegments: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    segments: [
      { start: 0, end: 60, color: 'var(--gauge-inviable)' },
      { start: 60, end: 85, color: 'var(--gauge-converging)' },
      { start: 85, end: 100, color: 'var(--gauge-great)' }
    ]
  }
}

export const CustomBackground: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    backgroundColor: 'var(--background)'
  },
  decorators: [
    (Story) => (
      <div className="bg-card p-6 rounded-lg">
        <Story />
      </div>
    )
  ]
}

export const NoValue: Story = {
  args: {
    title: 'Accuracy'
  }
}

export const LowValue: Story = {
  args: {
    value: 30,
    title: 'Accuracy'
  }
}

export const HighValue: Story = {
  args: {
    value: 95,
    title: 'Accuracy'
  }
}

export const NoTicks: Story = {
  args: {
    value: 75,
    title: 'Accuracy',
    showTicks: false
  }
}

export const MetricsGrid: Story = {
  render: () => (
    <div className="grid grid-cols-2 gap-8 max-w-4xl">
      <Gauge
        value={92.5}
        title="Accuracy"
        priority={true}
        information={
          "Accuracy measures the overall correctness of predictions, showing the " +
          "percentage of all cases (both positive and negative) that were " +
          "correctly classified."
        }
        informationUrl="https://example.com/ml-metrics/accuracy"
      />
      <Gauge
        value={88.3}
        title="Sensitivity"
        information={
          "Sensitivity (also called Recall) measures the ability to correctly " +
          "identify positive cases, showing the percentage of actual positive " +
          "cases that were correctly identified."
        }
        informationUrl="https://example.com/ml-metrics/sensitivity"
      />
      <Gauge
        value={95.7}
        title="Specificity"
        information={
          "Specificity measures the ability to correctly identify negative " +
          "cases, showing the percentage of actual negative cases that were " +
          "correctly identified."
        }
        informationUrl="https://example.com/ml-metrics/specificity"
      />
      <Gauge
        value={90.1}
        title="Precision"
        information={
          "Precision measures the accuracy of positive predictions, showing " +
          "the percentage of predicted positive cases that were actually positive."
        }
        informationUrl="https://example.com/ml-metrics/precision"
      />
    </div>
  )
}

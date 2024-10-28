import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import MetricsGauges from '../components/MetricsGauges'

const meta = {
  title: 'Components/MetricsGauges',
  component: MetricsGauges,
  args: {
    gauges: [
      { value: 92, label: 'Accuracy' },
      { value: 89.8, label: 'Balanced Accuracy' },
      { value: 95.2, label: 'ROC AUC' },
      { value: 88.7, label: 'PR AUC' },
    ]
  }
} satisfies Meta<typeof MetricsGauges>;

export default meta;
type Story = StoryObj<typeof MetricsGauges>;

export const Default: Story = {
  args: {
    gauges: [
      { value: 92, label: 'Accuracy' },
      { value: 89.8, label: 'Balanced Accuracy' },
      { value: 95.2, label: 'ROC AUC' },
      { value: 88.7, label: 'PR AUC' },
      { value: 90, label: 'Precision' },
      { value: 87.4, label: 'Recall' },
      { value: 88.7, label: 'F1 Score' },
      { value: 86.9, label: 'F-Beta Score' },
    ]
  }
}

export const FourMetrics: Story = {
  args: {
    gauges: [
      { value: 92, label: 'Accuracy' },
      { value: 90, label: 'Precision' },
      { value: 87.4, label: 'Recall' },
      { value: 88.7, label: 'F1 Score' },
    ]
  }
}

export const ThreeMetrics: Story = {
  args: {
    gauges: [
      { value: 92, label: 'Accuracy' },
      { value: 95, label: 'ROC AUC' },
      { value: 88.7, label: 'PR AUC' },
    ]
  }
}

import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import MetricsGauges from '../components/MetricsGauges'

export default {
  title: 'Tasks/MetricsGauges',
  component: MetricsGauges,
  tags: ['autodocs'],
} satisfies Meta<typeof MetricsGauges>

type Story = StoryObj<typeof MetricsGauges>

export const Default: Story = {
  args: {
    gauges: [
      { id: 'accuracy', value: 92, label: 'Accuracy' },
      { id: 'balanced_accuracy', value: 89.8, label: 'Balanced Accuracy' },
      { id: 'roc_auc', value: 95.2, label: 'ROC AUC' },
      { id: 'pr_auc', value: 88.7, label: 'PR AUC' },
      { id: 'precision', value: 90, label: 'Precision' },
      { id: 'recall', value: 87.4, label: 'Recall' },
      { id: 'f1', value: 88.7, label: 'F1 Score' },
      { id: 'fbeta', value: 86.9, label: 'F-Beta Score' },
    ]
  }
}

export const FourMetrics: Story = {
  args: {
    gauges: [
      { id: 'accuracy', value: 92, label: 'Accuracy' },
      { id: 'precision', value: 90, label: 'Precision' },
      { id: 'recall', value: 87.4, label: 'Recall' },
      { id: 'f1', value: 88.7, label: 'F1 Score' },
    ]
  }
}

export const ThreeMetrics: Story = {
  args: {
    gauges: [
      { id: 'accuracy', value: 92, label: 'Accuracy' },
      { id: 'roc_auc', value: 95, label: 'ROC AUC' },
      { id: 'pr_auc', value: 88.7, label: 'PR AUC' },
    ]
  }
}

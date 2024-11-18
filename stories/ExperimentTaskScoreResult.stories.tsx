import type { Meta, StoryObj } from '@storybook/react'
import { ExperimentTaskScoreResult } from '../components/ExperimentTaskScoreResult'

const meta: Meta<typeof ExperimentTaskScoreResult> = {
  title: 'Components/ExperimentTaskScoreResult',
  component: ExperimentTaskScoreResult,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof ExperimentTaskScoreResult>

export const Correct: Story = {
  args: {
    id: '1',
    value: 1,
    confidence: 0.95,
    metadata: JSON.stringify({
      predicted_value: 'Appointment Scheduling',
      true_value: 'Appointment Scheduling',
      label: 'Appointment Scheduling'
    }),
    correct: true
  },
}

export const Incorrect: Story = {
  args: {
    id: '2',
    value: 0,
    confidence: 0.75,
    metadata: JSON.stringify({
      predicted_value: 'Billing Question',
      true_value: 'Appointment Scheduling',
      label: 'Appointment Scheduling'
    }),
    correct: false
  },
}

export const NoConfidence: Story = {
  args: {
    id: '3',
    value: 1,
    metadata: JSON.stringify({
      predicted_value: 'Medical Question',
      true_value: 'Medical Question'
    }),
    correct: true
  },
}

export const Loading: Story = {
  args: {
    id: '4',
    value: 0,
    metadata: JSON.stringify({
      predicted_value: 'Processing...',
    })
  },
} 
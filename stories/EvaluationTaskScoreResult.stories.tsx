import type { Meta, StoryObj } from '@storybook/react'
import { EvaluationTaskScoreResult } from '../components/EvaluationTaskScoreResult'

const meta: Meta<typeof EvaluationTaskScoreResult> = {
  title: 'Components/EvaluationTaskScoreResult',
  component: EvaluationTaskScoreResult,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof EvaluationTaskScoreResult>

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
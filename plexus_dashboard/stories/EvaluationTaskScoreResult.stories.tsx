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
      results: {
        result1: {
          value: 'Appointment Scheduling',
          metadata: {
            human_label: 'Appointment Scheduling',
            correct: true,
            text: 'Sample text for appointment scheduling'
          },
          explanation: 'This is clearly about scheduling an appointment'
        }
      }
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
      results: {
        result1: {
          value: 'Billing Question',
          metadata: {
            human_label: 'Appointment Scheduling',
            correct: false,
            text: 'Sample text about scheduling'
          },
          explanation: 'The text appears to be about billing but is actually about scheduling'
        }
      }
    }),
    correct: false
  },
}

export const NoConfidence: Story = {
  args: {
    id: '3',
    value: 1,
    metadata: JSON.stringify({
      results: {
        result1: {
          value: 'Medical Question',
          metadata: {
            human_label: 'Medical Question',
            correct: true,
            text: 'Sample medical question text'
          }
        }
      }
    }),
    correct: true
  },
}

export const Loading: Story = {
  args: {
    id: '4',
    value: 0,
    metadata: JSON.stringify({
      results: {
        result1: {
          value: 'Processing...',
          metadata: {
            text: 'Content being processed'
          }
        }
      }
    })
  },
} 
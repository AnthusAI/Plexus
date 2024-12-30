import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { EvaluationTaskScoreResults } from '../components/EvaluationTaskScoreResults'

const meta: Meta<typeof EvaluationTaskScoreResults> = {
  title: 'Components/EvaluationTaskScoreResults',
  component: EvaluationTaskScoreResults,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof EvaluationTaskScoreResults>

const mockResults = [
  {
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
  },
  {
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
  },
  {
    id: '3',
    value: 1,
    confidence: 0.88,
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
  },
]

export const Default: Story = {
  args: {
    results: mockResults,
    accuracy: 85.5,
  },
  decorators: [
    (Story) => (
      <div className="w-[400px]">
        <Story />
      </div>
    ),
  ],
}

export const PerfectAccuracy: Story = {
  args: {
    results: mockResults.map(r => ({ ...r, value: 1 })),
    accuracy: 100,
  },
  decorators: Default.decorators,
}

export const LowAccuracy: Story = {
  args: {
    results: mockResults.map(r => ({ ...r, value: 0 })),
    accuracy: 25.5,
  },
  decorators: Default.decorators,
} 
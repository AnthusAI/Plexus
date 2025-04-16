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
    value: '1',
    confidence: 0.95,
    explanation: 'This is clearly about scheduling an appointment',
    metadata: {
      human_label: 'Appointment Scheduling',
      correct: true
    },
    itemId: null,
    trace: null
  },
  {
    id: '2',
    value: '0',
    confidence: 0.75,
    explanation: 'The text appears to be about billing but is actually about scheduling',
    metadata: {
      human_label: 'Appointment Scheduling',
      correct: false
    },
    itemId: null,
    trace: null
  },
  {
    id: '3',
    value: '1',
    confidence: 0.88,
    explanation: null,
    metadata: {
      human_label: 'Medical Question',
      correct: true
    },
    itemId: null,
    trace: null
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
    results: mockResults.map(r => ({ ...r, value: '1' })),
    accuracy: 100,
  },
  decorators: Default.decorators,
}

export const LowAccuracy: Story = {
  args: {
    results: mockResults.map(r => ({ ...r, value: '0' })),
    accuracy: 25.5,
  },
  decorators: Default.decorators,
} 
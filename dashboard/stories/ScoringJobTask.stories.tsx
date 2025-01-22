import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import ScoringJobTask from '@/components/ScoringJobTask'
import type { ScoringJobTaskProps } from '@/components/ScoringJobTask'

const meta = {
  title: 'Tasks/Types/ScoringJobTask',
  component: ScoringJobTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ScoringJobTask>

export default meta
type Story = StoryObj<typeof ScoringJobTask>

const defaultTask = {
  id: '1',
  type: 'Scoring Job',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: new Date().toISOString(),
  data: {
    type: 'scoring',
    status: 'running',
    modelProvider: 'OpenAI',
    modelName: 'gpt-4',
    totalRequests: 100,
    completedRequests: 50,
    failedRequests: 0,
    startedAt: new Date().toISOString(),
    scoringJobs: []
  }
}

export const Default = {
  args: {
    task: defaultTask
  }
}

export const WithError: Story = {
  args: {
    task: {
      ...defaultTask,
      data: {
        ...defaultTask.data,
        status: 'failed',
        errorMessage: 'Failed to connect to scoring service',
        totalItems: 300,
        completedItems: 145,
        batchJobs: [
          {
            id: '1',
            modelProvider: 'OpenAI',
            modelName: 'gpt-4',
            type: 'sentiment-analysis',
            status: 'failed',
            totalRequests: 100,
            completedRequests: 50,
            failedRequests: 50,
            errorMessage: 'API rate limit exceeded',
          },
          {
            id: '2',
            modelProvider: 'Anthropic',
            modelName: 'claude-2',
            type: 'categorization',
            status: 'canceled',
            totalRequests: 100,
            completedRequests: 0,
            failedRequests: 0,
          },
        ],
      },
    },
  },
}

export const Complete: Story = {
  args: {
    task: {
      ...defaultTask,
      data: {
        ...defaultTask.data,
        status: 'done',
        totalItems: 300,
        completedItems: 300,
        batchJobs: [
          {
            id: '1',
            modelProvider: 'OpenAI',
            modelName: 'gpt-4',
            type: 'sentiment-analysis',
            status: 'done',
            totalRequests: 100,
            completedRequests: 100,
            failedRequests: 0,
          },
          {
            id: '2',
            modelProvider: 'Anthropic',
            modelName: 'claude-2',
            type: 'categorization',
            status: 'done',
            totalRequests: 100,
            completedRequests: 100,
            failedRequests: 0,
          },
        ],
      },
    },
  },
}

export const DetailView: Story = {
  args: {
    variant: 'detail',
    task: defaultTask,
  },
  decorators: [
    (Story) => (
      <div className="w-[600px]">
        <Story />
      </div>
    ),
  ],
} 
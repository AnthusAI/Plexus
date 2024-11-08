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

const baseTask = {
  id: 1,
  type: 'Scoring Job',
  scorecard: 'Customer Satisfaction',
  score: 'Overall Score',
  time: '2 hours ago',
  summary: 'Scoring customer feedback',
  description: 'Processing batch of customer reviews',
  data: {
    status: 'in_progress',
    itemName: 'Q4 Reviews',
    scorecardName: 'Customer Satisfaction',
    totalItems: 300,
    completedItems: 145,
    batchJobs: [
      {
        id: '1',
        provider: 'OpenAI',
        type: 'sentiment-analysis',
        status: 'done',
        totalRequests: 100,
        completedRequests: 100,
        failedRequests: 0,
      },
      {
        id: '2',
        provider: 'Anthropic',
        type: 'categorization',
        status: 'in_progress',
        totalRequests: 100,
        completedRequests: 45,
        failedRequests: 0,
      },
      {
        id: '3',
        provider: 'Cohere',
        type: 'topic-extraction',
        status: 'pending',
        totalRequests: 100,
        completedRequests: 0,
        failedRequests: 0,
      },
    ],
  },
}

export const Default: Story = {
  args: {
    task: baseTask,
  },
}

export const WithError: Story = {
  args: {
    task: {
      ...baseTask,
      data: {
        ...baseTask.data,
        status: 'failed',
        errorMessage: 'Failed to connect to scoring service',
        totalItems: 300,
        completedItems: 145,
        batchJobs: [
          {
            id: '1',
            provider: 'OpenAI',
            type: 'sentiment-analysis',
            status: 'failed',
            totalRequests: 100,
            completedRequests: 50,
            failedRequests: 50,
            errorMessage: 'API rate limit exceeded',
          },
          {
            id: '2',
            provider: 'Anthropic',
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
      ...baseTask,
      data: {
        ...baseTask.data,
        status: 'done',
        totalItems: 300,
        completedItems: 300,
        batchJobs: baseTask.data.batchJobs?.map(job => ({
          ...job,
          status: 'done',
          completedRequests: 100,
        })),
      },
    },
  },
}

export const DetailView: Story = {
  args: {
    variant: 'detail',
    task: baseTask,
  },
  decorators: [
    (Story) => (
      <div className="w-[600px]">
        <Story />
      </div>
    ),
  ],
} 
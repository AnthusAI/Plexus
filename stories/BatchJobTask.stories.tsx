import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import BatchJobTask from '@/components/BatchJobTask';
import type { BatchJobTaskProps } from '@/components/BatchJobTask';

const meta = {
  title: 'Tasks/Types/BatchJobTask',
  component: BatchJobTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof BatchJobTask>;

export default meta;
type Story = StoryObj<typeof BatchJobTask>;

const baseTask = {
  id: 1,
  type: 'Batch Job',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  summary: 'Processing items',
  description: 'Processing a batch of items',
  data: {
    provider: 'OpenAI',
    type: 'inference',
    status: 'in_progress',
    totalRequests: 100,
    completedRequests: 65,
    failedRequests: 0,
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
        errorMessage: 'API rate limit exceeded',
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
        completedRequests: 100,
      },
    },
  },
}

export const Nested: Story = {
  args: {
    variant: 'nested',
    task: baseTask,
  },
}

export const NestedComplete: Story = {
  args: {
    variant: 'nested',
    task: {
      ...baseTask,
      data: {
        ...baseTask.data,
        status: 'done',
        completedRequests: 100,
      },
    },
  },
}
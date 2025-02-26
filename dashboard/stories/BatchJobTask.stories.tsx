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

const defaultTask = {
  id: '1',
  type: 'Batch Job',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: new Date().toISOString(),
  data: {
    id: '1',
    title: 'Batch Job Task',
    modelProvider: 'OpenAI',
    modelName: 'gpt-4',
    type: 'batch',
    status: 'running',
    totalRequests: 100,
    completedRequests: 50,
    failedRequests: 0,
    startedAt: new Date().toISOString(),
    estimatedEndAt: null,
    completedAt: null,
    errorMessage: undefined,
    errorDetails: {},
    scoringJobs: [],
    scoringJobCountCache: 0
  }
}

export const Default: Story = {
  args: {
    variant: 'grid',
    task: defaultTask
  }
}

export const WithError: Story = {
  args: {
    variant: 'grid',
    task: {
      ...defaultTask,
      data: {
        ...defaultTask.data,
        status: 'failed',
        errorMessage: 'API rate limit exceeded',
        errorDetails: { code: 429, message: 'API rate limit exceeded' }
      },
    },
  },
}

export const Complete: Story = {
  args: {
    variant: 'grid',
    task: {
      ...defaultTask,
      data: {
        ...defaultTask.data,
        status: 'done',
        completedRequests: 100,
        completedAt: new Date().toISOString()
      },
    },
  },
}

export const Nested: Story = {
  args: {
    variant: 'nested',
    task: defaultTask,
  },
}

export const NestedComplete: Story = {
  args: {
    variant: 'nested',
    task: {
      ...defaultTask,
      data: {
        ...defaultTask.data,
        status: 'done',
        completedRequests: 100,
        completedAt: new Date().toISOString()
      },
    },
  },
}
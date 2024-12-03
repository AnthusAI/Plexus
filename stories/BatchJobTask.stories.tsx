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
  summary: 'Test Summary',
  data: {
    type: 'batch',
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
        errorMessage: 'API rate limit exceeded',
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
        completedRequests: 100,
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
      },
    },
  },
}
import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import type { ExperimentTask as ExperimentTaskType } from '@/components/ExperimentTask';

const meta = {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ExperimentTask>;

export default meta;
type Story = StoryObj<typeof ExperimentTask>;

const createTask = (id: number, processedItems: number, totalItems: number): ExperimentTaskType => ({
  id,
  type: 'Experiment started',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  summary: 'Experiment Summary',
  description: 'Experiment Description',
  data: {
    accuracy: 75,
    sensitivity: 78,
    specificity: 82,
    precision: 80,
    elapsedTime: '01:30:00',
    processedItems,
    totalItems,
    estimatedTimeRemaining: '00:30:00',
  },
});

export const Single: Story = {
  args: {
    variant: 'grid',
    task: createTask(1, 75, 100),
  }
};

export const Detail: Story = {
  args: {
    variant: 'detail',
    task: createTask(2, 90, 100),
  }
};

export const InProgress: Story = {
  args: {
    variant: 'grid',
    task: createTask(3, 50, 100),
  }
};

export const Completed: Story = {
  args: {
    variant: 'grid',
    task: createTask(4, 100, 100),
  }
};

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import { BaseTaskProps } from '@/components/Task';

const meta = {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ExperimentTask>;

export default meta;
type Story = StoryObj<typeof ExperimentTask>;

const createTask = (id: number, processedItems: number, totalItems: number): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Experiment',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Experiment Summary',
    description: 'Experiment Description',
    data: {
      accuracy: 75,
      f1Score: 82,
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
    },
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid: Story = {
  args: createTask(1, 75, 100),
};

export const Detail: Story = {
  args: {
    ...createTask(2, 90, 100),
    variant: 'detail',
  },
};

export const InProgress: Story = {
  args: createTask(3, 50, 100),
};

export const Completed: Story = {
  args: createTask(4, 100, 100),
};

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import ExperimentTask from '../components/ExperimentTask';
import { TaskProps } from '../components/TaskProgress';

const meta: Meta<typeof ExperimentTask> = {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
};

export default meta;
type Story = StoryObj<typeof ExperimentTask>;

const createTask = (id: number, processedItems: number, totalItems: number): TaskProps => ({
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
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
      outerRing: [
        { category: 'Positive', value: 50, fill: 'var(--true)' },
        { category: 'Negative', value: 50, fill: 'var(--false)' },
      ],
      innerRing: [
        { category: 'Positive', value: 75, fill: 'var(--true)' },
        { category: 'Negative', value: 25, fill: 'var(--false)' },
      ],
    },
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 75, 100),
};

export const Detail: Story = {
  args: {
    ...createTask(2, 90, 100),
    variant: 'detail',
  },
};

export const Grid: Story = {
  args: createTask(1, 75, 100),
};

export const InProgress: Story = {
  args: createTask(4, 50, 100),
};

export const Completed: Story = {
  args: createTask(5, 100, 100),
};

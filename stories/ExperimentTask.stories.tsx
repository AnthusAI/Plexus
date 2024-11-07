import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import type { ExperimentTaskProps } from '@/components/ExperimentTask';

const meta = {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ExperimentTask>;

export default meta;
type Story = StoryObj<typeof ExperimentTask>;

const createTask = (id: number, processedItems: number, totalItems: number): ExperimentTaskProps => ({
  task: {
    id,
    type: 'Experiment started',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Experiment Summary',
    description: 'Experiment Description',
    data: {
      accuracy: 90,
      sensitivity: 92,
      specificity: 89,
      precision: 91,
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
      confusionMatrix: {
        matrix: [
          [45, 3, 2],
          [2, 43, 2],
          [1, 2, 40],
        ],
        labels: ["Positive", "Negative", "Neutral"],
      },
      progress: 75,
      inferences: 150,
      results: 100,
      cost: 5,
      status: 'In Progress'
    },
  },
});

export const Grid: Story = {
  args: createTask(1, 75, 100),
};

export const Detail: Story = {
  args: {
    ...createTask(2, 90, 100),
    variant: 'detail',
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
  },
  decorators: [
    (Story) => (
      <div className="w-[600px]">
        <Story />
      </div>
    ),
  ],
};

export const DetailFullWidth: Story = {
  args: {
    ...Detail.args,
    isFullWidth: true,
  },
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <div className="w-full h-screen p-4">
        <Story />
      </div>
    ),
  ],
};

export const GridWithMany = {
  render: () => (
    <div className="grid grid-cols-2 gap-4">
      <ExperimentTask {...createTask(1, 25, 100)} />
      <ExperimentTask {...createTask(2, 50, 100)} />
      <ExperimentTask {...createTask(3, 75, 100)} />
      <ExperimentTask {...createTask(4, 100, 100)} />
    </div>
  ),
};

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
    id: id.toString(),
    type: 'Experiment started',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Experiment Summary',
    description: 'Experiment Description',
    data: {
      accuracy: 90,
      metrics: [
        {
          name: "Accuracy",
          value: 90,
          unit: "%",
          maximum: 100,
          priority: true
        },
        {
          name: "Precision",
          value: 91,
          unit: "%",
          maximum: 100,
          priority: true
        },
        {
          name: "Sensitivity",
          value: 92,
          unit: "%",
          maximum: 100,
          priority: true
        },
        {
          name: "Specificity",
          value: 89,
          unit: "%",
          maximum: 100,
          priority: true
        }
      ],
      processedItems,
      totalItems,
      progress: Math.round((processedItems / totalItems) * 100),
      inferences: 150,
      cost: 5,
      status: 'In Progress',
      elapsedSeconds: 5400,
      estimatedRemainingSeconds: 1800,
      confusionMatrix: {
        matrix: [
          [45, 3, 2],
          [2, 43, 2],
          [1, 2, 40],
        ],
        labels: ["Positive", "Negative", "Neutral"],
      }
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

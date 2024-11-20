import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import EvaluationTask from '@/components/EvaluationTask';
import type { EvaluationTaskProps } from '@/components/EvaluationTask';

const meta = {
  title: 'Tasks/Types/EvaluationTask',
  component: EvaluationTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof EvaluationTask>;

export default meta;
type Story = StoryObj<typeof EvaluationTask>;

const createTask = (id: number, processedItems: number, totalItems: number): EvaluationTaskProps => ({
  task: {
    id: id.toString(),
    type: 'Evaluation started',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Evaluation Summary',
    description: 'Evaluation Description',
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
      <EvaluationTask {...createTask(1, 25, 100)} />
      <EvaluationTask {...createTask(2, 50, 100)} />
      <EvaluationTask {...createTask(3, 75, 100)} />
      <EvaluationTask {...createTask(4, 100, 100)} />
    </div>
  ),
};

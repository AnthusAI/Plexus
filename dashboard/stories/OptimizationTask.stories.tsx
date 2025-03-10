import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import OptimizationTask from '@/components/OptimizationTask';
import { BaseTaskProps } from '@/components/Task';
import type { OptimizationTaskData } from '@/components/OptimizationTask';

const meta: Meta<typeof OptimizationTask> = {
  title: 'Tasks/Types/OptimizationTask',
  component: OptimizationTask,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof OptimizationTask>;

interface OptimizationTaskStoryProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task'] & {
    data?: OptimizationTaskData
  }
}

const createTask = (
  id: number, 
  numberComplete: number, 
  numberTotal: number
): OptimizationTaskStoryProps => ({
  variant: 'grid',
  task: {
    id: id.toString(),
    type: 'optimization',
    scorecard: 'Optimization',
    score: '90',
    time: '1h 30m',
    data: {
      id: id.toString(),
      title: 'Optimization Task',
      before: {
        outerRing: [{ category: 'Accuracy', value: 70, fill: '#4CAF50' }],
        innerRing: [{ category: 'Accuracy', value: 70, fill: '#4CAF50' }]
      },
      after: {
        outerRing: [{ category: 'Accuracy', value: 90, fill: '#4CAF50' }],
        innerRing: [{ category: 'Accuracy', value: 90, fill: '#4CAF50' }]
      },
      progress: (numberComplete / numberTotal) * 100,
      accuracy: 90,
      elapsedTime: '1h 30m',
      numberComplete,
      numberTotal,
      eta: '30m remaining',
      processedItems: numberComplete,
      totalItems: numberTotal,
      estimatedTimeRemaining: '30m remaining',
      elapsedSeconds: 5400,
      estimatedRemainingSeconds: 1800
    }
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
      <OptimizationTask {...createTask(1, 25, 100)} />
      <OptimizationTask {...createTask(2, 50, 100)} />
      <OptimizationTask {...createTask(3, 75, 100)} />
      <OptimizationTask {...createTask(4, 100, 100)} />
    </div>
  ),
};

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import OptimizationTask from '@/components/OptimizationTask';
import { BaseTaskProps } from '@/components/Task';

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
    data?: {
      before: { innerRing: Array<{ value: number }> }
      after: { innerRing: Array<{ value: number }> }
      progress: number
      elapsedTime: string
      numberComplete: number
      numberTotal: number
      eta: string
    }
  }
}

const createTask = (
  id: number, 
  numberComplete: number, 
  numberTotal: number
): OptimizationTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Data Optimization',
    scorecard: 'Analysis',
    score: 'In Progress',
    time: '2 hours ago',
    summary: 'Optimization Summary',
    description: 'Optimization Description',
    data: {
      before: { innerRing: [{ value: 70 }] },
      after: { innerRing: [{ value: 90 }] },
      progress: (numberComplete / numberTotal) * 100,
      elapsedTime: '1h 30m',
      numberComplete,
      numberTotal,
      eta: '30m remaining'
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

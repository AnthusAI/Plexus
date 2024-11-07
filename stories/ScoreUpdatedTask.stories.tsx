import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof ScoreUpdatedTask> = {
  title: 'Tasks/Types/ScoreUpdatedTask',
  component: ScoreUpdatedTask,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ScoreUpdatedTask>;

interface ScoreUpdatedTaskStoryProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task'] & {
    data?: {
      before: { innerRing: Array<{ value: number }> }
      after: { innerRing: Array<{ value: number }> }
    }
  }
}

const createTask = (id: number, beforeScore: number, afterScore: number): ScoreUpdatedTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Score Update',
    scorecard: 'Performance Review',
    score: 'Improved',
    time: '30 minutes ago',
    summary: 'Score improved significantly',
    description: 'Score update details',
    data: {
      before: {
        innerRing: [{ value: beforeScore }],
      },
      after: {
        innerRing: [{ value: afterScore }],
      },
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid: Story = {
  args: createTask(1, 75, 85),
};

export const Detail: Story = {
  args: {
    ...createTask(2, 60, 90),
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
      <ScoreUpdatedTask {...createTask(1, 50, 75)} />
      <ScoreUpdatedTask {...createTask(2, 60, 80)} />
      <ScoreUpdatedTask {...createTask(3, 70, 85)} />
      <ScoreUpdatedTask {...createTask(4, 80, 95)} />
    </div>
  ),
};

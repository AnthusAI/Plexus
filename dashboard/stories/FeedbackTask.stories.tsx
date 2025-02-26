import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import FeedbackTask from '@/components/FeedbackTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof FeedbackTask> = {
  title: 'Tasks/Types/FeedbackTask',
  component: FeedbackTask,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof FeedbackTask>;

interface FeedbackTaskStoryProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task'] & {
    data?: {
      progress: number
      elapsedTime: string
      processedItems: number
      totalItems: number
      estimatedTimeRemaining: string
    }
  }
}

const createTask = (id: string, processedItems: number, totalItems: number): FeedbackTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Feedback',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    description: 'Feedback Description',
    data: {
      id,
      title: 'Feedback Task',
      progress: (processedItems / totalItems) * 100,
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid: Story = {
  args: createTask('1', 75, 100),
};

export const Detail: Story = {
  args: {
    ...createTask('2', 90, 100),
    variant: 'detail',
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
  },
};

export const DetailFullWidth: Story = {
  args: {
    ...Detail.args,
    isFullWidth: true,
  },
  parameters: {
    layout: 'fullscreen',
  },
};

export const GridWithMany = {
  render: () => (
    <div className="grid grid-cols-2 gap-4">
      <FeedbackTask {...createTask('1', 25, 100)} />
      <FeedbackTask {...createTask('2', 50, 100)} />
      <FeedbackTask {...createTask('3', 75, 100)} />
      <FeedbackTask {...createTask('4', 100, 100)} />
    </div>
  ),
};

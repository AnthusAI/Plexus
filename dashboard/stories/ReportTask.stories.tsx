import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof ReportTask> = {
  title: 'Tasks/Types/ReportTask',
  component: ReportTask,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ReportTask>;

interface ReportTaskStoryProps extends Omit<BaseTaskProps, 'task'> {
  task: BaseTaskProps['task']
}

const createTask = (id: number): ReportTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Report',
    scorecard: 'Monthly Report',
    score: 'Completed',
    time: '1 day ago',
    summary: 'Generated successfully',
    description: 'Report details'
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid: Story = {
  args: createTask(1),
};

export const Detail: Story = {
  args: {
    ...createTask(2),
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
      <ReportTask {...createTask(1)} />
      <ReportTask {...createTask(2)} />
      <ReportTask {...createTask(3)} />
      <ReportTask {...createTask(4)} />
    </div>
  ),
};

import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import AlertTask, { AlertTaskProps } from '@/components/AlertTask';

const meta = {
  title: 'Tasks/Types/AlertTask',
  component: AlertTask,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof AlertTask>;

export default meta;
type Story = StoryObj<typeof AlertTask>;

const createTask = (
  id: string,
  description: string, 
  iconType: 'info' | 'warning' | 'siren'
): AlertTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Alert',
    scorecard: 'System Health',
    score: 'Critical',
    time: '10 minutes ago',
    description,
    data: {
      id,
      title: description,
      iconType,
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid: Story = {
  args: createTask('1', 'Critical System Alert', 'warning'),
};

export const Detail: Story = {
  args: {
    ...createTask('2', 'Detailed System Alert', 'siren'),
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
      <AlertTask {...createTask('1', 'Info Alert', 'info')} />
      <AlertTask {...createTask('2', 'Warning Alert', 'warning')} />
      <AlertTask {...createTask('3', 'Critical Alert', 'siren')} />
      <AlertTask {...createTask('4', 'System Alert', 'warning')} />
    </div>
  ),
};

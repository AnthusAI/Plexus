import React from 'react';
import type { Meta, StoryObj, StoryFn } from '@storybook/react';
import { expect, within } from '@storybook/test';
import AlertTask from '@/components/AlertTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof AlertTask> = {
  title: 'Tasks/Types/AlertTask',
  component: AlertTask,
  args: {
    variant: 'grid',
    task: {
      id: 1,
      type: 'Alert',
      scorecard: 'System Health',
      score: 'Critical',
      time: '10 minutes ago',
      summary: 'System Alert',
    },
    iconType: 'warning'
  }
};

export default meta;
type Story = StoryObj<typeof AlertTask>;

interface AlertTaskStoryProps extends BaseTaskProps {
  iconType: 'info' | 'warning' | 'siren';
}

const Template: StoryFn<AlertTaskStoryProps> = (args: AlertTaskStoryProps) => (
  <AlertTask {...args} />
);

const createTask = (
  id: number, 
  summary: string, 
  iconType: 'info' | 'warning' | 'siren'
): AlertTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Alert',
    scorecard: 'System Health',
    score: 'Critical',
    time: '10 minutes ago',
    summary,
  },
  iconType,
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 'Critical System Alert', 'warning'),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Critical System Alert')).toBeInTheDocument();
    await expect(canvas.getByText('System Health')).toBeInTheDocument();
    await expect(canvas.getByText('Critical')).toBeInTheDocument();
    await expect(canvas.getByText('10 minutes ago')).toBeInTheDocument();
    await expect(canvas.getByText('Alert')).toBeInTheDocument();
    
    const warningIcon = canvasElement.querySelector('.lucide.lucide-message-circle-warning');
    expect(warningIcon).toBeInTheDocument();
    expect(warningIcon).toHaveClass('h-[120px]', 'w-[120px]');
  }
};

export const Detail: Story = {
  args: {
    ...createTask(2, 'Detailed System Alert', 'siren'),
    variant: 'detail',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Detailed System Alert')).toBeInTheDocument();
    await expect(canvas.getByText('System Health')).toBeInTheDocument();
    
    const sirenIcon = canvasElement.querySelector('.lucide.lucide-siren');
    expect(sirenIcon).toBeInTheDocument();
    expect(sirenIcon).toHaveClass('h-[120px]', 'w-[120px]');
  }
};

export const Grid: Story = {
  render: () => (
    <>
      <AlertTask {...createTask(1, 'Info Alert', 'info')} />
      <AlertTask {...createTask(2, 'Warning Alert', 'warning')} />
      <AlertTask {...createTask(3, 'Critical Alert', 'siren')} />
      <AlertTask {...createTask(4, 'System Alert', 'warning')} />
    </>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check for specific alert summaries
    await expect(canvas.getByText('Info Alert')).toBeInTheDocument();
    await expect(canvas.getByText('Warning Alert')).toBeInTheDocument();
    await expect(canvas.getByText('Critical Alert')).toBeInTheDocument();
    await expect(canvas.getByText('System Alert')).toBeInTheDocument();
    
    // Check for exactly 4 instances of type "Alert"
    const alertTypes = canvas.getAllByText('Alert');
    expect(alertTypes).toHaveLength(4);
    
    const systemHealthLabels = canvas.getAllByText('System Health');
    expect(systemHealthLabels).toHaveLength(4);
    
    const criticalLabels = canvas.getAllByText('Critical');
    expect(criticalLabels).toHaveLength(4);
    
    const icons = canvasElement.querySelectorAll('.lucide');
    expect(icons).toHaveLength(8); // 4 header icons + 4 large icons
  }
};

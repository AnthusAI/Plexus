import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import TaskProgress, { TaskProgressProps } from '@/components/TaskProgress';

export default {
  title: 'Tasks/TaskProgress',
  component: TaskProgress,
} as Meta<TaskProgressProps>;

const Template: StoryFn<TaskProgressProps> = (args) => <TaskProgress {...args} />;

export const Default = Template.bind({});
Default.args = {
  progress: 75,
  elapsedTime: '5 minutes',
  processedItems: 30,
  totalItems: 40,
  estimatedTimeRemaining: '10 minutes',
  processingRate: 6,
};

export const InProgress = Template.bind({});
InProgress.args = {
  progress: 50,
  elapsedTime: '3 minutes',
  processedItems: 20,
  totalItems: 40,
  estimatedTimeRemaining: '3 minutes',
  processingRate: 6.67,
};

export const Completed = Template.bind({});
Completed.args = {
  progress: 100,
  elapsedTime: '10 minutes',
  processedItems: 40,
  totalItems: 40,
  estimatedTimeRemaining: '0 minutes',
  processingRate: 4,
};

import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import TaskProgress from '@/components/TaskProgress';

export default {
  title: 'Tasks/TaskProgress',
  component: TaskProgress,
} as Meta;

const Template: StoryFn = (args) => <TaskProgress {...args} />;

export const Default = Template.bind({});
Default.args = {
  progress: 75,
  elapsedTime: '5 minutes',
  processedItems: 30,
  totalItems: 40,
  estimatedTimeRemaining: '10 minutes',
};

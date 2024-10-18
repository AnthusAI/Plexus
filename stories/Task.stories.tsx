import React from 'react';
import { Story, Meta } from '@storybook/react';
import { Task, TaskHeader, TaskContent, TaskActions, BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/Task',
  component: Task,
} as Meta;

const Template: Story<BaseTaskProps & { children?: React.ReactNode }> = (args) => <Task {...args}>{args.children}</Task>;

export const Grid = Template.bind({});
Grid.args = {
  variant: 'grid',
  task: {
    id: 8,
    type: 'Generic Task',
    scorecard: 'Generic Scorecard',
    score: 'N/A',
    time: 'Just now',
    summary: 'This is a generic task summary.',
    description: 'This is a detailed description of the generic task.',
    data: {},
  },
  children: (
    <>
      <TaskHeader />
      <TaskContent />
    </>
  ),
};

export const Detail = Template.bind({});
Detail.args = {
  variant: 'detail',
  task: {
    id: 8,
    type: 'Generic Task',
    scorecard: 'Generic Scorecard',
    score: 'N/A',
    time: 'Just now',
    summary: 'This is a generic task summary.',
    description: 'This is a detailed description of the generic task.',
    data: {},
  },
  children: (
    <>
      <TaskHeader />
      <TaskContent />
    </>
  ),
};

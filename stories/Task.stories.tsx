import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import { Task, TaskHeader, TaskContent, BaseTaskProps, TaskComponentProps } from '@/components/Task';

export default {
  title: 'Components/Task',
  component: Task,
} as Meta;

const Template: StoryFn<TaskComponentProps> = (args) => (
  <Task 
    {...args}
    renderHeader={(props) => <TaskHeader {...props} />}
    renderContent={(props) => <TaskContent {...props} />}
  />
);

const createTask = (id: number, type: string, summary: string): TaskComponentProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'General',
    score: 'In Progress',
    time: '1 hour ago',
    summary,
  },
  onClick: () => console.log(`Clicked on task ${id}`),
  renderHeader: (props) => <TaskHeader {...props} />,
  renderContent: (props) => <TaskContent {...props} />,
});

export const Default = Template.bind({});
Default.args = createTask(1, 'Default Task', 'This is a default task');

export const GridVariant = Template.bind({});
GridVariant.args = createTask(2, 'Grid Task', 'This is a grid task');

export const DetailVariant = Template.bind({});
DetailVariant.args = {
  ...createTask(3, 'Detail Task', 'This is a detail task'),
  variant: 'detail',
};

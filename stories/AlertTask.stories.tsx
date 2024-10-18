import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import AlertTask from '@/components/AlertTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Tasks/Types/AlertTask',
  component: AlertTask,
  argTypes: {
    variant: {
      control: { type: 'radio' },
      options: ['grid', 'detail'],
    },
    iconType: {
      control: { type: 'radio' },
      options: ['info', 'warning'],
    },
  },
} as Meta;

interface AlertTaskStoryProps extends BaseTaskProps {
  iconType: 'info' | 'warning';
}

const Template: StoryFn<AlertTaskStoryProps> = (args) => <AlertTask {...args} />;

const createTask = (
  id: number, 
  type: string, 
  summary: string, 
  iconType: 'info' | 'warning'
): AlertTaskStoryProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'System Health',
    score: 'Critical',
    time: '10 minutes ago',
    summary,
  },
  onClick: () => console.log(`Clicked on task ${id}`),
  iconType,
});

export const Grid = () => (
  <>
    <Template {...createTask(1, 'System Outage', 'Urgent attention required', 'info')} />
    <Template {...createTask(2, 'Security Breach', 'Investigating', 'info')} />
    <Template {...createTask(3, 'Performance Degradation', 'Monitoring', 'warning')} />
    <Template {...createTask(4, 'Data Inconsistency', 'Verification needed', 'warning')} />
  </>
);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Network Anomaly', 'Investigating', 'info'),
  variant: 'detail',
};

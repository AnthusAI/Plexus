import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import AlertTask from '@/components/AlertTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/AlertTask',
  component: AlertTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <AlertTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
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
});

export const Default = () => (
  <>
    <style>
      {`
        :root {
          --true: #22c55e;
          --false: #ef4444;
        }
      `}
    </style>
    <Template {...createTask(1, 'System Outage', 'Urgent attention required')} />
    <Template {...createTask(2, 'Security Breach', 'Investigating')} />
    <Template {...createTask(3, 'Performance Degradation', 'Monitoring')} />
    <Template {...createTask(4, 'Data Inconsistency', 'Verification needed')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Critical Error', 'Urgent attention required');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Network Anomaly', 'Investigating'),
  variant: 'detail',
};

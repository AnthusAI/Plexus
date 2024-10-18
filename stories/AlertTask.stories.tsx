import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import AlertTask from '@/components/AlertTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/AlertTask',
  component: AlertTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <AlertTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Alert',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Alert details',
    data: {
      // Add any specific data for AlertTask here
    },
  },
});

export const MultipleGridItems: StoryFn = () => (
  <div style={{
    display: 'grid',
    gap: '1rem',
    gridTemplateColumns: '1fr',
    width: '100vw',
    maxWidth: '100vw',
    margin: '0 -1rem',
    padding: '1rem',
    boxSizing: 'border-box',
  }}>
    <style>
      {`
        @media (min-width: 768px) {
          div {
            grid-template-columns: repeat(2, 1fr) !important;
          }
        }
        @media (min-width: 1024px) {
          div {
            grid-template-columns: repeat(3, 1fr) !important;
          }
        }
      `}
    </style>
    {Template(createTask(1, 'System Outage', 'Urgent attention required'))}
    {Template(createTask(2, 'Security Breach', 'Investigating'))}
    {Template(createTask(3, 'Performance Degradation', 'Monitoring'))}
    {Template(createTask(4, 'Data Inconsistency', 'Verification needed'))}
    {Template(createTask(5, 'API Error', 'Troubleshooting'))}
    {Template(createTask(6, 'Compliance Issue', 'Review immediately'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Critical Error', 'Urgent attention required');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Network Anomaly', 'Investigating'),
  variant: 'detail',
};

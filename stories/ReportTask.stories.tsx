import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/ReportTask',
  component: ReportTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ReportTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Report generated',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Report details',
    data: {
      // Add any specific data for ReportTask here
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
    {Template(createTask(1, 'Monthly Report', 'Generated successfully'))}
    {Template(createTask(2, 'Weekly Summary', 'Ready for review'))}
    {Template(createTask(3, 'Performance Analysis', 'Awaiting approval'))}
    {Template(createTask(4, 'Quarterly Review', 'In progress'))}
    {Template(createTask(5, 'Annual Report', 'Scheduled'))}
    {Template(createTask(6, 'Custom Report', 'Completed'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Daily Report', 'Generated successfully');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Weekly Report', 'Ready for review'),
  variant: 'detail',
};

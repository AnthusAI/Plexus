import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/ReportTask',
  component: ReportTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ReportTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'Report',
    score: 'Completed',
    time: '1 day ago',
    summary,
    description: 'Report details',
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
    <Template {...createTask(1, 'Monthly Report', 'Generated successfully')} />
    <Template {...createTask(2, 'Weekly Summary', 'Ready for review')} />
    <Template {...createTask(3, 'Performance Analysis', 'Awaiting approval')} />
    <Template {...createTask(4, 'Quarterly Review', 'In progress')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(5, 'Annual Report', 'Finalizing content');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(6, 'Financial Statement', 'Pending audit'),
  variant: 'detail',
};

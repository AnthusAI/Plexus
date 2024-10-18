import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import FeedbackTask from '@/components/FeedbackTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/FeedbackTask',
  component: FeedbackTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <FeedbackTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'Feedback',
    score: 'In Progress',
    time: '3 hours ago',
    summary,
    description: 'Feedback processing',
    data: {
      progress: 75,
      elapsedTime: '2h 30m',
      numberComplete: 150,
      numberTotal: 200,
      eta: '45m',
    },
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
    <Template {...createTask(1, 'Customer Feedback', 'Processing customer survey responses')} />
    <Template {...createTask(2, 'User Reviews', 'Analyzing app store reviews')} />
    <Template {...createTask(3, 'Support Tickets', 'Categorizing support requests')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(4, 'Product Feedback', 'Evaluating feature requests');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 'Employee Feedback', 'Processing annual survey'),
  variant: 'detail',
};

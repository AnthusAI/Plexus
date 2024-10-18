import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import FeedbackTask from '@/components/FeedbackTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Tasks/Types/FeedbackTask',
  component: FeedbackTask,
  argTypes: {
    variant: {
      control: { type: 'radio' },
      options: ['grid', 'detail'],
    },
  },
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
      processedItems: 150,
      totalItems: 200,
      estimatedTimeRemaining: '45m',
    },
  },
  onClick: () => console.log(`Clicked on task ${id}`),
});

export const Grid = () => (
  <>
    <Template {...createTask(1, 'Customer Feedback', 'Processing customer survey responses')} />
    <Template {...createTask(2, 'User Reviews', 'Analyzing app store reviews')} />
    <Template {...createTask(3, 'Support Tickets', 'Categorizing support requests')} />
  </>
);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(4, 'Product Feedback', 'Evaluating feature requests'),
  variant: 'detail',
};

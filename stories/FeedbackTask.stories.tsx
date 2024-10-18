import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import FeedbackTask from '@/components/FeedbackTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/FeedbackTask',
  component: FeedbackTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <FeedbackTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Feedback',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Feedback progress',
    data: {
      progress: 75,
      elapsedTime: '2h 30m',
      processedItems: 150,
      totalItems: 200,
      estimatedTimeRemaining: '45m',
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
    {Template(createTask(1, 'Customer Feedback', 'In progress'))}
    {Template(createTask(2, 'Agent Performance', 'Review pending'))}
    {Template(createTask(3, 'Call Quality', 'Feedback collected'))}
    {Template(createTask(4, 'Training Effectiveness', 'Analysis ongoing'))}
    {Template(createTask(5, 'Product Knowledge', 'Feedback requested'))}
    {Template(createTask(6, 'Customer Satisfaction', 'Results available'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Sales Pitch Feedback', 'In progress');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Customer Service Feedback', 'Review pending'),
  variant: 'detail',
};

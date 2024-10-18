import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/ScoreUpdatedTask',
  component: ScoreUpdatedTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ScoreUpdatedTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'Score Update',
    score: 'Improved',
    time: '30 minutes ago',
    summary,
    description: 'Score update details',
    data: {
      before: {
        innerRing: [{ value: 75 }],
      },
      after: {
        innerRing: [{ value: 85 }],
      },
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
    <Template {...createTask(1, 'Customer Satisfaction', 'Score improved')} />
    <Template {...createTask(2, 'Product Quality', 'Score maintained')} />
    <Template {...createTask(3, 'Employee Performance', 'Score slightly decreased')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(4, 'Team Productivity', 'Score significantly improved');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 'Project Success Rate', 'Score update analysis'),
  variant: 'detail',
};

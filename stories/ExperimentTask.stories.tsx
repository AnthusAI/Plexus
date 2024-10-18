import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/ExperimentTask',
  component: ExperimentTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ExperimentTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'Experiment',
    score: 'In Progress',
    time: '4 hours ago',
    summary,
    description: 'Experiment progress',
    data: {
      accuracy: 75,
      progress: 65,
      elapsedTime: '3h 15m',
      numberComplete: 130,
      numberTotal: 200,
      eta: '1h 45m',
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
    <Template {...createTask(1, 'A/B Test', 'Testing new feature')} />
    <Template {...createTask(2, 'Multivariate Test', 'Optimizing landing page')} />
    <Template {...createTask(3, 'Split Test', 'Comparing email campaigns')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(4, 'Usability Test', 'Evaluating new UI design');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 'Performance Test', 'Measuring load times'),
  variant: 'detail',
};

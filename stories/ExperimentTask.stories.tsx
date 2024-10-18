import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
  argTypes: {
    variant: {
      control: { type: 'radio' },
      options: ['grid', 'detail'],
    },
  },
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ExperimentTask {...args} />;

const createTask = (id: number, processedItems: number, totalItems: number): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Experiment',
    scorecard: 'Experiment Analysis',
    score: 'In Progress',
    time: '1 hour ago',
    data: {
      accuracy: 85,
      progress: 70,
      elapsedTime: '30m',
      numberComplete: processedItems,
      numberTotal: totalItems,
      eta: '15m remaining',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '15m',
    },
  },
  onClick: () => console.log(`Clicked on task ${id}`),
});

export const Grid = () => (
  <>
    <Template {...createTask(1, 50, 100)} />
    <Template {...createTask(2, 30, 60)} />
    <Template {...createTask(3, 70, 100)} />
    <Template {...createTask(4, 20, 40)} />
  </>
);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 80, 100),
  variant: 'detail',
};

import React from 'react';
import { Meta, StoryFn } from '@storybook/react';
import ExperimentTask from '../components/ExperimentTask';
import { ExperimentTaskProps } from '../components/ExperimentTask';

export default {
  title: 'Components/ExperimentTask',
  component: ExperimentTask,
} as Meta;

const Template: StoryFn<ExperimentTaskProps> = (args) => <ExperimentTask {...args} />;

const createTask = (id: number, processedItems: number, totalItems: number): ExperimentTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Experiment',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Experiment Summary',
    description: 'Experiment Description',
    data: {
      accuracy: 75,
      progress: (processedItems / totalItems) * 100,
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
      processingRate: 2.5
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid = Template.bind({});
Grid.args = createTask(1, 75, 100);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(2, 90, 100),
  variant: 'detail',
};

export const InProgress = Template.bind({});
InProgress.args = createTask(3, 50, 100);

export const Completed = Template.bind({});
Completed.args = createTask(4, 100, 100);

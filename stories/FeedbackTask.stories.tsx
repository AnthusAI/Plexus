import React from 'react';
import { Meta, StoryFn } from '@storybook/react';
import FeedbackTask from '../components/FeedbackTask';
import { TaskComponentProps } from '../components/Task';

export default {
  title: 'Components/FeedbackTask',
  component: FeedbackTask,
} as Meta;

const Template: StoryFn<Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>> = (args) => <FeedbackTask {...args} />;

const createTask = (id: number): Omit<TaskComponentProps, 'renderHeader' | 'renderContent'> => ({
  variant: 'grid',
  task: {
    id,
    type: 'Feedback',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Feedback Summary',
    description: 'Feedback Description',
    data: {
      accuracy: 75,
      progress: 75,
      elapsedTime: '2h 30m',
      numberComplete: 150,
      numberTotal: 200,
      eta: '45m',
    },
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Grid = Template.bind({});
Grid.args = createTask(1);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(2),
  variant: 'detail',
};

export const InProgress = Template.bind({});
InProgress.args = createTask(3);

export const Completed = Template.bind({});
Completed.args = createTask(4);

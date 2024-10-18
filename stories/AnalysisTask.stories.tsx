import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import AnalysisTask from '@/components/AnalysisTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Components/AnalysisTask',
  component: AnalysisTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <AnalysisTask {...args} />;

const createTask = (id: number, type: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard: 'Analysis',
    score: 'In Progress',
    time: '2 hours ago',
    summary,
    description: 'Analysis progress',
    data: {
      before: {
        innerRing: [{ value: 75 }],
      },
      after: {
        innerRing: [{ value: 85 }],
      },
      progress: 60,
      elapsedTime: '1h 30m',
      numberComplete: 600,
      numberTotal: 1000,
      eta: '1h remaining',
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
    <Template {...createTask(1, 'Data Analysis', 'Analyzing customer feedback')} />
    <Template {...createTask(2, 'Trend Analysis', 'Identifying market trends')} />
    <Template {...createTask(3, 'Performance Analysis', 'Evaluating system performance')} />
  </>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(4, 'Sentiment Analysis', 'Analyzing social media sentiment');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 'Predictive Analysis', 'Forecasting future trends'),
  variant: 'detail',
};

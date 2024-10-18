import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import OptimizationTask from '@/components/OptimizationTask';
import { BaseTaskProps } from '@/components/Task';

export default {
  title: 'Tasks/Types/OptimizationTask',
  component: OptimizationTask,
  argTypes: {
    variant: {
      control: { type: 'radio' },
      options: ['grid', 'detail'],
    },
  },
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => (
  <OptimizationTask {...args} />
);

interface CreateTaskParams {
  id: number;
  type: string;
  summary: string;
  scorecard?: string;
  score?: string;
  time?: string;
  description?: string;
  beforeValue?: number;
  afterValue?: number;
  progress?: number;
  elapsedTime?: string;
  numberComplete?: number;
  numberTotal?: number;
  eta?: string;
}

const createTask = ({
  id,
  type,
  summary,
  scorecard = 'Analysis',
  score = 'In Progress',
  time = '2 hours ago',
  description = 'Analysis progress',
  beforeValue = 75,
  afterValue = 85,
  progress = 60,
  elapsedTime = '1h 30m',
  numberComplete = 600,
  numberTotal = 1000,
  eta = '1h remaining',
}: CreateTaskParams): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type,
    scorecard,
    score,
    time,
    summary,
    description,
    data: {
      before: { innerRing: [{ value: beforeValue }] },
      after: { innerRing: [{ value: afterValue }] },
      progress,
      elapsedTime,
      numberComplete,
      numberTotal,
      eta,
    },
  },
  onClick: () => console.log(`Clicked on task ${id}`),
});

export const Grid = () => (
  <>
    <Template {...createTask({
      id: 1,
      type: 'Data Optimization',
      summary: 'Optimizing customer feedback',
      time: '1 day ago',
      beforeValue: 70,
      afterValue: 90,
      progress: 85,
      numberComplete: 849,
      numberTotal: 1000
    })} />
    <Template {...createTask({
      id: 2,
      type: 'Trend Optimization',
      summary: 'Identifying market trends',
      time: '3 hours ago',
      beforeValue: 60,
      afterValue: 80,
      progress: 50,
      elapsedTime: '2h 15m',
      eta: '2h 15m remaining'
    })} />
    <Template {...createTask({
      id: 3,
      type: 'Performance Optimization',
      summary: 'Evaluating system performance',
      time: '30 minutes ago'
    })} />
  </>
);

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(5, 'Predictive Analysis', 'Forecasting future trends'),
  variant: 'detail',
};

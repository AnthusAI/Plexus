import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ExperimentTask from '@/components/ExperimentTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/ExperimentTask',
  component: ExperimentTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ExperimentTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Experiment',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Experiment progress',
    data: {
      accuracy: 82,
      progress: 65,
      elapsedTime: '3h 15m',
      processedItems: 130,
      totalItems: 200,
      estimatedTimeRemaining: '1h 45m',
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
    {Template(createTask(1, 'A/B Test', 'In progress'))}
    {Template(createTask(2, 'Feature Trial', 'Results pending'))}
    {Template(createTask(3, 'Pricing Strategy', 'Experiment running'))}
    {Template(createTask(4, 'UI Optimization', 'Data collection'))}
    {Template(createTask(5, 'Customer Segmentation', 'Analysis phase'))}
    {Template(createTask(6, 'Conversion Funnel', 'Final stage'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'New Product Test', 'In progress');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Marketing Campaign Test', 'Results pending'),
  variant: 'detail',
};

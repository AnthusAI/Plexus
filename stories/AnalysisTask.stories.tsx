import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import AnalysisTask from '@/components/AnalysisTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/AnalysisTask',
  component: AnalysisTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <AnalysisTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Analysis',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Analysis progress',
    data: {
      before: {
        innerRing: [{ value: 75 }],
        outerRing: [{ value: 50 }, { value: 50 }],
      },
      after: {
        innerRing: [{ value: 85 }],
        outerRing: [{ value: 50 }, { value: 50 }],
      },
      progress: 80,
      elapsedTime: '4h 30m',
      numberComplete: 160,
      numberTotal: 200,
      estimatedTimeRemaining: '1h 15m',
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
    {Template(createTask(1, 'Sales Performance', 'Analyzing trends'))}
    {Template(createTask(2, 'Customer Behavior', 'Pattern recognition'))}
    {Template(createTask(3, 'Market Segmentation', 'Cluster analysis'))}
    {Template(createTask(4, 'Competitor Analysis', 'Data compilation'))}
    {Template(createTask(5, 'Product Performance', 'Metrics evaluation'))}
    {Template(createTask(6, 'Risk Assessment', 'Predictive modeling'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Financial Forecast', 'Analyzing trends');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Customer Churn Analysis', 'Pattern recognition'),
  variant: 'detail',
};

import React from 'react';
import { StoryFn, Meta } from '@storybook/react';
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask';
import { BaseTaskProps } from '@/components/task';

export default {
  title: 'Components/ScoreUpdatedTask',
  component: ScoreUpdatedTask,
} as Meta;

const Template: StoryFn<BaseTaskProps> = (args) => <ScoreUpdatedTask {...args} />;

const createTask = (id: number, score: string, summary: string): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Score updated',
    scorecard: 'SelectQuote TermLife v1',
    score,
    time: '1d ago',
    summary,
    description: 'Accuracy',
    data: {
      before: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 75, fill: "var(--true)" },
          { category: "Negative", value: 25, fill: "var(--false)" },
        ],
      },
      after: {
        outerRing: [
          { category: "Positive", value: 50, fill: "var(--true)" },
          { category: "Negative", value: 50, fill: "var(--false)" },
        ],
        innerRing: [
          { category: "Positive", value: 82, fill: "var(--true)" },
          { category: "Negative", value: 18, fill: "var(--false)" },
        ],
      },
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
    {Template(createTask(1, 'Assumptive Close', 'Improved from 75% to 82%'))}
    {Template(createTask(2, 'Objection Handling', 'Decreased from 90% to 85%'))}
    {Template(createTask(3, 'Needs Assessment', 'Improved from 60% to 72%'))}
    {Template(createTask(4, 'Product Knowledge', 'Maintained at 95%'))}
    {Template(createTask(5, 'Closing Techniques', 'Improved from 70% to 78%'))}
    {Template(createTask(6, 'Customer Rapport', 'Decreased from 88% to 82%'))}
  </div>
);

export const SingleGridItem = Template.bind({});
SingleGridItem.args = createTask(7, 'Assumptive Close', 'Improved from 75% to 82%');

export const Detail = Template.bind({});
Detail.args = {
  ...createTask(8, 'Assumptive Close', 'Improved from 75% to 82%'),
  variant: 'detail',
};

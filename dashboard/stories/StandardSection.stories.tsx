import React from 'react'
import { StandardSection } from '../components/landing/StandardSection'

export default {
  title: 'Landing/StandardSection',
  component: StandardSection,
  argTypes: {
    headlinePosition: { control: { type: 'radio', options: ['top', 'inline'] } },
  },
};

const Template = (args) => <StandardSection {...args} />;

export const TopHeadline = Template.bind({});
TopHeadline.args = {
  headline: "Don't Just Guess — Guess and Test",
  headlinePosition: 'top',
  leftContent: (
    <div style={{ padding: '1rem', background: '#f0f0f0' }}>
      {/* Placeholder for gauges or left content */}
      <p>Left Content: Gauges Component Placeholder</p>
    </div>
  ),
  rightContent: (
    <div style={{ padding: '1rem' }}>
      <p>You can't just write prompts and put them into production and hope they work. Evaluate quantitatively to meet your needs.</p>
      <p>Each use case demands its own success metrics.</p>
    </div>
  ),
  containerClassName: 'bg-background',
};

export const InlineHeadline = Template.bind({});
InlineHeadline.args = {
  headline: 'Intelligence at Scale',
  headlinePosition: 'inline',
  leftContent: (
    <div style={{ padding: '1rem', background: '#f0f0f0' }}>
      {/* Placeholder for a workflow component, e.g., ItemListWorkflow */}
      <p>Left Content: Workflow Component Placeholder</p>
    </div>
  ),
  rightContent: (
    <div style={{ padding: '1rem' }}>
      <p>Run a scorecard on your data, with multiple scores per scorecard. Classify, predict, and extract insights.</p>
    </div>
  ),
  containerClassName: 'bg-background',
}; 
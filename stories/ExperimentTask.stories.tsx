import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import ExperimentTask from '../components/ExperimentTask';
import { ExperimentTaskProps } from '../components/ExperimentTask';

const meta: Meta<typeof ExperimentTask> = {
  title: 'Tasks/Types/ExperimentTask',
  component: ExperimentTask,
};

export default meta;
type Story = StoryObj<typeof ExperimentTask>;

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
      f1Score: 82,
      elapsedTime: '01:30:00',
      processedItems,
      totalItems,
      estimatedTimeRemaining: '00:30:00',
      outerRing: [
        { category: 'Positive', value: 50, fill: 'var(--true)' },
        { category: 'Negative', value: 50, fill: 'var(--false)' },
      ],
      innerRing: [
        { category: 'Positive', value: 75, fill: 'var(--true)' },
        { category: 'Negative', value: 25, fill: 'var(--false)' },
      ],
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 75, 100),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check task metadata
    await expect(canvas.getByText('Experiment Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Experiment Description')).toBeInTheDocument();
    await expect(canvas.getByText('Test Scorecard')).toBeInTheDocument();
    await expect(canvas.getByText('Test Score')).toBeInTheDocument();
    await expect(canvas.getByText('2 hours ago')).toBeInTheDocument();
    await expect(canvas.getByText('Experiment')).toBeInTheDocument();
    
    // Check for Flask icon
    const flaskIcon = canvasElement.querySelector('.lucide.lucide-flask-conical');
    expect(flaskIcon).toBeInTheDocument();
    expect(flaskIcon).toHaveClass('h-6', 'w-6');
    
    // Check progress numbers and total items
    const seventyFiveElements = canvas.getAllByText(/75/);
    expect(seventyFiveElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
    // Check progress percentage and time information
    await expect(canvas.getByText('75%')).toBeInTheDocument();
    await expect(canvas.getByText('Elapsed: 01:30:00')).toBeInTheDocument();
    await expect(canvas.getByText('ETA: 00:30:00')).toBeInTheDocument();
  }
};

export const Detail: Story = {
  args: {
    ...createTask(2, 90, 100),
    variant: 'detail',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Experiment Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Experiment Description')).toBeInTheDocument();
    
    // Check that we have the right number of matches for 90 and total items
    const ninetyElements = canvas.getAllByText(/90/);
    expect(ninetyElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
    // Check for progress display
    const progressElement = canvas.getByText('90%');
    await expect(progressElement).toBeInTheDocument();
  }
};

export const Grid: Story = {
  args: createTask(1, 75, 100),
};

export const InProgress: Story = {
  args: createTask(4, 50, 100),
};

export const Completed: Story = {
  args: createTask(5, 100, 100),
};

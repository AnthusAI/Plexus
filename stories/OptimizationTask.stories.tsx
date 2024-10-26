import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import OptimizationTask from '@/components/OptimizationTask';
import { TaskComponentProps } from '@/components/Task';

const meta: Meta<typeof OptimizationTask> = {
  title: 'Tasks/Types/OptimizationTask',
  component: OptimizationTask,
  args: {
    variant: 'grid',
    task: {
      id: 1,
      type: 'optimization',
      scorecard: 'Analysis',
      score: 'In Progress',
      time: '2 hours ago',
      summary: 'Optimizing customer feedback',
      data: {
        before: { innerRing: [{ value: 75 }] },
        after: { innerRing: [{ value: 85 }] },
        progress: 60,
        elapsedTime: '1h 30m',
        numberComplete: 600,
        numberTotal: 1000,
        eta: '1h remaining'
      }
    }
  }
};

export default meta;
type Story = StoryObj<typeof OptimizationTask>;

const createTask = (
  id: number, 
  numberComplete: number, 
  numberTotal: number
): TaskComponentProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Data Optimization',
    scorecard: 'Analysis',
    score: 'In Progress',
    time: '2 hours ago',
    summary: 'Optimization Summary',
    description: 'Optimization Description',
    data: {
      before: { innerRing: [{ value: 70 }] },
      after: { innerRing: [{ value: 90 }] },
      progress: (numberComplete / numberTotal) * 100,
      elapsedTime: '1h 30m',
      numberComplete,
      numberTotal,
      eta: '30m remaining'
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 75, 100),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Optimization Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Optimization Description')).toBeInTheDocument();
    await expect(canvas.getByText('Analysis')).toBeInTheDocument();
    await expect(canvas.getByText('In Progress')).toBeInTheDocument();
    await expect(canvas.getByText('2 hours ago')).toBeInTheDocument();
    await expect(canvas.getByText('Data Optimization')).toBeInTheDocument();
    
    // Updated icon testing to match ExperimentTask approach
    const sparklesIcon = canvasElement.querySelector('.lucide.lucide-sparkles');
    expect(sparklesIcon).toBeInTheDocument();
    expect(sparklesIcon).toHaveClass('h-6', 'w-6');
    
    const seventyFiveElements = canvas.getAllByText(/75/);
    expect(seventyFiveElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
    await expect(canvas.getByText('75%')).toBeInTheDocument();
    await expect(canvas.getByText('Elapsed: 1h 30m')).toBeInTheDocument();
    await expect(canvas.getByText('ETA: 30m remaining')).toBeInTheDocument();
  }
};

export const Detail: Story = {
  args: {
    ...createTask(2, 90, 100),
    variant: 'detail',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Optimization Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Optimization Description')).toBeInTheDocument();
    
    const ninetyElements = canvas.getAllByText(/90/);
    expect(ninetyElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
    await expect(canvas.getByText('90%')).toBeInTheDocument();
    
    const sparklesIcon = canvasElement.querySelector('.lucide.lucide-sparkles');
    expect(sparklesIcon).not.toBeInTheDocument();
  }
};

export const Grid: Story = {
  render: () => (
    <>
      <OptimizationTask {...createTask(1, 25, 100)} />
      <OptimizationTask {...createTask(2, 50, 100)} />
      <OptimizationTask {...createTask(3, 75, 100)} />
      <OptimizationTask {...createTask(4, 100, 100)} />
    </>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    const summaries = canvas.getAllByText('Optimization Summary');
    expect(summaries).toHaveLength(4);
    
    await expect(canvas.getByText('25%')).toBeInTheDocument();
    await expect(canvas.getByText('50%')).toBeInTheDocument();
    await expect(canvas.getByText('75%')).toBeInTheDocument();
    await expect(canvas.getByText('100%')).toBeInTheDocument();
    
    const sparklesIcons = canvasElement.querySelectorAll('.lucide.lucide-sparkles');
    expect(sparklesIcons).toHaveLength(4);
    
    const descriptions = canvas.getAllByText('Optimization Description');
    expect(descriptions).toHaveLength(4);
  }
};

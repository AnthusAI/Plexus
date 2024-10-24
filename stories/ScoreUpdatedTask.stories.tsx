import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import ScoreUpdatedTask from '@/components/ScoreUpdatedTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof ScoreUpdatedTask> = {
  title: 'Tasks/Types/ScoreUpdatedTask',
  component: ScoreUpdatedTask,
  args: {
    variant: 'grid',
    task: {
      id: 1,
      type: 'Score Update',
      scorecard: 'Performance Review',
      score: 'Improved',
      time: '30 minutes ago',
      summary: 'Score improved significantly',
      description: 'Score update details',
      data: {
        before: {
          innerRing: [{ value: 75 }],
        },
        after: {
          innerRing: [{ value: 85 }],
        },
      }
    }
  }
};

export default meta;
type Story = StoryObj<typeof ScoreUpdatedTask>;

const createTask = (id: number, beforeScore: number, afterScore: number): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Score Update',
    scorecard: 'Performance Review',
    score: 'Improved',
    time: '30 minutes ago',
    summary: 'Score improved significantly',
    description: 'Score update details',
    data: {
      before: {
        innerRing: [{ value: beforeScore }],
      },
      after: {
        innerRing: [{ value: afterScore }],
      },
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 75, 85),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check task metadata
    await expect(canvas.getByText('Score update details')).toBeInTheDocument();
    await expect(canvas.getByText('Performance Review')).toBeInTheDocument();
    await expect(canvas.getByText('Improved')).toBeInTheDocument();
    await expect(canvas.getByText('30 minutes ago')).toBeInTheDocument();
    await expect(canvas.getByText('Score Update')).toBeInTheDocument();
    
    // Check for ListTodo icon
    const todoIcon = canvasElement.querySelector('.lucide.lucide-list-todo');
    expect(todoIcon).toBeInTheDocument();
    expect(todoIcon).toHaveClass('h-6', 'w-6');
    
    // Check before/after score values
    await expect(canvas.getByText(/75%/)).toBeInTheDocument();
    await expect(canvas.getByText(/85%/)).toBeInTheDocument();
    
    // Check for arrow icon
    const arrowIcon = canvasElement.querySelector('.lucide.lucide-move-up-right');
    expect(arrowIcon).toBeInTheDocument();
  }
};

export const Detail: Story = {
  args: {
    ...createTask(2, 60, 90),
    variant: 'detail',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check task metadata
    await expect(canvas.getByText('Score update details')).toBeInTheDocument();
    
    // Check score values in detail view
    await expect(canvas.getByText(/60%/)).toBeInTheDocument();
    await expect(canvas.getByText(/90%/)).toBeInTheDocument();
        
    // Check for arrow icon
    const arrowIcon = canvasElement.querySelector('.lucide.lucide-move-up-right');
    expect(arrowIcon).toBeInTheDocument();
    
    // Verify pie chart visualization
    const pieChartContainers = canvasElement.querySelectorAll(
      '.recharts-responsive-container'
    );
    expect(pieChartContainers.length).toBeGreaterThan(0);
    
    // Verify "Before" and "After" labels
    await expect(canvas.getByText('Before')).toBeInTheDocument();
    await expect(canvas.getByText('After')).toBeInTheDocument();
  }
};

export const Grid: Story = {
  render: () => (
    <>
      <ScoreUpdatedTask {...createTask(1, 50, 75)} />
      <ScoreUpdatedTask {...createTask(2, 60, 80)} />
      <ScoreUpdatedTask {...createTask(3, 70, 85)} />
      <ScoreUpdatedTask {...createTask(4, 80, 95)} />
    </>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check that we have all ListTodo icons
    const todoIcons = canvasElement.querySelectorAll('.lucide.lucide-list-todo');
    expect(todoIcons).toHaveLength(4);
    
    // Check that each task has its description
    const descriptions = canvas.getAllByText('Score update details');
    expect(descriptions).toHaveLength(4);
    
    // Verify score values are present
    await expect(canvas.getByText(/50%/)).toBeInTheDocument();
    await expect(canvas.getByText(/75%/)).toBeInTheDocument();
    await expect(canvas.getByText(/60%/)).toBeInTheDocument();
    await expect(canvas.getByText(/95%/)).toBeInTheDocument();
  }
};

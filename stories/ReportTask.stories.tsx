import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

const meta: Meta<typeof ReportTask> = {
  title: 'Tasks/Types/ReportTask',
  component: ReportTask,
  args: {
    variant: 'grid',
    task: {
      id: 1,
      type: 'Report',
      scorecard: 'Monthly Report',
      score: 'Completed',
      time: '1 day ago',
      summary: 'Generated successfully',
      description: 'Report details'
    }
  }
};

export default meta;
type Story = StoryObj<typeof ReportTask>;

const createTask = (id: number): BaseTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Report',
    scorecard: 'Monthly Report',
    score: 'Completed',
    time: '1 day ago',
    summary: 'Generated successfully',
    description: 'Report details'
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check task metadata
    await expect(canvas.getByText('Generated successfully')).toBeInTheDocument();
    await expect(canvas.getByText('Report details')).toBeInTheDocument();
    await expect(canvas.getByText('Monthly Report')).toBeInTheDocument();
    await expect(canvas.getByText('Completed')).toBeInTheDocument();
    await expect(canvas.getByText('1 day ago')).toBeInTheDocument();
    await expect(canvas.getByText('Report')).toBeInTheDocument();
    
    // Check for FileText icon
    const fileIcon = canvasElement.querySelector('.lucide.lucide-file-text');
    expect(fileIcon).toBeInTheDocument();
    expect(fileIcon).toHaveClass('h-6', 'w-6');
  }
};

export const Detail: Story = {
  args: {
    ...createTask(2),
    variant: 'detail',
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Check task metadata
    await expect(canvas.getByText('Generated successfully')).toBeInTheDocument();
    await expect(canvas.getByText('Report details')).toBeInTheDocument();
    await expect(canvas.getByText('Monthly Report')).toBeInTheDocument();
    await expect(canvas.getByText('Completed')).toBeInTheDocument();
    await expect(canvas.getByText('1 day ago')).toBeInTheDocument();
    await expect(canvas.getByText('Report')).toBeInTheDocument();
  }
};

export const Grid: Story = {
  render: () => (
    <>
      <ReportTask {...createTask(1)} />
      <ReportTask {...createTask(2)} />
      <ReportTask {...createTask(3)} />
      <ReportTask {...createTask(4)} />
    </>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    // Verify all four tasks are present
    const summaries = canvas.getAllByText('Generated successfully');
    expect(summaries).toHaveLength(4);
    
    // Verify all tasks have FileText icons
    const fileIcons = canvasElement.querySelectorAll('.lucide.lucide-file-text');
    expect(fileIcons).toHaveLength(4);
    
    // Check that each task has its description
    const descriptions = canvas.getAllByText('Report details');
    expect(descriptions).toHaveLength(4);
    
    // Verify all tasks have their metadata
    const scorecards = canvas.getAllByText('Monthly Report');
    expect(scorecards).toHaveLength(4);
    
    const statuses = canvas.getAllByText('Completed');
    expect(statuses).toHaveLength(4);
  }
};

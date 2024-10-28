import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { expect, within } from '@storybook/test';
import FeedbackTask from '../components/FeedbackTask';
import { TaskComponentProps } from '../components/Task';

type FeedbackTaskProps = Omit<TaskComponentProps, 'renderHeader' | 'renderContent'>;

const meta: Meta<typeof FeedbackTask> = {
  title: 'Tasks/Types/FeedbackTask',
  component: FeedbackTask,
  args: {
    variant: 'grid',
    task: {
      id: 1,
      type: 'feedback',
      scorecard: 'B+',
      score: '85%',
      time: '1h 30m',
      summary: 'Feedback Summary',
      data: {
        progress: 75,
        elapsedTime: '1h 15m',
        numberComplete: 150,
        numberTotal: 200,
        eta: '30m'
      }
    }
  }
};

export default meta;
type Story = StoryObj<typeof FeedbackTask>;

const createTask = (id: number, processedItems: number, totalItems: number): FeedbackTaskProps => ({
  variant: 'grid',
  task: {
    id,
    type: 'Feedback',
    scorecard: 'Test Scorecard',
    score: 'Test Score',
    time: '2 hours ago',
    summary: 'Feedback Summary',
    description: 'Feedback Description',
    data: {
      progress: (processedItems / totalItems) * 100,
      elapsedTime: '01:30:00',
      numberComplete: processedItems,
      numberTotal: totalItems,
      eta: '00:30:00',
    }
  },
  onClick: () => console.log(`Clicked task ${id}`),
});

export const Single: Story = {
  args: createTask(1, 75, 100),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    await expect(canvas.getByText('Feedback Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Feedback Description')).toBeInTheDocument();
    await expect(canvas.getByText('Test Scorecard')).toBeInTheDocument();
    await expect(canvas.getByText('Test Score')).toBeInTheDocument();
    await expect(canvas.getByText('2 hours ago')).toBeInTheDocument();
    await expect(canvas.getByText('Feedback')).toBeInTheDocument();
    
    const messageIcon = canvasElement.querySelector('.lucide.lucide-message-circle-more');
    expect(messageIcon).toBeInTheDocument();
    expect(messageIcon).toHaveClass('h-6', 'w-6');
    
    const seventyFiveElements = canvas.getAllByText(/75/);
    expect(seventyFiveElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
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
    
    await expect(canvas.getByText('Feedback Summary')).toBeInTheDocument();
    await expect(canvas.getByText('Feedback Description')).toBeInTheDocument();
    
    const ninetyElements = canvas.getAllByText(/90/);
    expect(ninetyElements).toHaveLength(2);
    await expect(canvas.getByText(/100/)).toBeInTheDocument();
    
    await expect(canvas.getByText('90%')).toBeInTheDocument();
  }
};

export const Grid: Story = {
  render: () => (
    <>
      <FeedbackTask {...createTask(1, 25, 100)} />
      <FeedbackTask {...createTask(2, 50, 100)} />
      <FeedbackTask {...createTask(3, 75, 100)} />
      <FeedbackTask {...createTask(4, 100, 100)} />
    </>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    
    const summaries = canvas.getAllByText('Feedback Summary');
    expect(summaries).toHaveLength(4);
    
    await expect(canvas.getByText('25%')).toBeInTheDocument();
    await expect(canvas.getByText('50%')).toBeInTheDocument();
    await expect(canvas.getByText('75%')).toBeInTheDocument();
    await expect(canvas.getByText('100%')).toBeInTheDocument();
    
    const messageIcons = canvasElement.querySelectorAll(
      '.lucide.lucide-message-circle-more'
    );
    expect(messageIcons).toHaveLength(4);
    
    const descriptions = canvas.getAllByText('Feedback Description');
    expect(descriptions).toHaveLength(4);
  }
};

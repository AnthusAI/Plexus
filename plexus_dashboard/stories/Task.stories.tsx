import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Task, TaskHeader, TaskContent } from '@/components/Task'
import { Activity } from 'lucide-react'

const meta = {
  title: 'Tasks/Task',
  component: Task,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Task>

export default meta
type Story = StoryObj<typeof Task>

const sampleTask = {
  id: 1,
  type: 'Sample Task',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  summary: 'Task Summary',
  description: 'Task Description',
}

const TaskStoryHeader = (props: any) => (
  <TaskHeader {...props}>
    <div className="flex justify-end w-full">
      <Activity className="h-6 w-6" />
    </div>
  </TaskHeader>
)

const TaskStoryContent = (props: any) => (
  <TaskContent {...props} />
)

export const Grid: Story = {
  args: {
    variant: 'grid',
    task: sampleTask,
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
}

export const Detail: Story = {
  args: {
    variant: 'detail',
    task: sampleTask,
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (Story) => (
      <div className="w-[600px]">
        <Story />
      </div>
    ),
  ],
}

export const DetailFullWidth: Story = {
  args: {
    ...Detail.args,
    isFullWidth: true,
  },
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <div className="w-full h-screen p-4">
        <Story />
      </div>
    ),
  ],
}

export const GridWithMany = {
  render: () => (
    <div className="grid grid-cols-2 gap-4">
      <Task
        variant="grid"
        task={{ ...sampleTask, id: 1, summary: 'First Task' }}
        renderHeader={TaskStoryHeader}
        renderContent={TaskStoryContent}
      />
      <Task
        variant="grid"
        task={{ ...sampleTask, id: 2, summary: 'Second Task' }}
        renderHeader={TaskStoryHeader}
        renderContent={TaskStoryContent}
      />
      <Task
        variant="grid"
        task={{ ...sampleTask, id: 3, summary: 'Third Task' }}
        renderHeader={TaskStoryHeader}
        renderContent={TaskStoryContent}
      />
      <Task
        variant="grid"
        task={{ ...sampleTask, id: 4, summary: 'Fourth Task' }}
        renderHeader={TaskStoryHeader}
        renderContent={TaskStoryContent}
      />
    </div>
  ),
}
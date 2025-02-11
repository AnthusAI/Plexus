import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { SimpleDialog } from '@/components/task-dispatch'
import { Play } from 'lucide-react'

const meta: Meta<typeof SimpleDialog> = {
  title: 'Task Dispatch/SimpleDialog',
  component: SimpleDialog,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof SimpleDialog>

export const Default: Story = {
  args: {
    action: {
      name: "Demo",
      icon: <Play className="mr-2 h-4 w-4" />,
      command: "demo",
      target: "demo",
      dialogType: "simple",
      description: "Run a demo of the model"
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    }
  }
}

export const WithLongDescription: Story = {
  args: {
    action: {
      name: "Optimization",
      icon: <Play className="mr-2 h-4 w-4" />,
      command: "optimize",
      target: "optimization",
      dialogType: "simple",
      description: "Optimize the model's performance by running a series of tests and adjustments to improve overall efficiency and accuracy. This process may take several minutes to complete."
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    }
  }
} 
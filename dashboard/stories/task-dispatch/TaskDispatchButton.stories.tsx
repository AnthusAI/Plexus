import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { TaskDispatchButton, SimpleDialog, EvaluationDialog } from '@/components/task-dispatch'
import { ClipboardCheck, Play, Zap } from 'lucide-react'

const meta: Meta<typeof TaskDispatchButton> = {
  title: 'Task Dispatch/TaskDispatchButton',
  component: TaskDispatchButton,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof TaskDispatchButton>

const mockConfig = {
  buttonLabel: "Run Task",
  actions: [
    {
      name: "Demo",
      icon: <Play className="mr-2 h-4 w-4" />,
      command: "demo",
      target: "demo",
      dialogType: "simple",
      description: "Run a demo of the model"
    },
    {
      name: "Evaluation",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Run model evaluation"
    },
    {
      name: "Optimization",
      icon: <Zap className="mr-2 h-4 w-4" />,
      command: "optimize",
      target: "optimization",
      dialogType: "simple",
      description: "Optimize model performance"
    }
  ],
  dialogs: {
    simple: SimpleDialog,
    evaluation: EvaluationDialog
  }
}

export const Default: Story = {
  args: {
    config: mockConfig
  }
}

export const CustomLabel: Story = {
  args: {
    config: {
      ...mockConfig,
      buttonLabel: "Custom Action"
    }
  }
} 
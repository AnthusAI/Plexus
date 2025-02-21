import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { EvaluationDialog } from '@/components/task-dispatch'
import { ClipboardCheck } from 'lucide-react'

const meta: Meta<typeof EvaluationDialog> = {
  title: 'Task Dispatch/EvaluationDialog',
  component: EvaluationDialog,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof EvaluationDialog>

export const AccuracyEvaluation: Story = {
  args: {
    action: {
      name: "Accuracy",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate accuracy",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model accuracy against ground truth"
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    }
  }
}

export const ConsistencyEvaluation: Story = {
  args: {
    action: {
      name: "Consistency",
      icon: <ClipboardCheck className="mr-2 h-4 w-4" />,
      command: "evaluate consistency",
      target: "evaluation",
      dialogType: "evaluation",
      description: "Evaluate model consistency across similar inputs"
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    }
  }
} 
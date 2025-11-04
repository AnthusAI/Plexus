import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { FeedbackEvaluationDialog } from '@/components/task-dispatch'
import { MessageCircleMore } from 'lucide-react'

const meta: Meta<typeof FeedbackEvaluationDialog> = {
  title: 'Evaluations/Dispatch/FeedbackEvaluationDialog',
  component: FeedbackEvaluationDialog,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof FeedbackEvaluationDialog>

export const Default: Story = {
  args: {
    action: {
      name: "Evaluate Feedback",
      icon: <MessageCircleMore className="mr-2 h-4 w-4" />,
      command: "evaluate feedback",
      target: "evaluation",
      dialogType: "feedback",
      description: "Evaluate feedback alignment by analyzing feedback items"
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    }
  }
}

export const WithInitialValues: Story = {
  args: {
    action: {
      name: "Evaluate Feedback",
      icon: <MessageCircleMore className="mr-2 h-4 w-4" />,
      command: "evaluate feedback",
      target: "evaluation",
      dialogType: "feedback",
      description: "Evaluate feedback alignment by analyzing feedback items"
    },
    isOpen: true,
    onClose: () => {},
    onDispatch: async (command: string, target?: string) => {
      console.log('Dispatching command:', { command, target })
    },
    initialOptions: {
      scorecardName: 'Call Criteria',
      scoreName: 'Greeting',
      days: 30
    }
  }
}

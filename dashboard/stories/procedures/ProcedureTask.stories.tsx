import type { Meta, StoryObj } from '@storybook/react'
import ProcedureTask, { ProcedureTaskData } from '@/components/ProcedureTask'

const meta: Meta<typeof ProcedureTask> = {
  title: 'Procedures/ProcedureTask',
  component: ProcedureTask,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof ProcedureTask>

// Mock procedure data
const mockProcedureData: ProcedureTaskData = {
  id: 'proc-123',
  title: 'Customer Service Optimization',
  featured: true,
  rootNodeId: 'node-root-123',
  createdAt: '2024-01-15T10:30:00Z',
  updatedAt: '2024-01-15T14:45:00Z',
  scorecard: {
    name: 'CS3 Services v2'
  },
  score: {
    name: 'Good Call'
  },
  task: {
    id: 'task-456',
    type: 'Procedure Run',
    status: 'RUNNING',
    target: 'procedure/run/proc-123',
    command: 'procedure run proc-123',
    description: 'Running optimization procedure for customer service calls',
    dispatchStatus: 'DISPATCHED',
    metadata: '{"experiment_type": "optimization", "priority": "high"}',
    createdAt: '2024-01-15T10:30:00Z',
    startedAt: '2024-01-15T10:32:00Z',
    completedAt: undefined,
    estimatedCompletionAt: '2024-01-15T11:00:00Z',
    errorMessage: undefined,
    errorDetails: undefined,
    currentStageId: 'stage-processing',
    stages: {
      items: [
        {
          id: 'stage-setup',
          name: 'Setup',
          order: 1,
          status: 'COMPLETED',
          statusMessage: 'Environment prepared',
          startedAt: '2024-01-15T10:30:00Z',
          completedAt: '2024-01-15T10:31:00Z',
          estimatedCompletionAt: '2024-01-15T10:31:00Z',
          processedItems: 1,
          totalItems: 1
        },
        {
          id: 'stage-processing',
          name: 'Processing',
          order: 2,
          status: 'RUNNING',
          statusMessage: 'Analyzing conversation patterns...',
          startedAt: '2024-01-15T10:32:00Z',
          completedAt: undefined,
          estimatedCompletionAt: '2024-01-15T10:55:00Z',
          processedItems: 42,
          totalItems: 100
        },
        {
          id: 'stage-evaluation',
          name: 'Evaluation',
          order: 3,
          status: 'PENDING',
          statusMessage: 'Waiting for processing to complete',
          startedAt: undefined,
          completedAt: undefined,
          estimatedCompletionAt: '2024-01-15T11:00:00Z',
          processedItems: 0,
          totalItems: 50
        }
      ]
    }
  }
}

const mockProcedureDataCompleted: ProcedureTaskData = {
  ...mockProcedureData,
  id: 'proc-456',
  title: 'Sales Call Analysis',
  featured: false,
  scorecard: {
    name: 'AW IB Sales'
  },
  score: {
    name: 'Pain Points'
  },
  task: {
    ...mockProcedureData.task!,
    id: 'task-789',
    status: 'COMPLETED',
    completedAt: '2024-01-15T11:15:00Z',
    currentStageId: 'stage-evaluation',
    stages: {
      items: [
        {
          id: 'stage-setup',
          name: 'Setup',
          order: 1,
          status: 'COMPLETED',
          statusMessage: 'Environment prepared',
          startedAt: '2024-01-15T10:30:00Z',
          completedAt: '2024-01-15T10:31:00Z',
          estimatedCompletionAt: '2024-01-15T10:31:00Z',
          processedItems: 1,
          totalItems: 1
        },
        {
          id: 'stage-processing',
          name: 'Processing',
          order: 2,
          status: 'COMPLETED',
          statusMessage: 'Analysis complete',
          startedAt: '2024-01-15T10:32:00Z',
          completedAt: '2024-01-15T10:55:00Z',
          estimatedCompletionAt: '2024-01-15T10:55:00Z',
          processedItems: 100,
          totalItems: 100
        },
        {
          id: 'stage-evaluation',
          name: 'Evaluation',
          order: 3,
          status: 'COMPLETED',
          statusMessage: 'Evaluation finished successfully',
          startedAt: '2024-01-15T10:55:00Z',
          completedAt: '2024-01-15T11:15:00Z',
          estimatedCompletionAt: '2024-01-15T11:00:00Z',
          processedItems: 50,
          totalItems: 50
        }
      ]
    }
  }
}

const mockProcedureDataFailed: ProcedureTaskData = {
  ...mockProcedureData,
  id: 'proc-789',
  title: 'Failed Analysis Procedure',
  featured: false,
  task: {
    ...mockProcedureData.task!,
    id: 'task-failed',
    status: 'FAILED',
    errorMessage: 'Insufficient data for analysis',
    errorDetails: '{"error_code": "DATA_INSUFFICIENT", "details": "Less than 10 samples available"}',
    completedAt: '2024-01-15T10:45:00Z',
    currentStageId: 'stage-processing'
  }
}

export const GridView: Story = {
  args: {
    variant: 'grid',
    procedure: mockProcedureData,
    isSelected: false,
    onDelete: (id) => console.log('Delete procedure:', id),
    onEdit: (id) => console.log('Edit procedure:', id),
    onDuplicate: (id) => console.log('Duplicate procedure:', id),
    onClick: () => console.log('Procedure clicked')
  }
}

export const GridViewSelected: Story = {
  args: {
    ...GridView.args,
    isSelected: true
  }
}

export const GridViewCompleted: Story = {
  args: {
    ...GridView.args,
    procedure: mockProcedureDataCompleted
  }
}

export const GridViewFailed: Story = {
  args: {
    ...GridView.args,
    procedure: mockProcedureDataFailed
  }
}

export const DetailView: Story = {
  args: {
    variant: 'detail',
    procedure: mockProcedureData,
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close procedure'),
    onDelete: (id) => console.log('Delete procedure:', id),
    onEdit: (id) => console.log('Edit procedure:', id),
    onDuplicate: (id) => console.log('Duplicate procedure:', id),
    onConversationFullscreenChange: (isFullscreen) => console.log('Conversation fullscreen:', isFullscreen)
  }
}

export const DetailViewFullWidth: Story = {
  args: {
    ...DetailView.args,
    isFullWidth: true
  }
}

export const DetailViewCompleted: Story = {
  args: {
    ...DetailView.args,
    procedure: mockProcedureDataCompleted
  }
}

export const DetailViewFailed: Story = {
  args: {
    ...DetailView.args,
    procedure: mockProcedureDataFailed
  }
}

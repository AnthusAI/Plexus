import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

interface ReportTaskData {
  id: string;
  title: string;
  command: string;
  elapsedTime?: string;
}

const meta: Meta<typeof ReportTask> = {
  title: 'Tasks/Types/ReportTask',
  component: ReportTask,
  parameters: {
    layout: 'centered',
  },
};

export default meta;
type Story = StoryObj<typeof ReportTask>;

type TaskType = BaseTaskProps<ReportTaskData>['task'];

const createTask = (id: string, overrides: Partial<TaskType> = {}) => {
  const baseTask: { variant: 'grid' | 'detail' | 'nested', task: TaskType, onClick: () => void } = {
    variant: 'grid',
    task: {
      id,
      type: 'Report',
      scorecard: 'Monthly Report',
      score: 'In Progress',
      time: '1 day ago',
      data: {
        id,
        title: 'Report Generation',
        command: 'plexus report generate --type monthly'
      },
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Preparing report generation...'
        },
        {
          key: 'processing',
          label: 'Processing',
          color: 'bg-secondary',
          name: 'Processing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        {
          key: 'finishing',
          label: 'Finishing',
          color: 'bg-primary',
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing report...'
        }
      ],
      ...overrides
    },
    onClick: () => console.log('Task clicked')
  }

  // Calculate overall progress if not provided in overrides
  if (!('processedItems' in overrides) && baseTask.task.stages) {
    const currentStage = baseTask.task.stages.find(
      stage => stage.name === baseTask.task.currentStageName
    )
    if (currentStage) {
      baseTask.task.processedItems = currentStage.processedItems
      baseTask.task.totalItems = currentStage.totalItems
    }
  }

  return baseTask
}

export const Starting: Story = {
  args: {
    ...createTask('starting', {
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'RUNNING',
          processedItems: 20,
          totalItems: 100,
          statusMessage: 'Loading activity data from database...'
        },
        {
          key: 'processing',
          label: 'Processing',
          color: 'bg-secondary',
          name: 'Processing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        {
          key: 'finishing',
          label: 'Finishing',
          color: 'bg-primary',
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing report...'
        }
      ],
      currentStageName: 'Initialization',
      status: 'RUNNING',
      data: {
        id: 'starting',
        title: 'Report Generation',
        command: 'plexus report generate --type monthly',
        elapsedTime: '15s'
      }
    }),
    variant: 'grid'
  }
};

export const Processing: Story = {
  args: {
    ...createTask('processing', {
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Activity data loaded'
        },
        {
          key: 'processing',
          label: 'Processing',
          color: 'bg-secondary',
          name: 'Processing',
          order: 2,
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Analyzing call metrics and trends...'
        },
        {
          key: 'finishing',
          label: 'Finishing',
          color: 'bg-primary',
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing report...'
        }
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      data: {
        id: 'processing',
        title: 'Report Generation',
        command: 'plexus report generate --type monthly',
        elapsedTime: '1m 30s'
      }
    }),
    variant: 'grid'
  }
};

export const Finishing: Story = {
  args: {
    ...createTask('finishing', {
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Activity data loaded'
        },
        {
          key: 'processing',
          label: 'Processing',
          color: 'bg-secondary',
          name: 'Processing',
          order: 2,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Analysis complete'
        },
        {
          key: 'finishing',
          label: 'Finishing',
          color: 'bg-primary',
          name: 'Finishing',
          order: 3,
          status: 'RUNNING',
          processedItems: 80,
          totalItems: 100,
          statusMessage: 'Generating final report...'
        }
      ],
      currentStageName: 'Finishing',
      status: 'RUNNING',
      data: {
        id: 'finishing',
        title: 'Report Generation',
        command: 'plexus report generate --type monthly',
        elapsedTime: '2m 45s'
      }
    }),
    variant: 'grid'
  }
};

export const Complete: Story = {
  args: {
    ...createTask('complete', {
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Activity data loaded'
        },
        {
          key: 'processing',
          label: 'Processing',
          color: 'bg-secondary',
          name: 'Processing',
          order: 2,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Analysis complete'
        },
        {
          key: 'finishing',
          label: 'Finishing',
          color: 'bg-primary',
          name: 'Finishing',
          order: 3,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Report generated successfully'
        }
      ],
      currentStageName: 'Finishing',
      status: 'COMPLETED',
      data: {
        id: 'complete',
        title: 'Report Generation',
        command: 'plexus report generate --type monthly',
        elapsedTime: '3m 0s'
      }
    }),
    variant: 'grid'
  }
};

export const Failed: Story = {
  args: {
    ...createTask('failed', {
      stages: [
        {
          key: 'initialization',
          label: 'Initialization',
          color: 'bg-primary',
          name: 'Initialization',
          order: 1,
          status: 'FAILED',
          processedItems: 20,
          totalItems: 100,
          statusMessage: 'Failed to load activity data'
        }
      ],
      currentStageName: 'Initialization',
      status: 'FAILED',
      data: {
        id: 'failed',
        title: 'Report Generation',
        command: 'plexus report generate --type monthly',
        elapsedTime: '1m 45s'
      }
    }),
    variant: 'grid'
  }
};

export const AllStages = {
  render: () => {
    // Ensure all tasks have the required properties
    const tasks = [
      Starting.args?.task,
      Processing.args?.task,
      Finishing.args?.task,
      Complete.args?.task,
      Failed.args?.task,
    ].filter((task): task is NonNullable<typeof task> => task !== undefined);

    return (
      <div className="grid grid-cols-1 gap-4">
        {tasks.map((task, index) => (
          <ReportTask key={task.id} variant="grid" task={task} />
        ))}
      </div>
    );
  },
};

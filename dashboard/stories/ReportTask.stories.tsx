import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ReportTask from '@/components/ReportTask';
import { BaseTaskProps } from '@/components/Task';

interface ReportTaskData {
  id: string;
  title: string;
  command: string;
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
  const baseTask = {
    variant: 'grid',
    task: {
      id,
      type: 'Report',
      scorecard: 'Monthly Report',
      score: 'In Progress',
      time: '1 day ago',
      summary: 'Generating monthly activity report',
      data: {
        id,
        title: 'Report Generation',
        command: 'plexus report generate --type monthly'
      },
      stages: [
        {
          name: 'Initialization',
          order: 1,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Preparing report generation...'
        },
        {
          name: 'Processing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        {
          name: 'Finishing',
          order: 3,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing report...'
        }
      ],
      processedItems: 0,
      totalItems: 100,
      ...overrides
    } as TaskType,
    onClick: () => console.log(`Clicked task ${id}`),
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
  args: createTask('starting', {
    stages: [
      {
        name: 'Initialization',
        order: 1,
        status: 'RUNNING',
        processedItems: 20,
        totalItems: 100,
        statusMessage: 'Loading activity data from database...'
      },
      {
        name: 'Processing',
        order: 2,
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        statusMessage: 'Processing activity data...'
      },
      {
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
    elapsedTime: '15s',
    estimatedTimeRemaining: '2m 45s'
  })
};

export const Processing: Story = {
  args: createTask('processing', {
    stages: [
      {
        name: 'Initialization',
        order: 1,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Activity data loaded'
      },
      {
        name: 'Processing',
        order: 2,
        status: 'RUNNING',
        processedItems: 45,
        totalItems: 100,
        statusMessage: 'Analyzing call metrics and trends...'
      },
      {
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
    elapsedTime: '1m 30s',
    estimatedTimeRemaining: '1m 15s'
  })
};

export const Finishing: Story = {
  args: createTask('finishing', {
    stages: [
      {
        name: 'Initialization',
        order: 1,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Activity data loaded'
      },
      {
        name: 'Processing',
        order: 2,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Analysis complete'
      },
      {
        name: 'Finishing',
        order: 3,
        status: 'RUNNING',
        processedItems: 80,
        totalItems: 100,
        statusMessage: 'Generating PDF report...'
      }
    ],
    currentStageName: 'Finishing',
    status: 'RUNNING',
    elapsedTime: '2m 45s',
    estimatedTimeRemaining: '15s'
  })
};

export const Complete: Story = {
  args: createTask('complete', {
    stages: [
      {
        name: 'Initialization',
        order: 1,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Activity data loaded'
      },
      {
        name: 'Processing',
        order: 2,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Analysis complete'
      },
      {
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
    elapsedTime: '3m 0s'
  })
};

export const Failed: Story = {
  args: createTask('failed', {
    stages: [
      {
        name: 'Initialization',
        order: 1,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
        statusMessage: 'Activity data loaded'
      },
      {
        name: 'Processing',
        order: 2,
        status: 'FAILED',
        processedItems: 50,
        totalItems: 100,
        statusMessage: 'Error analyzing call metrics: insufficient data'
      },
      {
        name: 'Finishing',
        order: 3,
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        statusMessage: 'Finalizing report...'
      }
    ],
    currentStageName: 'Processing',
    status: 'FAILED',
    elapsedTime: '1m 45s'
  })
};

export const Demo = {
  render: () => (
    <div className="space-y-4 p-4">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Starting</div>
        <ReportTask {...Starting.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Processing</div>
        <ReportTask {...Processing.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Finishing</div>
        <ReportTask {...Finishing.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Complete</div>
        <ReportTask {...Complete.args} />
      </div>
      <div>
        <div className="text-sm text-muted-foreground mb-2">Failed</div>
        <ReportTask {...Failed.args} />
      </div>
    </div>
  )
};

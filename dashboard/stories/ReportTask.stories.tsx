import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ReportTask, { ReportTaskProps } from '../components/ReportTask';
// BaseTaskProps might not be directly needed here if ReportTaskProps is comprehensive
// import { BaseTaskProps } from '../components/Task'; 

// Assuming ReportTaskData is defined within ReportTask.tsx and implicitly typed via ReportTaskProps
// If ReportTaskData fields are needed explicitly for mocking, they should be aligned with the actual interface.

const meta: Meta<typeof ReportTask> = {
  title: 'Tasks/Types/ReportTask',
  component: ReportTask,
  parameters: {
    layout: 'centered',
  },
  // argTypes for controlling props in Storybook UI if needed
};

export default meta;
type Story = StoryObj<typeof ReportTask>;

// TaskObjectType is the type of the 'task' object within ReportTaskProps
type TaskObjectType = ReportTaskProps['task'];

// createTaskObject now only returns the task object
// Ensure the data structure within task.data matches ReportTaskData from ReportTask.tsx
const createTaskObject = (id: string, overrides: Partial<TaskObjectType> = {}): TaskObjectType => {
  const baseTaskObject: TaskObjectType = {
    id,
    type: 'Report',
    scorecard: 'Monthly Report', // Example, can be overridden
    score: 'Status Placeholder',    // Example, can be overridden
    time: new Date(Date.now() - 86400000).toISOString(), // "1 day ago"
    data: { // This structure must match ReportTaskData from ReportTask.tsx
      id,
      title: `Report: ${id}`, // Default title
      // name, configName, configDescription, createdAt, updatedAt, output, reportBlocks
      // are part of ReportTaskData. Mock them as needed or rely on overrides.
      // Example:
      // name: `Report Name for ${id}`,
      // configName: `Config for ${id}`,
      // createdAt: new Date().toISOString(),
      // updatedAt: new Date().toISOString(),
      // output: `# Default Markdown for ${id}`,
      // reportBlocks: [], 
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
        totalItems: 100, // Example total
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
    status: 'PENDING', // Default status
    ...overrides // Spread overrides for the task object
  };

  // Calculate overall progress if not provided in overrides
  if (!('processedItems' in overrides) && baseTaskObject.stages) {
    const currentStage = baseTaskObject.stages.find(
      stage => stage.name === baseTaskObject.currentStageName
    );
    if (currentStage) {
      baseTaskObject.processedItems = currentStage.processedItems;
      baseTaskObject.totalItems = currentStage.totalItems;
    }
  }
  return baseTaskObject;
};

export const Starting: Story = {
  args: {
    variant: 'grid',
    task: createTaskObject('starting', {
      stages: [
        { key: 'initialization', label: 'Initialization', color: 'bg-primary', name: 'Initialization', order: 1, status: 'RUNNING', processedItems: 20, totalItems: 100, statusMessage: 'Loading activity data...' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', name: 'Processing', order: 2, status: 'PENDING', processedItems: 0, totalItems: 100, statusMessage: 'Waiting...' },
        { key: 'finishing', label: 'Finishing', color: 'bg-primary', name: 'Finishing', order: 3, status: 'PENDING', processedItems: 0, totalItems: 100, statusMessage: 'Waiting...' }
      ],
      currentStageName: 'Initialization',
      status: 'RUNNING',
      data: { id: 'starting', title: 'Report Gen - Starting' }
    }),
    onClick: () => console.log('Starting Task clicked')
  }
};

export const Processing: Story = {
  args: {
    variant: 'grid',
    task: createTaskObject('processing', {
      stages: [
        { key: 'initialization', label: 'Initialization', color: 'bg-primary', name: 'Initialization', order: 1, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Done' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', name: 'Processing', order: 2, status: 'RUNNING', processedItems: 45, totalItems: 100, statusMessage: 'Analyzing data...' },
        { key: 'finishing', label: 'Finishing', color: 'bg-primary', name: 'Finishing', order: 3, status: 'PENDING', processedItems: 0, totalItems: 100, statusMessage: 'Waiting...' }
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      data: { id: 'processing', title: 'Report Gen - Processing' }
    }),
    onClick: () => console.log('Processing Task clicked')
  }
};

export const Finishing: Story = {
  args: {
    variant: 'grid',
    task: createTaskObject('finishing', {
      stages: [
        { key: 'initialization', label: 'Initialization', color: 'bg-primary', name: 'Initialization', order: 1, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Done' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', name: 'Processing', order: 2, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Done' },
        { key: 'finishing', label: 'Finishing', color: 'bg-primary', name: 'Finishing', order: 3, status: 'RUNNING', processedItems: 80, totalItems: 100, statusMessage: 'Generating output...' }
      ],
      currentStageName: 'Finishing',
      status: 'RUNNING',
      data: { id: 'finishing', title: 'Report Gen - Finishing' }
    }),
    onClick: () => console.log('Finishing Task clicked')
  }
};

export const Complete: Story = {
  args: {
    variant: 'grid',
    task: createTaskObject('complete', {
      stages: [
        { key: 'initialization', label: 'Initialization', color: 'bg-primary', name: 'Initialization', order: 1, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Done' },
        { key: 'processing', label: 'Processing', color: 'bg-secondary', name: 'Processing', order: 2, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Done' },
        { key: 'finishing', label: 'Finishing', color: 'bg-primary', name: 'Finishing', order: 3, status: 'COMPLETED', processedItems: 100, totalItems: 100, statusMessage: 'Report ready' }
      ],
      currentStageName: 'Finishing', // Or could be undefined/last stage if that's the convention
      status: 'COMPLETED',
      completedAt: new Date().toISOString(), // Add completion time
      data: { 
        id: 'complete', 
        title: 'Report Gen - Complete',
        updatedAt: new Date().toISOString() // Reflect completion
      }
    }),
    onClick: () => console.log('Complete Task clicked')
  }
};

export const Failed: Story = {
  args: {
    variant: 'grid',
    task: createTaskObject('failed', {
      stages: [
        { key: 'initialization', label: 'Initialization', color: 'bg-primary', name: 'Initialization', order: 1, status: 'FAILED', processedItems: 20, totalItems: 100, statusMessage: 'Error during init' },
        // Other stages might be PENDING or not shown if failure is early
      ],
      currentStageName: 'Initialization',
      status: 'FAILED',
      errorMessage: 'Database connection timed out after 3 attempts.',
      completedAt: new Date().toISOString(), // Mark failure time
      data: { 
        id: 'failed', 
        title: 'Report Gen - Failed',
        updatedAt: new Date().toISOString() // Reflect failure time
      }
    }),
    onClick: () => console.log('Failed Task clicked')
  }
};

export const AllStages: Story = {
  render: () => {
    const storyArgsArray: Array<ReportTaskProps | undefined> = [ // Ensure type matches Story['args']
      Starting.args,
      Processing.args,
      Finishing.args,
      Complete.args,
      Failed.args,
    ];

    const validStoryArgs = storyArgsArray.filter((args): args is ReportTaskProps => !!args);

    return (
      <div className="grid grid-cols-1 gap-4 p-4 max-w-md mx-auto">
        {validStoryArgs.map((storyArg) => (
          <ReportTask key={storyArg.task.id} {...storyArg} />
        ))}
      </div>
    );
  },
};

export const BareVariant: Story = {
  args: {
    variant: 'bare',
    task: { 
      id: 'bare-variant',
      type: 'Report',
      scorecard: '', 
      score: '', 
      time: new Date().toISOString(),
      data: {
        id: 'bare-variant',
        title: 'Bare Report Content',
        output: 
`# Bare Report Title (from Markdown)

This is **markdown** content rendered directly.

\`\`\`block
class: SimpleBlock
name: MySimpleBlockInstance
config_value: TestValueFromMarkdown
\`\`\`

More markdown.

\`\`\`block
class: AnotherBlock
name: SecondBlockInstance
\`\`\`
`,
        reportBlocks: [
          {
            type: 'SimpleBlock',
            name: 'MySimpleBlockInstance',
            config: { config_value: 'TestValueFromMarkdown' },
            output: { content: 'Output for SimpleBlock (bare variant).' },
            position: 1,
          },
          {
            type: 'AnotherBlock',
            name: 'SecondBlockInstance',
            config: {},
            output: { message: 'Output from AnotherBlock (bare variant).' },
            position: 2,
          }
        ],
        createdAt: new Date(Date.now() - 3600000).toISOString(),
        updatedAt: new Date().toISOString(),
      },
      status: 'COMPLETED',
      stages: [],
    },
    onClick: () => console.log('Bare task clicked (no-op for bare variant)')
  },
};

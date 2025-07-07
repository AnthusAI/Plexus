import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Task, TaskHeader, TaskContent, TaskComponentProps, BaseTaskProps } from '../components/Task'
import { Activity } from 'lucide-react'
import { BaseTaskData } from '@/types/base'

interface TaskStoryData extends BaseTaskData {
  id: string
  title: string
  description?: string
  command?: string
  elapsedTime?: string
  estimatedTimeRemaining?: string
}

const meta = {
  title: 'Tasks/Task',
  component: Task,
  parameters: {
    layout: 'centered',
  },
  argTypes: {
    commandDisplay: {
      control: 'select',
      options: ['hide', 'show', 'full'],
      defaultValue: 'show',
      description: 'Controls how to display the command'
    },
    statusMessageDisplay: {
      control: 'select',
      options: ['always', 'never', 'error-only'],
      defaultValue: 'always',
      description: 'Controls when to display the status message'
    }
  }
} satisfies Meta<typeof Task>

export default meta
type Story = StoryObj<TaskComponentProps<TaskStoryData>>

const createTask = (id: string, overrides = {}) => ({
  id,
  type: 'Sample Task',
  scorecard: 'Test Scorecard',
  score: 'Test Score',
  time: '2 hours ago',
  description: 'Task Description',
  command: 'python process_data.py --input data.csv --output results.json',
  output: undefined, // Universal Code YAML output
  attachedFiles: undefined, // Array of S3 file keys for attachments
  stdout: undefined, // Task stdout output
  stderr: undefined, // Task stderr output
  data: {
    id,
    title: 'Sample Task',
    description: 'Task Description',
    command: 'python process_data.py --input data.csv --output results.json'
  },
  ...overrides
})

const TaskStoryHeader = (props: BaseTaskProps<TaskStoryData>) => (
  <TaskHeader {...props}>
    <div className="flex justify-end w-full">
      <Activity className="h-6 w-6" />
    </div>
  </TaskHeader>
)

const TaskStoryContent = (props: BaseTaskProps<TaskStoryData>) => (
  <TaskContent {...props} />
)

const baseArgs: Omit<TaskComponentProps<TaskStoryData>, 'task'> = {
  variant: 'grid',
  renderHeader: TaskStoryHeader,
  renderContent: TaskStoryContent,
  showProgress: true,
  isFullWidth: false,
  isLoading: false,
}

const sampleStages = [
  {
    key: 'Initializing',
    label: 'Initializing',
    color: 'bg-primary',
    name: 'Initializing',
    order: 0,
    status: 'COMPLETED' as const,
    processedItems: 100,
    totalItems: 100,
    statusMessage: 'Data loaded'
  },
  {
    key: 'Processing',
    label: 'Processing',
    color: 'bg-secondary',
    name: 'Processing',
    order: 1,
    status: 'RUNNING' as const,
    processedItems: 45,
    totalItems: 100,
    statusMessage: 'Processing activity data...'
  },
  {
    key: 'Finalizing',
    label: 'Finalizing',
    color: 'bg-primary',
    name: 'Finalizing',
    order: 2,
    status: 'PENDING' as const,
    processedItems: 0,
    totalItems: 100,
    statusMessage: 'Finalizing...'
  }
]

const stories = {
  Starting: {
    args: {
      ...baseArgs,
      task: createTask('starting', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        statusMessage: 'Initializing task...'
      }),
    },
  },
  Announced: {
    args: {
      ...baseArgs,
      showPreExecutionStages: true,
      task: createTask('announced', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        dispatchStatus: 'DISPATCHED',
        celeryTaskId: '',
        statusMessage: 'Activity announced...'
      }),
    },
  },
  Claimed: {
    args: {
      ...baseArgs,
      showPreExecutionStages: true,
      task: createTask('claimed', {
        stages: [],
        status: 'PENDING',
        processedItems: 0,
        totalItems: 100,
        dispatchStatus: 'DISPATCHED',
        celeryTaskId: 'task-123',
        statusMessage: 'Activity claimed.'
      }),
    },
  },
} as const

export const Starting: Story = stories.Starting
export const Announced: Story = stories.Announced
export const Claimed: Story = stories.Claimed

export const Initializing: Story = {
  args: {
    ...baseArgs,
    task: createTask('initializing', {
      stages: [
        {
          ...sampleStages[0],
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Loading data...'
        },
        sampleStages[1],
        sampleStages[2]
      ],
      currentStageName: 'Initializing',
      status: 'RUNNING',
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
  },
}

export const Running: Story = {
  args: {
    ...baseArgs,
    task: createTask('running', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        sampleStages[2]
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
  },
}

export const NoStages: Story = {
  args: {
    ...baseArgs,
    task: createTask('nostages', {
      stages: [],
      currentStageName: 'Processing',
      processedItems: 45,
      totalItems: 100,
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s',
      status: 'RUNNING',
      statusMessage: 'Fetching report list...'
    }),
  },
}

export const Finalizing: Story = {
  args: {
    ...baseArgs,
    task: createTask('finalizing', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Processing complete'
        },
        {
          ...sampleStages[2],
          status: 'RUNNING',
          statusMessage: 'Generating final report...'
        }
      ],
      currentStageName: 'Finalizing',
      status: 'RUNNING',
      elapsedTime: '4m 45s'
    }),
  },
}

export const Complete: Story = {
  args: {
    ...baseArgs,
    task: createTask('complete', {
      stages: sampleStages.map(stage => ({
        ...stage,
        status: 'COMPLETED',
        processedItems: 100,
        totalItems: 100,
      })),
      currentStageName: 'Complete',
      status: 'COMPLETED',
      elapsedTime: '5m 0s'
    }),
  },
}

export const Failed: Story = {
  args: {
    ...baseArgs,
    task: createTask('failed', {
      stages: [
        {
          ...sampleStages[0],
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          ...sampleStages[1],
          status: 'FAILED',
          processedItems: 50,
          totalItems: 100,
          statusMessage: 'Error: Insufficient data for report generation'
        },
        sampleStages[2]
      ],
      currentStageName: 'Processing',
      status: 'FAILED',
      elapsedTime: '2m 15s'
    }),
  },
}

export const NoProgress: Story = {
  args: {
    ...baseArgs,
    task: createTask('noprogress', {
      stages: [
        {
          name: 'Initializing',
          order: 0,
          status: 'COMPLETED',
          processedItems: 100,
          totalItems: 100,
          statusMessage: 'Data loaded'
        },
        {
          name: 'Processing',
          order: 1,
          status: 'RUNNING',
          processedItems: 45,
          totalItems: 100,
          statusMessage: 'Processing activity data...'
        },
        {
          name: 'Finalizing',
          order: 2,
          status: 'PENDING',
          processedItems: 0,
          totalItems: 100,
          statusMessage: 'Finalizing...'
        }
      ],
      currentStageName: 'Processing',
      status: 'RUNNING',
      elapsedTime: '2m 15s',
      estimatedTimeRemaining: '2m 45s'
    }),
    showProgress: false,
  },
}

export const Detail: Story = {
  args: {
    variant: 'detail',
    task: createTask('1', {
      type: 'Starting',
      description: 'Task is starting...'
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[600px]">
        <StoryFn />
      </div>
    )
  ]
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
    (Story: React.ComponentType) => (
      <div className="w-full h-screen p-4">
        <Story />
      </div>
    ),
  ],
}

export const DetailWithFullCommand: Story = {
  args: {
    variant: 'detail',
    task: createTask('command-test', {
      type: 'Test Task',
      command: 'python process_data.py --input /very/long/path/to/input/data.csv --output /another/very/long/path/to/output/results.json --config /path/to/config.yaml --verbose --debug --log-level INFO --batch-size 1000 --workers 4 --additional-param value --another-param "some value with spaces" --yet-another-param=123',
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
    commandDisplay: 'full'
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[800px]">
        <StoryFn />
      </div>
    )
  ]
}

export const Command: Story = {
  render: () => {
    const longCommand = 'python process_data.py --input /very/long/path/to/input/data.csv --output /another/very/long/path/to/output/results.json --config /path/to/config.yaml --verbose --debug --log-level INFO --batch-size 1000 --workers 4'
    
    const variants: Array<{
      title: string;
      args: TaskComponentProps<TaskStoryData>;
    }> = [
      {
        title: 'Hidden Command',
        args: {
          ...baseArgs,
          commandDisplay: 'hide',
          task: createTask('command-hidden', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      },
      {
        title: 'Single Line (Truncated)',
        args: {
          ...baseArgs,
          commandDisplay: 'show',
          task: createTask('command-single', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      },
      {
        title: 'Full Command (Wrapped)',
        args: {
          ...baseArgs,
          commandDisplay: 'full',
          task: createTask('command-full', {
            command: longCommand,
            stages: sampleStages,
            currentStageName: 'Processing',
            status: 'RUNNING',
            processedItems: 45,
            totalItems: 100,
            statusMessage: 'Processing activity data...'
          }),
        }
      }
    ]

    return (
      <div className="space-y-8">
        {variants.map(({ title, args }) => (
          <div key={title}>
            <div className="text-sm text-muted-foreground mb-2">{title}</div>
            <Task {...args} />
          </div>
        ))}
      </div>
    )
  }
}

export const StatusMessageAlwaysShown: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'always',
    task: createTask('status-always', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
  },
}

export const StatusMessageNeverShown: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'never',
    task: createTask('status-never', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'Processing activity data...'
    }),
  },
}

export const StatusMessageErrorOnly: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'error-only',
    task: createTask('status-error', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'FAILED',
      processedItems: 45,
      totalItems: 100,
      errorMessage: 'Failed to process data: Invalid format'
    }),
  },
}

export const StatusMessageErrorOnlyWithoutError: Story = {
  args: {
    ...baseArgs,
    statusMessageDisplay: 'error-only',
    task: createTask('status-error-no-error', {
      stages: sampleStages,
      currentStageName: 'Processing',
      status: 'RUNNING',
      processedItems: 45,
      totalItems: 100,
      statusMessage: 'This message should not be shown'
    }),
  },
}

// Universal Code and Attachments Stories
export const WithUniversalCode: Story = {
  args: {
    variant: 'detail',
    task: createTask('with-universal-code', {
      type: 'Prediction Test',
      command: 'predict --scorecard "termlifev1" --score "Assumptive Close" --item "276514287" --format json',
      status: 'COMPLETED',
      stages: sampleStages.map(stage => ({ ...stage, status: 'COMPLETED' as const })),
      output: `# ====================================
# Task Output Context
# ====================================
# This Universal Code was generated from a task execution.
# Task Type: Prediction Test
# Command: predict --scorecard "termlifev1" --score "Assumptive Close" --item "276514287" --format json
# 
# The structured output below contains the results and context from the task execution.

prediction_results:
  - item_id: "276514287"
    text: "I'm looking for a policy that will help secure my family's financial future..."
    Assumptive Close:
      value: "Yes"
      explanation: "The customer's language shows readiness to move forward with a purchase decision. Phrases like 'looking for a policy' and 'secure my family's financial future' indicate strong intent and urgency."
      cost:
        input_tokens: 152
        output_tokens: 48
        total_cost: 0.0023
      trace:
        model: "gpt-4o-mini"
        temperature: 0.1
        max_tokens: 150

task_metadata:
  scorecard: "termlifev1"
  score: "Assumptive Close"
  item_id: "276514287"
  execution_time: "1.2s"
  timestamp: "2025-01-06T15:30:45Z"`
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[800px]">
        <StoryFn />
      </div>
    )
  ]
}

export const WithAttachmentsAndOutput: Story = {
  args: {
    variant: 'detail',
    task: createTask('with-attachments-output', {
      type: 'Evaluation Report',
      command: 'plexus evaluate accuracy --scorecard "termlifev1" --number-of-samples 100',
      status: 'COMPLETED',
      stages: sampleStages.map(stage => ({ ...stage, status: 'COMPLETED' as const })),
      output: `# ====================================
# Evaluation Report Output
# ====================================
# Generated evaluation results for accuracy testing
# Scorecard: termlifev1
# Sample Size: 100 items
# Accuracy: 87.5%

evaluation_summary:
  scorecard: "termlifev1"
  type: "accuracy"
  total_items: 100
  processed_items: 100
  accuracy: 0.875
  
detailed_metrics:
  precision: 0.923
  recall: 0.851
  f1_score: 0.885
  
confusion_matrix:
  true_positive: 42
  false_positive: 3
  true_negative: 45
  false_negative: 7
  
score_distribution:
  "Yes": 48
  "No": 45
  "Maybe": 7`,
      attachedFiles: [
        'evaluations/2025-01-06/eval_123456/output.json',
        'evaluations/2025-01-06/eval_123456/confusion_matrix.csv',
        'evaluations/2025-01-06/eval_123456/detailed_results.xlsx',
        'evaluations/2025-01-06/eval_123456/trace_logs.txt'
      ],
      stdout: `Starting accuracy evaluation for scorecard: termlifev1
Loading samples... Found 100 items
Processing items: 100/100 [████████████████████████████████] 100%
Calculating metrics...
Accuracy: 87.50%
Precision: 92.31% 
Recall: 85.07%
F1 Score: 88.54%
Evaluation complete! Results saved to output.json`,
      stderr: `2025-01-06 15:30:12 [WARNING] Item 47 has missing metadata field 'source'
2025-01-06 15:30:15 [WARNING] Score confidence low (0.3) for item 82
2025-01-06 15:30:18 [INFO] Batch processing completed with 2 warnings`
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[900px]">
        <StoryFn />
      </div>
    )
  ]
}

export const WithStdoutOnly: Story = {
  args: {
    variant: 'detail',
    task: createTask('with-stdout', {
      type: 'Data Processing',
      command: 'python analyze_data.py --input dataset.csv --output results.json',
      status: 'COMPLETED',
      stages: sampleStages.map(stage => ({ ...stage, status: 'COMPLETED' as const })),
      stdout: `Analyzing dataset.csv...
Found 1,247 records
Processing columns: name, age, location, score
Applying filters...
Removed 23 invalid records
Calculating statistics...
  - Mean score: 78.4
  - Median score: 81.0
  - Standard deviation: 12.7
Generating visualizations...
Saving results to results.json
Analysis complete!`
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[700px]">
        <StoryFn />
      </div>
    )
  ]
}

export const WithStderrOnly: Story = {
  args: {
    variant: 'detail',
    task: createTask('with-stderr', {
      type: 'Model Training',
      command: 'python train_model.py --config model_config.yaml',
      status: 'FAILED',
      stages: [
        { ...sampleStages[0], status: 'COMPLETED' as const },
        { ...sampleStages[1], status: 'FAILED' as const, statusMessage: 'Training failed due to configuration error' },
        sampleStages[2]
      ],
      stderr: `2025-01-06 15:25:10 [ERROR] Configuration file 'model_config.yaml' not found
2025-01-06 15:25:10 [ERROR] Required parameter 'learning_rate' missing
2025-01-06 15:25:10 [ERROR] Invalid value for 'batch_size': must be positive integer
2025-01-06 15:25:10 [FATAL] Cannot proceed with training due to configuration errors
Traceback (most recent call last):
  File "train_model.py", line 45, in load_config
    config = yaml.load(config_file)
FileNotFoundError: [Errno 2] No such file or directory: 'model_config.yaml'`
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[700px]">
        <StoryFn />
      </div>
    )
  ]
}

export const AttachmentsOnly: Story = {
  args: {
    variant: 'detail',
    task: createTask('attachments-only', {
      type: 'Report Generation',
      command: 'plexus report run --config "Monthly Report"',
      status: 'COMPLETED',
      stages: sampleStages.map(stage => ({ ...stage, status: 'COMPLETED' as const })),
      attachedFiles: [
        'reports/2025-01/monthly_report.pdf',
        'reports/2025-01/raw_data.csv',
        'reports/2025-01/charts/performance_chart.png',
        'reports/2025-01/charts/trend_analysis.svg',
        'reports/2025-01/metadata.json'
      ]
    }),
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
    renderHeader: TaskStoryHeader,
    renderContent: TaskStoryContent,
  },
  decorators: [
    (StoryFn) => (
      <div className="w-[700px]">
        <StoryFn />
      </div>
    )
  ]
}

export const AllOutputTypes: Story = {
  render: () => {
    const variants = [
      {
        title: 'Grid View (No Output Shown)',
        variant: 'grid' as const,
        width: '300px'
      },
      {
        title: 'Detail View - Universal Code Only',
        variant: 'detail' as const,
        width: '600px'
      },
      {
        title: 'Detail View - All Output Types',
        variant: 'detail' as const,
        width: '800px'
      }
    ]

    return (
      <div className="space-y-8">
        {variants.map(({ title, variant, width }, index) => (
          <div key={title}>
            <div className="text-sm text-muted-foreground mb-4">{title}</div>
            <div style={{ width }}>
              <Task
                variant={variant}
                task={createTask(`all-output-${index}`, {
                  type: 'Complex Analysis',
                  command: 'analyze --input data.json --output results.yaml --verbose',
                  status: 'COMPLETED',
                  stages: sampleStages.map(stage => ({ ...stage, status: 'COMPLETED' as const })),
                  ...(index === 1 ? {
                    // Universal Code only
                    output: `analysis_results:
  total_records: 1500
  valid_records: 1456
  accuracy: 0.891
  performance_metrics:
    precision: 0.923
    recall: 0.867`
                  } : index === 2 ? {
                    // All output types
                    output: `analysis_results:
  total_records: 1500
  valid_records: 1456
  accuracy: 0.891`,
                    attachedFiles: ['analysis/output.json', 'analysis/chart.png'],
                    stdout: 'Processing complete. Results saved.',
                    stderr: '2025-01-06 [WARNING] 44 records had missing data'
                  } : {})
                })}
                renderHeader={TaskStoryHeader}
                renderContent={TaskStoryContent}
                isFullWidth={false}
                onToggleFullWidth={() => console.log('Toggle full width')}
                onClose={() => console.log('Close')}
              />
            </div>
          </div>
        ))}
      </div>
    )
  }
}
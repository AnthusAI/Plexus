import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { TaskOutputDisplay } from '../components/TaskOutputDisplay'

const meta = {
  title: 'Tasks/TaskOutputDisplay',
  component: TaskOutputDisplay,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays Universal Code output, file attachments, and stdout/stderr for tasks. This component is automatically integrated into the generic Task component when in detail view.'
      }
    }
  },
  argTypes: {
    output: {
      control: 'text',
      description: 'Universal Code YAML output from task execution'
    },
    attachedFiles: {
      control: 'object',
      description: 'Array of S3 file keys for task attachments'
    },
    stdout: {
      control: 'text', 
      description: 'Standard output from task execution'
    },
    stderr: {
      control: 'text',
      description: 'Standard error output from task execution'
    },
    command: {
      control: 'text',
      description: 'Task command for context'
    },
    taskType: {
      control: 'text',
      description: 'Task type for context'
    }
  }
} satisfies Meta<typeof TaskOutputDisplay>

export default meta
type Story = StoryObj<typeof meta>

// Sample data for stories
const sampleUniversalCode = `# ====================================
# Task Output Context
# ====================================
# This Universal Code was generated from a task execution.
# Task Type: Prediction Test
# Command: predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287" --format json
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
  scorecard: "example-scorecard-2"
  score: "Assumptive Close"
  item_id: "276514287"
  execution_time: "1.2s"
  timestamp: "2025-01-06T15:30:45Z"`

const sampleStdout = `Starting prediction for item: 276514287
Loading scorecard: example-scorecard-2
Initializing score: Assumptive Close
Processing text input...
Generating prediction...
Prediction complete!
- Value: Yes
- Confidence: 0.85
- Explanation: Customer shows strong purchase intent
Saving results to output.json
Task completed successfully in 1.2s`

const sampleStderr = `2025-01-06 15:30:12 [WARNING] Item text is shorter than recommended (45 chars)
2025-01-06 15:30:13 [INFO] Using fallback model gpt-4o-mini due to rate limits
2025-01-06 15:30:14 [WARNING] Prediction confidence below threshold (0.85 < 0.9)`

const sampleAttachments = [
  'predictions/2025-01-06/pred_123456/output.json',
  'predictions/2025-01-06/pred_123456/trace_log.txt',
  'predictions/2025-01-06/pred_123456/metadata.yaml'
]

export const Empty: Story = {
  args: {},
  parameters: {
    docs: {
      description: {
        story: 'TaskOutputDisplay with no data. The component renders nothing when no output data is provided.'
      }
    }
  }
}

export const UniversalCodeOnly: Story = {
  args: {
    output: sampleUniversalCode,
    command: 'predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287" --format json',
    taskType: 'Prediction Test'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only Universal Code output with task context. The Code button allows expanding/collapsing the YAML output with copy functionality.'
      }
    }
  }
}

export const AttachmentsOnly: Story = {
  args: {
    attachedFiles: sampleAttachments,
    command: 'predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287"',
    taskType: 'Prediction Test'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only file attachments. Files are listed with view buttons (functionality to be implemented).'
      }
    }
  }
}

export const StdoutOnly: Story = {
  args: {
    stdout: sampleStdout,
    command: 'predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287"',
    taskType: 'Prediction Test'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only stdout output from task execution. Useful for viewing command progress and results.'
      }
    }
  }
}

export const StderrOnly: Story = {
  args: {
    stderr: sampleStderr,
    command: 'predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287"',
    taskType: 'Prediction Test'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows only stderr output from task execution. Displayed in red to indicate errors/warnings.'
      }
    }
  }
}

export const AllOutputTypes: Story = {
  args: {
    output: sampleUniversalCode,
    attachedFiles: sampleAttachments,
    stdout: sampleStdout,
    stderr: sampleStderr,
    command: 'predict --scorecard "example-scorecard-2" --score "Assumptive Close" --item "276514287" --format json',
    taskType: 'Prediction Test'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows all output types together. Each type has its own toggle button and can be expanded independently.'
      }
    }
  }
}

export const EvaluationExample: Story = {
  args: {
    output: `# ====================================
# Evaluation Report Output
# ====================================
# Generated evaluation results for accuracy testing
# Scorecard: example-scorecard-2
# Sample Size: 100 items
# Accuracy: 87.5%

evaluation_summary:
  scorecard: "example-scorecard-2"
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
    stdout: `Starting accuracy evaluation for scorecard: example-scorecard-2
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
2025-01-06 15:30:18 [INFO] Batch processing completed with 2 warnings`,
    command: 'plexus evaluate accuracy --scorecard "example-scorecard-2" --number-of-samples 100',
    taskType: 'Accuracy Evaluation'
  },
  parameters: {
    docs: {
      description: {
        story: 'Example of TaskOutputDisplay for an evaluation task with comprehensive output including Universal Code, attachments, and logs.'
      }
    }
  }
}

export const FailedTaskExample: Story = {
  args: {
    stderr: `2025-01-06 15:25:10 [ERROR] Configuration file 'model_config.yaml' not found
2025-01-06 15:25:10 [ERROR] Required parameter 'learning_rate' missing
2025-01-06 15:25:10 [ERROR] Invalid value for 'batch_size': must be positive integer
2025-01-06 15:25:10 [FATAL] Cannot proceed with training due to configuration errors
Traceback (most recent call last):
  File "train_model.py", line 45, in load_config
    config = yaml.load(config_file)
FileNotFoundError: [Errno 2] No such file or directory: 'model_config.yaml'`,
    stdout: `Initializing model training...
Loading configuration from 'model_config.yaml'
Configuration loading failed.
Training aborted.`,
    command: 'python train_model.py --config model_config.yaml',
    taskType: 'Model Training'
  },
  parameters: {
    docs: {
      description: {
        story: 'Example of TaskOutputDisplay for a failed task showing both stdout and stderr output.'
      }
    }
  }
}

export const LongOutputExample: Story = {
  args: {
    output: `# ====================================
# Large Dataset Analysis Output
# ====================================
# Processing 50,000 records for comprehensive analysis

dataset_info:
  total_records: 50000
  valid_records: 48756
  invalid_records: 1244
  processing_time: "45.7s"
  
column_analysis:
  name:
    unique_values: 45890
    missing_values: 234
    data_type: "string"
  age:
    min_value: 18
    max_value: 95
    mean: 42.6
    median: 41
    missing_values: 78
  location:
    unique_values: 2847
    top_locations: 
      - "New York": 4520
      - "Los Angeles": 3890
      - "Chicago": 3120
    missing_values: 445
  score:
    min_value: 0.0
    max_value: 100.0
    mean: 67.8
    median: 69.2
    std_deviation: 18.4
    missing_values: 0

statistical_summary:
  correlation_matrix:
    age_score: 0.23
    location_score: 0.15
    name_length_score: -0.08
  outliers_detected: 892
  data_quality_score: 0.89
  
recommendations:
  - "Remove 1,244 invalid records before analysis"
  - "Consider imputing missing age values using median"
  - "Investigate 892 outliers in score distribution"
  - "Location data shows geographic bias toward urban areas"`,
    stdout: `Starting large dataset analysis...
Loading dataset: large_dataset.csv
Found 50,000 records
Validating data integrity...
- Found 1,244 invalid records
- Found 757 records with missing values
Processing data columns...
- name: 45,890 unique values (98% unique)
- age: Range 18-95, mean 42.6
- location: 2,847 unique locations
- score: Range 0-100, mean 67.8
Calculating correlations...
Detecting outliers using IQR method...
Found 892 potential outliers
Generating recommendations...
Analysis complete!
Results saved to output.yaml
Total processing time: 45.7 seconds`,
    attachedFiles: [
      'analysis/2025-01-06/large_dataset_analysis/output.yaml',
      'analysis/2025-01-06/large_dataset_analysis/correlation_matrix.csv',
      'analysis/2025-01-06/large_dataset_analysis/outliers_report.txt',
      'analysis/2025-01-06/large_dataset_analysis/charts/distribution_plot.png',
      'analysis/2025-01-06/large_dataset_analysis/charts/correlation_heatmap.png',
      'analysis/2025-01-06/large_dataset_analysis/summary_statistics.json'
    ],
    command: 'python analyze_large_dataset.py --input large_dataset.csv --output analysis_results.yaml --generate-charts',
    taskType: 'Large Dataset Analysis'
  },
  parameters: {
    docs: {
      description: {
        story: 'Example with longer content showing how the component handles scrollable content in expandable panels.'
      }
    }
  }
}
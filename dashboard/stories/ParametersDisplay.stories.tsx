import type { Meta, StoryObj } from '@storybook/react'
import { ParametersDisplay } from '@/components/ui/ParametersDisplay'
import type { ParameterDefinition, ParameterValues } from '@/types/parameters'

const meta = {
  title: 'Components/ParametersDisplay',
  component: ParametersDisplay,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ParametersDisplay>

export default meta
type Story = StoryObj<typeof meta>

const sampleParameters: ParameterDefinition[] = [
  {
    name: 'project_name',
    label: 'Project Name',
    type: 'text',
    required: true
  },
  {
    name: 'max_iterations',
    label: 'Maximum Iterations',
    type: 'number',
    required: true,
    min: 1,
    max: 100
  },
  {
    name: 'enable_debug',
    label: 'Enable Debug Mode',
    type: 'boolean',
    default: false
  },
  {
    name: 'environment',
    label: 'Environment',
    type: 'select',
    options: [
      { value: 'development', label: 'Development' },
      { value: 'staging', label: 'Staging' },
      { value: 'production', label: 'Production' }
    ]
  },
  {
    name: 'due_date',
    label: 'Due Date',
    type: 'date'
  }
]

const sampleValues: ParameterValues = {
  project_name: 'AI Analysis Pipeline',
  max_iterations: 25,
  enable_debug: true,
  environment: 'production',
  due_date: '2025-12-31'
}

export const Default: Story = {
  args: {
    parameters: sampleParameters,
    values: sampleValues,
    compact: false
  }
}

export const Compact: Story = {
  args: {
    parameters: sampleParameters,
    values: sampleValues,
    compact: true
  }
}

export const PartialValues: Story = {
  args: {
    parameters: sampleParameters,
    values: {
      project_name: 'Incomplete Project',
      max_iterations: 10,
      enable_debug: false
      // environment and due_date are missing
    },
    compact: false
  }
}

export const BooleanValues: Story = {
  args: {
    parameters: [
      {
        name: 'feature_a',
        label: 'Feature A',
        type: 'boolean'
      },
      {
        name: 'feature_b',
        label: 'Feature B',
        type: 'boolean'
      },
      {
        name: 'feature_c',
        label: 'Feature C',
        type: 'boolean'
      }
    ],
    values: {
      feature_a: true,
      feature_b: false,
      feature_c: true
    },
    compact: false
  }
}

export const SelectValues: Story = {
  args: {
    parameters: [
      {
        name: 'priority',
        label: 'Priority',
        type: 'select',
        options: [
          { value: 'low', label: 'Low Priority' },
          { value: 'medium', label: 'Medium Priority' },
          { value: 'high', label: 'High Priority' }
        ]
      },
      {
        name: 'status',
        label: 'Status',
        type: 'select',
        options: [
          { value: 'draft', label: 'Draft' },
          { value: 'review', label: 'In Review' },
          { value: 'approved', label: 'Approved' }
        ]
      }
    ],
    values: {
      priority: 'high',
      status: 'review'
    },
    compact: false
  }
}

export const CompactWithBooleans: Story = {
  args: {
    parameters: [
      {
        name: 'project',
        label: 'Project',
        type: 'text'
      },
      {
        name: 'iterations',
        label: 'Iterations',
        type: 'number'
      },
      {
        name: 'cache_enabled',
        label: 'Cache',
        type: 'boolean'
      },
      {
        name: 'parallel',
        label: 'Parallel',
        type: 'boolean'
      },
      {
        name: 'verbose',
        label: 'Verbose',
        type: 'boolean'
      }
    ],
    values: {
      project: 'ML Pipeline',
      iterations: 100,
      cache_enabled: true,
      parallel: true,
      verbose: false
    },
    compact: true
  }
}

export const Empty: Story = {
  args: {
    parameters: [],
    values: {},
    compact: false
  }
}

export const ProcedureExample: Story = {
  args: {
    parameters: [
      {
        name: 'scorecard_id',
        label: 'Scorecard',
        type: 'scorecard_select',
        required: true
      },
      {
        name: 'score_id',
        label: 'Score',
        type: 'score_select',
        required: true,
        depends_on: 'scorecard_id'
      },
      {
        name: 'score_version_id',
        label: 'Score Version',
        type: 'score_version_select',
        required: false,
        depends_on: 'score_id'
      },
      {
        name: 'max_depth',
        label: 'Max Depth',
        type: 'number',
        default: 5,
        min: 1,
        max: 20
      },
      {
        name: 'enable_caching',
        label: 'Enable Caching',
        type: 'boolean',
        default: true
      }
    ],
    values: {
      scorecard_id: 'scorecard-123',
      score_id: 'score-456',
      score_version_id: 'version-789',
      max_depth: 8,
      enable_caching: true
    },
    compact: false
  }
}

export const TableVariant: Story = {
  args: {
    parameters: sampleParameters,
    values: sampleValues,
    variant: 'table'
  }
}

export const TableVariantProcedure: Story = {
  args: {
    parameters: [
      {
        name: 'scorecard_id',
        label: 'Scorecard',
        type: 'scorecard_select',
        required: true
      },
      {
        name: 'score_id',
        label: 'Score',
        type: 'score_select',
        required: true,
        depends_on: 'scorecard_id'
      },
      {
        name: 'score_version_id',
        label: 'Score Version',
        type: 'score_version_select',
        required: false,
        depends_on: 'score_id'
      },
      {
        name: 'max_depth',
        label: 'Max Depth',
        type: 'number',
        default: 5,
        min: 1,
        max: 20
      },
      {
        name: 'enable_caching',
        label: 'Enable Caching',
        type: 'boolean',
        default: true
      },
      {
        name: 'timeout',
        label: 'Timeout (seconds)',
        type: 'number',
        default: 30
      },
      {
        name: 'retry_attempts',
        label: 'Retry Attempts',
        type: 'number',
        default: 3
      },
      {
        name: 'use_fallback',
        label: 'Use Fallback',
        type: 'boolean',
        default: false
      }
    ],
    values: {
      scorecard_id: 'Call Criteria',
      score_id: 'Empathy',
      score_version_id: 'v2.1.0',
      max_depth: 8,
      enable_caching: true,
      timeout: 60,
      retry_attempts: 5,
      use_fallback: true
    },
    variant: 'table'
  }
}

export const RequiredFields: Story = {
  args: {
    parameters: [
      {
        name: 'required_text',
        label: 'Required Text',
        type: 'text',
        required: true
      },
      {
        name: 'optional_text',
        label: 'Optional Text',
        type: 'text',
        required: false
      },
      {
        name: 'required_number',
        label: 'Required Number',
        type: 'number',
        required: true
      },
      {
        name: 'optional_number',
        label: 'Optional Number',
        type: 'number',
        required: false
      }
    ],
    values: {
      required_text: 'This is required',
      required_number: 42
      // Optional fields are not filled
    },
    compact: false
  }
}


import type { Meta, StoryObj } from '@storybook/react'
import { useState } from 'react'
import { ConfigurableParametersForm } from '@/components/ui/ConfigurableParametersForm'
import type { ParameterDefinition, ParameterValues } from '@/types/parameters'

const meta = {
  title: 'Components/ConfigurableParametersForm',
  component: ConfigurableParametersForm,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ConfigurableParametersForm>

export default meta
type Story = StoryObj<typeof meta>

// Wrapper component to manage state
function FormWrapper({ 
  parameters, 
  initialValues = {} 
}: { 
  parameters: ParameterDefinition[]
  initialValues?: ParameterValues
}) {
  const [values, setValues] = useState<ParameterValues>(initialValues)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const handleChange = (newValues: ParameterValues) => {
    setValues(newValues)
    
    // Simple validation
    const newErrors: Record<string, string> = {}
    parameters.forEach(param => {
      if (param.required && !newValues[param.name]) {
        newErrors[param.name] = `${param.label} is required`
      }
      if (param.type === 'number' && newValues[param.name] !== undefined) {
        const numValue = Number(newValues[param.name])
        if (param.min !== undefined && numValue < param.min) {
          newErrors[param.name] = `Minimum value is ${param.min}`
        }
        if (param.max !== undefined && numValue > param.max) {
          newErrors[param.name] = `Maximum value is ${param.max}`
        }
      }
    })
    setErrors(newErrors)
  }

  return (
    <div className="max-w-2xl">
      <ConfigurableParametersForm
        parameters={parameters}
        values={values}
        onChange={handleChange}
        errors={errors}
      />
      <div className="mt-4 p-4 bg-muted rounded-md">
        <h3 className="text-sm font-medium mb-2">Current Values:</h3>
        <pre className="text-xs">{JSON.stringify(values, null, 2)}</pre>
        {Object.keys(errors).length > 0 && (
          <>
            <h3 className="text-sm font-medium mb-2 mt-4 text-destructive">Validation Errors:</h3>
            <pre className="text-xs text-destructive">{JSON.stringify(errors, null, 2)}</pre>
          </>
        )}
      </div>
    </div>
  )
}

export const BasicTypes: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true,
        description: 'Enter the name of your project'
      },
      {
        name: 'max_iterations',
        label: 'Maximum Iterations',
        type: 'number',
        required: true,
        default: 10,
        min: 1,
        max: 100,
        description: 'Maximum number of iterations to run'
      },
      {
        name: 'enable_debug',
        label: 'Enable Debug Mode',
        type: 'boolean',
        default: false,
        description: 'Enable detailed logging'
      }
    ]

    return <FormWrapper parameters={parameters} initialValues={{ max_iterations: 10, enable_debug: false }} />
  }
}

export const WithSelect: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'environment',
        label: 'Environment',
        type: 'select',
        required: true,
        options: [
          { value: 'development', label: 'Development' },
          { value: 'staging', label: 'Staging' },
          { value: 'production', label: 'Production' }
        ],
        description: 'Select the deployment environment'
      },
      {
        name: 'log_level',
        label: 'Log Level',
        type: 'select',
        required: false,
        options: [
          { value: 'debug', label: 'Debug' },
          { value: 'info', label: 'Info' },
          { value: 'warn', label: 'Warning' },
          { value: 'error', label: 'Error' }
        ],
        default: 'info'
      }
    ]

    return <FormWrapper parameters={parameters} initialValues={{ log_level: 'info' }} />
  }
}

export const DependentFields: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'category',
        label: 'Category',
        type: 'select',
        required: true,
        options: [
          { value: 'product', label: 'Product' },
          { value: 'service', label: 'Service' }
        ],
        description: 'Select a category first'
      },
      {
        name: 'subcategory',
        label: 'Subcategory',
        type: 'select',
        required: true,
        depends_on: 'category',
        options: [
          { value: 'electronics', label: 'Electronics' },
          { value: 'clothing', label: 'Clothing' },
          { value: 'consulting', label: 'Consulting' },
          { value: 'support', label: 'Support' }
        ],
        description: 'This field is enabled after selecting a category'
      },
      {
        name: 'details',
        label: 'Details',
        type: 'text',
        required: false,
        depends_on: 'subcategory',
        description: 'This field is enabled after selecting a subcategory'
      }
    ]

    return (
      <div>
        <div className="mb-4 p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md">
          <p className="text-sm text-blue-900 dark:text-blue-100">
            <strong>Dependent Fields Demo:</strong> Select a category first, then the subcategory field will be enabled. 
            After selecting a subcategory, the details field will be enabled. 
            Changing the category will clear the dependent fields.
          </p>
        </div>
        <FormWrapper parameters={parameters} />
      </div>
    )
  }
}

export const AllTypes: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'title',
        label: 'Title',
        type: 'text',
        required: true,
        description: 'Enter a descriptive title'
      },
      {
        name: 'count',
        label: 'Count',
        type: 'number',
        required: true,
        min: 1,
        max: 10,
        default: 5
      },
      {
        name: 'active',
        label: 'Is Active',
        type: 'boolean',
        default: true
      },
      {
        name: 'priority',
        label: 'Priority',
        type: 'select',
        required: true,
        options: [
          { value: 'low', label: 'Low' },
          { value: 'medium', label: 'Medium' },
          { value: 'high', label: 'High' }
        ]
      },
      {
        name: 'due_date',
        label: 'Due Date',
        type: 'date',
        required: false
      }
    ]

    return <FormWrapper parameters={parameters} initialValues={{ count: 5, active: true }} />
  }
}

export const WithValidation: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: true,
        description: 'Username is required'
      },
      {
        name: 'age',
        label: 'Age',
        type: 'number',
        required: true,
        min: 18,
        max: 120,
        description: 'Age must be between 18 and 120'
      },
      {
        name: 'terms',
        label: 'Accept Terms',
        type: 'boolean',
        required: true,
        description: 'You must accept the terms'
      }
    ]

    return (
      <div>
        <div className="mb-4 p-4 bg-amber-50 dark:bg-amber-950 border border-amber-200 dark:border-amber-800 rounded-md">
          <p className="text-sm text-amber-900 dark:text-amber-100">
            <strong>Validation Demo:</strong> Try submitting with empty fields or invalid values to see validation errors.
          </p>
        </div>
        <FormWrapper parameters={parameters} />
      </div>
    )
  }
}

export const Empty: Story = {
  render: () => {
    return <FormWrapper parameters={[]} />
  }
}


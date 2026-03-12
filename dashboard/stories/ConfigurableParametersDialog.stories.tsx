import type { Meta, StoryObj } from '@storybook/react'
import { ConfigurableParametersDialog } from '@/components/ui/ConfigurableParametersDialog'
import { ParameterDefinition } from '@/types/parameters'
import { useState } from 'react'
import { Button } from '@/components/ui/button'

const meta: Meta<typeof ConfigurableParametersDialog> = {
  title: 'Components/ConfigurableParametersDialog',
  component: ConfigurableParametersDialog,
  parameters: {
    layout: 'centered',
    // Mock Amplify API calls for Storybook
    mockData: {
      scorecards: [
        { id: 'scorecard-1', name: 'Customer Support Quality', accountId: 'mock-account-1' },
        { id: 'scorecard-2', name: 'Sales Call Effectiveness', accountId: 'mock-account-1' },
        { id: 'scorecard-3', name: 'Product Feedback Analysis', accountId: 'mock-account-1' },
      ],
      scores: {
        'scorecard-1': [
          { id: 'score-1-1', name: 'Agent Empathy' },
          { id: 'score-1-2', name: 'Problem Resolution' },
          { id: 'score-1-3', name: 'Response Time' },
        ],
        'scorecard-2': [
          { id: 'score-2-1', name: 'Objection Handling' },
          { id: 'score-2-2', name: 'Value Proposition' },
        ],
        'scorecard-3': [
          { id: 'score-3-1', name: 'Feature Requests' },
          { id: 'score-3-2', name: 'Bug Reports' },
        ]
      },
      versions: [
        { id: 'version-1', createdAt: '2024-01-15T10:00:00Z', isFeatured: true },
        { id: 'version-2', createdAt: '2024-01-10T10:00:00Z', isFeatured: false },
        { id: 'version-3', createdAt: '2024-01-05T10:00:00Z', isFeatured: false },
      ]
    }
  },
  tags: ['autodocs'],
}

export default meta
type Story = StoryObj<typeof ConfigurableParametersDialog>

// Wrapper component to handle state
function DialogWrapper({ parameters, ...props }: any) {
  const [open, setOpen] = useState(false)
  const [lastSubmitted, setLastSubmitted] = useState<any>(null)

  return (
    <div>
      <Button onClick={() => setOpen(true)}>Open Dialog</Button>
      <ConfigurableParametersDialog
        open={open}
        onOpenChange={setOpen}
        parameters={parameters}
        onSubmit={(values) => {
          console.log('Submitted values:', values)
          setLastSubmitted(values)
        }}
        {...props}
      />
      {lastSubmitted && (
        <div className="mt-4 p-4 border rounded">
          <h3 className="font-bold mb-2">Last Submitted:</h3>
          <pre className="text-xs">{JSON.stringify(lastSubmitted, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}

export const BasicTextInputs: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'name',
        label: 'Name',
        type: 'text',
        required: true,
        placeholder: 'Enter your name',
      },
      {
        name: 'email',
        label: 'Email',
        type: 'text',
        required: true,
        placeholder: 'your.email@example.com',
        description: 'We will never share your email',
      },
      {
        name: 'bio',
        label: 'Biography',
        type: 'text',
        required: false,
        placeholder: 'Tell us about yourself',
      },
    ]

    return (
      <DialogWrapper
        title="User Information"
        description="Please provide your basic information"
        parameters={parameters}
        submitLabel="Save"
      />
    )
  },
}

export const NumberAndBoolean: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'age',
        label: 'Age',
        type: 'number',
        required: true,
        min: 0,
        max: 150,
        default: 25,
      },
      {
        name: 'quantity',
        label: 'Quantity',
        type: 'number',
        required: true,
        min: 1,
        max: 100,
        description: 'How many items do you want?',
      },
      {
        name: 'agree',
        label: 'I agree to the terms and conditions',
        type: 'boolean',
        required: true,
      },
      {
        name: 'newsletter',
        label: 'Subscribe to newsletter',
        type: 'boolean',
        default: false,
      },
    ]

    return (
      <DialogWrapper
        title="Configuration"
        description="Set your preferences"
        parameters={parameters}
      />
    )
  },
}

export const SelectOptions: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'country',
        label: 'Country',
        type: 'select',
        required: true,
        options: [
          { value: 'us', label: 'United States' },
          { value: 'uk', label: 'United Kingdom' },
          { value: 'ca', label: 'Canada' },
          { value: 'au', label: 'Australia' },
        ],
      },
      {
        name: 'language',
        label: 'Preferred Language',
        type: 'select',
        required: false,
        options: [
          { value: 'en', label: 'English' },
          { value: 'es', label: 'Spanish' },
          { value: 'fr', label: 'French' },
          { value: 'de', label: 'German' },
        ],
        default: 'en',
      },
    ]

    return (
      <DialogWrapper
        title="Localization Settings"
        parameters={parameters}
      />
    )
  },
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
          { value: 'electronics', label: 'Electronics' },
          { value: 'clothing', label: 'Clothing' },
          { value: 'books', label: 'Books' },
        ],
        description: 'Select a category first',
      },
      {
        name: 'subcategory',
        label: 'Subcategory',
        type: 'select',
        required: true,
        depends_on: 'category',
        options: [
          { value: 'laptop', label: 'Laptops' },
          { value: 'phone', label: 'Phones' },
          { value: 'tablet', label: 'Tablets' },
        ],
        description: 'This field is disabled until you select a category (note: options would normally filter based on category)',
      },
      {
        name: 'brand',
        label: 'Brand',
        type: 'select',
        required: false,
        depends_on: 'subcategory',
        options: [
          { value: 'apple', label: 'Apple' },
          { value: 'samsung', label: 'Samsung' },
          { value: 'dell', label: 'Dell' },
        ],
        description: 'This field is disabled until you select a subcategory',
      },
      {
        name: 'quantity',
        label: 'Quantity',
        type: 'number',
        required: true,
        default: 1,
        min: 1,
        max: 100,
      },
    ]

    return (
      <div className="space-y-4">
        <div className="p-4 bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 rounded-md">
          <h3 className="font-semibold text-blue-900 dark:text-blue-100 mb-2">📝 Dependent Fields Demo</h3>
          <p className="text-sm text-blue-800 dark:text-blue-200">
            This demonstrates <strong>dependent field behavior</strong>:
          </p>
          <ul className="text-sm text-blue-800 dark:text-blue-200 list-disc list-inside mt-2 space-y-1">
            <li><strong>Subcategory</strong> field is disabled until you select a <strong>Category</strong></li>
            <li><strong>Brand</strong> field is disabled until you select a <strong>Subcategory</strong></li>
            <li>Changing a parent field automatically clears its dependent children</li>
          </ul>
          <p className="text-xs text-blue-700 dark:text-blue-300 mt-2 italic">
            Try selecting Category → Subcategory → Brand to see the cascade. Change Category and watch Subcategory/Brand reset!
          </p>
        </div>
        <DialogWrapper
          title="Product Configuration"
          description="Select options - notice how fields become enabled as you fill in their dependencies"
          parameters={parameters}
          submitLabel="Add to Cart"
        />
      </div>
    )
  },
}

export const MixedTypes: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'project_name',
        label: 'Project Name',
        type: 'text',
        required: true,
        placeholder: 'My Awesome Project',
      },
      {
        name: 'environment',
        label: 'Environment',
        type: 'select',
        required: true,
        options: [
          { value: 'dev', label: 'Development' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
        ],
        default: 'dev',
      },
      {
        name: 'replicas',
        label: 'Number of Replicas',
        type: 'number',
        required: true,
        min: 1,
        max: 10,
        default: 3,
        description: 'How many instances to deploy',
      },
      {
        name: 'auto_scaling',
        label: 'Enable Auto Scaling',
        type: 'boolean',
        default: true,
      },
      {
        name: 'scorecard_id',
        label: 'Scorecard',
        type: 'scorecard_select',
        required: false,
        description: 'Optional scorecard association',
      },
    ]

    return (
      <DialogWrapper
        title="Deploy Configuration"
        description="Configure your deployment settings"
        parameters={parameters}
        submitLabel="Deploy"
        cancelLabel="Cancel"
      />
    )
  },
}

export const ValidationExample: Story = {
  render: () => {
    const parameters: ParameterDefinition[] = [
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        required: true,
        placeholder: 'Enter username',
      },
      {
        name: 'password',
        label: 'Password',
        type: 'text',
        required: true,
        placeholder: 'Enter password',
      },
      {
        name: 'age',
        label: 'Age',
        type: 'number',
        required: true,
        min: 18,
        max: 120,
        description: 'Must be 18 or older',
      },
      {
        name: 'terms',
        label: 'I accept the terms and conditions',
        type: 'boolean',
        required: true,
      },
    ]

    return (
      <DialogWrapper
        title="Sign Up"
        description="Create your account (try submitting without filling required fields)"
        parameters={parameters}
        submitLabel="Create Account"
      />
    )
  },
}




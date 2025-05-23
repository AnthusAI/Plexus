import React, { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import { MetadataEditor, MetadataEditorProps } from '../../components/ui/metadata-editor'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'

const meta = {
  title: 'Components/MetadataEditor',
  component: MetadataEditor,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'A reusable component for editing key-value metadata pairs with validation support.'
      }
    }
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-2xl">
        <div className="bg-card rounded-xl p-6">
          <Story />
        </div>
      </div>
    ),
  ],
  argTypes: {
    value: {
      control: 'object',
      description: 'Initial metadata entries as object or array'
    },
    onChange: {
      action: 'onChange',
      description: 'Callback when metadata changes'
    },
    keyPlaceholder: {
      control: 'text',
      description: 'Placeholder text for key inputs'
    },
    valuePlaceholder: {
      control: 'text',
      description: 'Placeholder text for value inputs'
    },
    disabled: {
      control: 'boolean',
      description: 'Whether the component is disabled'
    },
    showAddButton: {
      control: 'boolean',
      description: 'Whether to show the add entry button'
    },
    maxEntries: {
      control: 'number',
      description: 'Maximum number of entries allowed'
    }
  }
} satisfies Meta<typeof MetadataEditor>

export default meta
type Story = StoryObj<typeof MetadataEditor>

// Interactive wrapper component for stories that need state management
interface InteractiveWrapperProps extends Omit<MetadataEditorProps, 'value' | 'onChange'> {
  initialValue?: Record<string, string>
  title?: string
}

const InteractiveWrapper = ({ initialValue, title, ...props }: InteractiveWrapperProps) => {
  const [value, setValue] = useState(initialValue || {})
  
  return (
    <div className="space-y-4">
      {title && (
        <h3 className="text-lg font-semibold text-card-foreground">{title}</h3>
      )}
      <MetadataEditor
        value={value}
        onChange={(newValue) => {
          setValue(newValue)
          action('onChange')(newValue)
        }}
        {...props}
      />
      <div className="mt-4 p-3 bg-muted rounded-md">
        <h4 className="text-sm font-medium mb-2">Current Value:</h4>
        <pre className="text-xs text-muted-foreground">
          {JSON.stringify(value, null, 2)}
        </pre>
      </div>
    </div>
  )
}

export const Default: Story = {
  render: () => <InteractiveWrapper 
    title="Default Metadata Editor"
    keyPlaceholder="Enter key"
    valuePlaceholder="Enter value"
  />
}

export const WithInitialData: Story = {
  render: () => <InteractiveWrapper 
    title="With Initial Data"
    initialValue={{
      'environment': 'production',
      'version': '1.0.0',
      'department': 'engineering'
    }}
  />
}

export const WithValidation: Story = {
  render: () => <InteractiveWrapper 
    title="With Validation Rules"
    initialValue={{
      'valid-key': 'valid value'
    }}
    validateKey={(key: string) => {
      if (key.includes(' ')) {
        return 'Keys cannot contain spaces'
      }
      if (key.length > 20) {
        return 'Keys must be 20 characters or less'
      }
      return null
    }}
    validateValue={(value: string) => {
      if (value.length > 100) {
        return 'Values must be 100 characters or less'
      }
      return null
    }}
  />
}

export const WithMaxEntries: Story = {
  render: () => <InteractiveWrapper 
    title="Limited to 3 Entries"
    maxEntries={3}
    initialValue={{
      'key1': 'value1',
      'key2': 'value2'
    }}
  />
}

export const Disabled: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-2xl">
        <div className="bg-card rounded-xl p-6">
          <h3 className="text-lg font-semibold text-card-foreground mb-4">Disabled State</h3>
          <Story />
        </div>
      </div>
    ),
  ],
  args: {
    value: {
      'readonly-key': 'readonly value',
      'another-key': 'another value'
    },
    disabled: true,
    onChange: action('onChange')
  }
}

export const CustomPlaceholders: Story = {
  render: () => <InteractiveWrapper 
    title="Custom Placeholders"
    keyPlaceholder="Property name"
    valuePlaceholder="Property value"
    initialValue={{
      'sample': 'data'
    }}
  />
}

export const NoAddButton: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-2xl">
        <div className="bg-card rounded-xl p-6">
          <h3 className="text-lg font-semibold text-card-foreground mb-4">No Add Button</h3>
          <Story />
        </div>
      </div>
    ),
  ],
  args: {
    value: {
      'fixed-key': 'fixed value'
    },
    showAddButton: false,
    onChange: action('onChange')
  }
}

export const Empty: Story = {
  render: () => <InteractiveWrapper 
    title="Empty State" 
    initialValue={{}} 
  />
}

// Showcase all states in one story
export const AllStates: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl">
        <Story />
      </div>
    ),
  ],
  render: () => (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <Card className="bg-card border-0 shadow-none">
        <CardHeader>
          <CardTitle>Default (Empty)</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor onChange={action('onChange-empty')} />
        </CardContent>
      </Card>
      
      <Card className="bg-card border-0 shadow-none">
        <CardHeader>
          <CardTitle>With Data</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor 
            value={{
              'environment': 'production',
              'version': '2.1.0'
            }}
            onChange={action('onChange-data')} 
          />
        </CardContent>
      </Card>
      
      <Card className="bg-card border-0 shadow-none">
        <CardHeader>
          <CardTitle>With Validation Errors</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor 
            value={{
              'invalid key': 'value with space in key',
              'valid-key': 'x'.repeat(150) // Too long
            }}
            validateKey={(key) => key.includes(' ') ? 'Keys cannot contain spaces' : null}
            validateValue={(value) => value.length > 100 ? 'Values must be 100 characters or less' : null}
            onChange={action('onChange-validation')} 
          />
        </CardContent>
      </Card>
      
      <Card className="bg-card border-0 shadow-none">
        <CardHeader>
          <CardTitle>Max Entries Reached</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor 
            value={{
              'key1': 'value1',
              'key2': 'value2',
              'key3': 'value3'
            }}
            maxEntries={3}
            onChange={action('onChange-max')} 
          />
        </CardContent>
      </Card>
      
      <Card className="bg-card border-0 shadow-none">
        <CardHeader>
          <CardTitle>Disabled</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor 
            value={{
              'readonly': 'cannot edit'
            }}
            disabled={true}
            onChange={action('onChange-disabled')} 
          />
        </CardContent>
      </Card>
    </div>
  )
}

// Real-world use case examples
export const ScorecardMetadata: Story = {
  render: () => <InteractiveWrapper 
    title="Scorecard Example Items Metadata"
    keyPlaceholder="Metadata key (e.g., source, category)"
    valuePlaceholder="Metadata value"
    initialValue={{
      'source': 'customer_feedback',
      'category': 'quality_assurance',
      'priority': 'high',
      'reviewer': 'john.doe@company.com'
    }}
    validateKey={(key: string) => {
      const validKeys = ['source', 'category', 'priority', 'reviewer', 'department', 'tags']
      if (!validKeys.includes(key) && key.trim()) {
        return `Key must be one of: ${validKeys.join(', ')}`
      }
      return null
    }}
  />
}

export const ItemMetadata: Story = {
  render: () => <InteractiveWrapper 
    title="Item Metadata"
    keyPlaceholder="Field name"
    valuePlaceholder="Field value"
    initialValue={{
      'call_duration': '180',
      'customer_id': 'CUST-12345',
      'agent_id': 'AGT-567',
      'resolution_type': 'first_contact'
    }}
    maxEntries={10}
    validateValue={(value: string) => {
      if (value.trim() === '') {
        return 'Value cannot be empty'
      }
      return null
    }}
  />
} 
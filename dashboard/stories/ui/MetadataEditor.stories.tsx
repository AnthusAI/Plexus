import React, { useState } from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import { MetadataEditor, MetadataEditorProps } from '../../components/ui/metadata-editor'
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card'

const meta = {
  title: 'General/UI/MetadataEditor',
  component: MetadataEditor,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'A reusable component for editing key-value metadata pairs with validation support. Supports complex values like objects and arrays in read-only mode.'
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
  initialValue?: Record<string, any>
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

export const WithComplexValues: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl">
        <div className="bg-card rounded-xl p-6">
          <Story />
        </div>
      </div>
    ),
  ],
  render: () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-card-foreground">Complex Values (Read-Only)</h3>
      <MetadataEditor
        value={{
          'simple_string': 'Hello world',
          'number_value': 42,
          'boolean_value': true,
          'object_config': {
            host: 'localhost',
            port: 3000,
            ssl: true,
            options: {
              timeout: 5000,
              retries: 3
            }
          },
          'array_data': ['item1', 'item2', 'item3'],
          'complex_array': [
            { id: 1, name: 'First item', active: true },
            { id: 2, name: 'Second item', active: false }
          ],
          'nested_object': {
            user: {
              id: 123,
              profile: {
                name: 'John Doe',
                email: 'john@example.com',
                preferences: {
                  theme: 'dark',
                  notifications: true
                }
              }
            }
          }
        }}
        disabled={true}
        onChange={action('onChange')}
      />
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Demonstrates how the component handles complex values like objects and arrays in read-only mode. Complex values are formatted as readable JSON.'
      }
    }
  }
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

// Mixed data types in read-only mode
export const MixedDataTypes: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-3xl">
        <div className="bg-card rounded-xl p-6">
          <Story />
        </div>
      </div>
    ),
  ],
  render: () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-card-foreground">Mixed Data Types (Read-Only)</h3>
      <MetadataEditor
        value={{
          'id': 12345,
          'active': true,
          'name': 'Sample Item',
          'tags': ['urgent', 'customer-facing', 'production'],
          'configuration': {
            'api_endpoint': 'https://api.example.com/v1',
            'timeout_ms': 5000,
            'retry_attempts': 3,
            'features': {
              'caching': true,
              'compression': false,
              'encryption': 'AES256'
            }
          },
          'metrics': {
            'requests_per_second': 150.75,
            'error_rate': 0.025,
            'uptime_percentage': 99.9
          },
          'null_value': null,
          'empty_string': '',
          'zero_value': 0,
          'false_value': false
        }}
        disabled={true}
        onChange={action('onChange')}
      />
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Shows how various data types are handled: strings, numbers, booleans, objects, arrays, null values, etc.'
      }
    }
  }
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
          <CardTitle>Complex Values</CardTitle>
        </CardHeader>
        <CardContent>
          <MetadataEditor 
            value={{
              'config': { host: 'localhost', port: 3000 },
              'tags': ['web', 'api']
            }}
            disabled={true}
            onChange={action('onChange-complex')} 
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

// Real-world example with complex API response metadata
export const APIResponseMetadata: Story = {
  decorators: [
    (Story) => (
      <div className="w-full max-w-4xl">
        <div className="bg-card rounded-xl p-6">
          <Story />
        </div>
      </div>
    ),
  ],
  render: () => (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold text-card-foreground">API Response Metadata (Read-Only)</h3>
      <MetadataEditor
        value={{
          'request_id': 'req_abc123',
          'timestamp': '2024-01-15T10:30:00Z',
          'response_time_ms': 245,
          'status_code': 200,
          'headers': {
            'content-type': 'application/json',
            'cache-control': 'no-cache',
            'x-ratelimit-remaining': 99
          },
          'pagination': {
            'page': 1,
            'per_page': 20,
            'total': 150,
            'total_pages': 8
          },
          'filters_applied': ['status:active', 'created_after:2024-01-01'],
          'user_context': {
            'user_id': 'user_456',
            'permissions': ['read', 'write'],
            'organization': 'acme-corp'
          }
        }}
        disabled={true}
        onChange={action('onChange')}
      />
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Example of how the component displays complex API response metadata with nested objects and arrays.'
      }
    }
  }
} 
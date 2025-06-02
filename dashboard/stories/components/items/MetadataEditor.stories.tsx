import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import React from 'react'
import { MetadataEditor } from '../../../components/items/MetadataEditor'

const meta: Meta<typeof MetadataEditor> = {
  title: 'Content/MetadataEditor',
  component: MetadataEditor,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A metadata editor component that supports both read-only and edit modes for managing key-value pairs.'
      }
    }
  },
  argTypes: {
    metadata: {
      control: { type: 'object' },
      description: 'Metadata as key-value pairs'
    },
    readOnly: {
      control: { type: 'boolean' },
      description: 'Whether the component is in read-only mode'
    },
    onChange: {
      action: 'changed',
      description: 'Callback when metadata changes'
    }
  }
}

export default meta
type Story = StoryObj<typeof MetadataEditor>

// Sample metadata for stories
const sampleMetadata = {
  'Call ID': 'CALL-2024-001',
  'Customer Type': 'Premium',
  'Department': 'Sales',
  'Priority': 'High',
  'Agent ID': 'AGT-456'
}

const complexMetadata = {
  'Transcript ID': 'TXN-789456123',
  'Call Date': '2024-01-15',
  'Call Duration': '00:12:45',
  'Customer Satisfaction': '4.5/5',
  'Resolution Status': 'Resolved',
  'Issue Category': 'Billing Inquiry',
  'Follow-up Required': 'No',
  'Language': 'English',
  'Channel': 'Phone',
  'Recording ID': 'REC-001122334'
}

const minimalMetadata = {
  'ID': '12345',
  'Status': 'Active'
}

// Read-only mode stories
export const ReadOnlyDefault: Story = {
  args: {
    metadata: sampleMetadata,
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view showing metadata as formatted key-value pairs. Perfect for display-only contexts like dashboards.'
      }
    }
  }
}

export const ReadOnlyComplex: Story = {
  args: {
    metadata: complexMetadata,
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view with more complex metadata showing how longer keys and values are displayed.'
      }
    }
  }
}

export const ReadOnlyMinimal: Story = {
  args: {
    metadata: minimalMetadata,
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view with minimal metadata showing the compact display for simple data.'
      }
    }
  }
}

export const ReadOnlyEmpty: Story = {
  args: {
    metadata: {},
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view when no metadata is available, showing the empty state.'
      }
    }
  }
}

// Edit mode stories
export const EditDefault: Story = {
  args: {
    metadata: sampleMetadata,
    readOnly: false,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode with existing metadata. Users can modify existing entries and add new ones.'
      }
    }
  }
}

export const EditEmpty: Story = {
  args: {
    metadata: {},
    readOnly: false,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode starting with no metadata. Shows the empty state with option to add entries.'
      }
    }
  }
}

export const EditWithValidation: Story = {
  render: (args) => {
    const [metadata, setMetadata] = React.useState(args.metadata)
    
    const handleChange = (newMetadata: Record<string, string>) => {
      setMetadata(newMetadata)
      action('metadata-changed')(newMetadata)
    }

    return (
      <div className="w-96">
        <MetadataEditor
          {...args}
          metadata={metadata}
          onChange={handleChange}
        />
        <div className="mt-4 p-4 bg-muted rounded">
          <h3 className="text-sm font-medium mb-2">Current Metadata:</h3>
          <pre className="text-xs">{JSON.stringify(metadata, null, 2)}</pre>
        </div>
      </div>
    )
  },
  args: {
    metadata: { 'Sample Key': 'Sample Value' },
    readOnly: false,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive edit mode showing real-time validation. Try adding duplicate keys to see validation in action.'
      }
    }
  }
}

// Responsive stories
export const ResponsiveEdit: Story = {
  render: (args) => (
    <div className="w-full max-w-lg">
      <MetadataEditor {...args} />
    </div>
  ),
  args: {
    metadata: complexMetadata,
    readOnly: false,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode in a responsive container showing how the component adapts to different widths.'
      }
    }
  }
}

export const ResponsiveReadOnly: Story = {
  render: (args) => (
    <div className="w-full max-w-lg">
      <MetadataEditor {...args} />
    </div>
  ),
  args: {
    metadata: complexMetadata,
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only mode in a responsive container showing how the component adapts to different widths.'
      }
    }
  }
}

// Usage scenarios
export const InItemCard: Story = {
  render: (args) => (
    <div className="bg-card rounded-lg p-4 border max-w-md">
      <h2 className="text-lg font-semibold mb-4">Item Details</h2>
      <MetadataEditor {...args} />
    </div>
  ),
  args: {
    metadata: sampleMetadata,
    readOnly: true,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'How the MetadataEditor appears when used within an ItemCard component context.'
      }
    }
  }
}

export const InEditableForm: Story = {
  render: (args) => (
    <div className="bg-card rounded-lg p-4 border max-w-md space-y-4">
      <h2 className="text-lg font-semibold">Edit Item</h2>
      <div>
        <label className="text-sm font-medium">External ID</label>
        <input className="w-full mt-1 p-2 border rounded" defaultValue="ITEM-001" />
      </div>
      <div>
        <label className="text-sm font-medium">Description</label>
        <input className="w-full mt-1 p-2 border rounded" defaultValue="Sample item description" />
      </div>
      <MetadataEditor {...args} />
    </div>
  ),
  args: {
    metadata: { 'Priority': 'High', 'Category': 'Support' },
    readOnly: false,
    onChange: action('metadata-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'How the MetadataEditor appears when used within a larger editable form context.'
      }
    }
  }
} 
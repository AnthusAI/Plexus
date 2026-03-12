import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import React from 'react'
import { FileAttachments } from '../../../components/items/FileAttachments'

const meta: Meta<typeof FileAttachments> = {
  title: 'Content/FileAttachments',
  component: FileAttachments,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A file attachments component that supports both read-only and edit modes for managing file references and uploads. Now includes preview functionality for Parquet files and other text-based files.'
      }
    }
  },
  argTypes: {
    attachedFiles: {
      control: { type: 'object' },
      description: 'Array of file paths or URLs'
    },
    readOnly: {
      control: { type: 'boolean' },
      description: 'Whether the component is in read-only mode'
    },
    onChange: {
      action: 'changed',
      description: 'Callback when file list changes'
    },
    onUpload: {
      action: 'uploaded',
      description: 'Callback for file upload'
    },
    maxFiles: {
      control: { type: 'number' },
      description: 'Maximum number of files allowed'
    },
    allowedTypes: {
      control: { type: 'object' },
      description: 'Array of allowed MIME types'
    }
  }
}

export default meta
type Story = StoryObj<typeof FileAttachments>

// Sample files including Parquet and other viewable types
const sampleFiles = [
  '/uploads/document.pdf',
  'https://example.com/external-file.txt',
  'datasources/account-123/datasource-456/sample-data.parquet',
  'datasources/account-123/datasource-456/config.yaml',
  'datasources/account-123/datasource-456/results.json'
]

const sampleFilesWithParquet = [
  'datasources/account-123/datasource-456/customer-data.parquet',
  'datasources/account-123/datasource-456/sales-metrics.parquet',
  'datasources/account-123/datasource-456/configuration.yaml',
  'datasources/account-123/datasource-456/metadata.json'
]

const documentFiles = [
  'https://storage.company.com/contracts/agreement-2024.pdf',
  'https://storage.company.com/invoices/inv-12345.pdf',
  '/local/documents/meeting-notes.docx',
  '/local/documents/presentation.pptx'
]

const mediaFiles = [
  'https://cdn.example.com/calls/recording-001.wav',
  'https://cdn.example.com/video/screen-share.mp4',
  '/uploads/audio/interview.mp3'
]

const mixedFiles = [
  'https://api.example.com/files/data.json',
  '/uploads/screenshots/error.png',
  'https://storage.company.com/logs/system.log',
  '/local/files/backup.zip',
  'https://example.com/images/diagram.svg'
]

// Mock upload function
const mockUpload = async (file: File): Promise<string> => {
  // Simulate upload delay
  await new Promise(resolve => setTimeout(resolve, 1000))
  return Promise.resolve(`/uploads/${file.name}`)
}

// Read-only mode stories
export const ReadOnlyDefault: Story = {
  args: {
    attachedFiles: sampleFiles,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view showing file attachments with clickable links for URLs and view buttons for supported file types (Parquet, YAML, JSON, etc.).'
      }
    }
  }
}

export const ReadOnlyWithParquetFiles: Story = {
  args: {
    attachedFiles: sampleFilesWithParquet,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view specifically showing Parquet files and other data files with preview capabilities. Click the eye icon to preview Parquet files.'
      }
    }
  }
}

export const ReadOnlyDocuments: Story = {
  args: {
    attachedFiles: documentFiles,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view with document files showing how different file types are displayed.'
      }
    }
  }
}

export const ReadOnlyMedia: Story = {
  args: {
    attachedFiles: mediaFiles,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view with media files showing audio and video file handling.'
      }
    }
  }
}

export const ReadOnlyEmpty: Story = {
  args: {
    attachedFiles: [],
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only view when no files are attached, showing the empty state.'
      }
    }
  }
}

// Edit mode stories
export const EditDefault: Story = {
  args: {
    attachedFiles: sampleFiles,
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode with existing files. Users can modify paths, remove files, upload new ones, and preview supported file types.'
      }
    }
  }
}

export const EditWithParquetFiles: Story = {
  args: {
    attachedFiles: sampleFilesWithParquet,
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode showing Parquet files and other data files. Demonstrates the view functionality alongside edit capabilities.'
      }
    }
  }
}

export const EditEmpty: Story = {
  args: {
    attachedFiles: [],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode starting with no files. Shows the empty state with option to add files.'
      }
    }
  }
}

export const EditWithFileTypeRestrictions: Story = {
  args: {
    attachedFiles: ['datasources/account-123/datasource-456/data.parquet'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload,
    allowedTypes: ['.parquet', '.csv', '.json'],
    maxFiles: 3
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode with file type restrictions. Only allows specific file types to be uploaded.'
      }
    }
  }
}

// Loading states
export const EditWithUploadInProgress: Story = {
  args: {
    attachedFiles: ['/uploads/document.pdf'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: async (file: File) => {
      // Simulate a longer upload
      await new Promise(resolve => setTimeout(resolve, 3000))
      return `/uploads/${file.name}`
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode showing upload progress state. Upload a file to see the loading indicator.'
      }
    }
  }
}

// Error states
export const EditWithUploadError: Story = {
  args: {
    attachedFiles: [],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: async (file: File) => {
      // Simulate upload failure
      await new Promise(resolve => setTimeout(resolve, 1000))
      throw new Error('Upload failed: Network error')
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode demonstrating upload error handling. Try uploading a file to see the error state.'
      }
    }
  }
}

// Upload scenarios
export const UploadProgress: Story = {
  render: (args) => {
    const [files, setFiles] = React.useState(args.attachedFiles)
    
    const slowUpload = async (file: File): Promise<string> => {
      // Simulate slower upload for demo
      await new Promise(resolve => setTimeout(resolve, 5000))
      return `https://storage.example.com/uploads/${file.name}`
    }
    
    const handleChange = (newFiles: string[]) => {
      setFiles(newFiles)
      action('files-changed')(newFiles)
    }

    return (
      <div className="w-96">
        <FileAttachments
          {...args}
          attachedFiles={files}
          onChange={handleChange}
          onUpload={slowUpload}
        />
      </div>
    )
  },
  args: {
    attachedFiles: [],
    readOnly: false,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Upload with progress indication. Upload a file to see the loading state in action.'
      }
    }
  }
}

export const UploadErrors: Story = {
  render: (args) => {
    const [files, setFiles] = React.useState(args.attachedFiles)
    
    const failingUpload = async (file: File): Promise<string> => {
      await new Promise(resolve => setTimeout(resolve, 1000))
      // Always fail for demo
      throw new Error('Server temporarily unavailable')
    }
    
    const handleChange = (newFiles: string[]) => {
      setFiles(newFiles)
      action('files-changed')(newFiles)
    }

    return (
      <div className="w-96">
        <FileAttachments
          {...args}
          attachedFiles={files}
          onChange={handleChange}
          onUpload={failingUpload}
        />
      </div>
    )
  },
  args: {
    attachedFiles: [],
    readOnly: false,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'Upload error handling. Upload a file to see error states and user feedback.'
      }
    }
  }
}

// Configuration stories
export const LimitedFiles: Story = {
  args: {
    attachedFiles: ['file1.txt', 'file2.pdf'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload,
    maxFiles: 3
  },
  parameters: {
    docs: {
      description: {
        story: 'File list with maximum limit. Add button disappears when limit is reached.'
      }
    }
  }
}

export const RestrictedTypes: Story = {
  args: {
    attachedFiles: [],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload,
    allowedTypes: ['application/pdf', 'text/plain', 'image/png', 'image/jpeg']
  },
  parameters: {
    docs: {
      description: {
        story: 'File attachments with type restrictions. Only specific file types can be uploaded.'
      }
    }
  }
}

// Responsive stories
export const ResponsiveEdit: Story = {
  render: (args) => (
    <div className="w-full max-w-lg">
      <FileAttachments {...args} />
    </div>
  ),
  args: {
    attachedFiles: mixedFiles,
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
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
      <FileAttachments {...args} />
    </div>
  ),
  args: {
    attachedFiles: mixedFiles,
    readOnly: true,
    onChange: action('files-changed')
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
      <FileAttachments {...args} />
    </div>
  ),
  args: {
    attachedFiles: sampleFilesWithParquet,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'How the FileAttachments component appears when used within an ItemCard component context, showing Parquet files with preview capabilities.'
      }
    }
  }
}

export const InEditableForm: Story = {
  render: (args) => (
    <div className="bg-card rounded-lg p-4 border max-w-md space-y-4">
      <h2 className="text-lg font-semibold">Edit Data Source</h2>
      <div>
        <label className="text-sm font-medium">Name</label>
        <input className="w-full mt-1 p-2 border rounded" defaultValue="Customer Analytics Dataset" />
      </div>
      <div>
        <label className="text-sm font-medium">Description</label>
        <textarea className="w-full mt-1 p-2 border rounded" defaultValue="Customer behavior analysis data in Parquet format" />
      </div>
      <FileAttachments {...args} />
    </div>
  ),
  args: {
    attachedFiles: ['datasources/account-123/customer-analytics/data.parquet'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'How the FileAttachments component appears when used within a data source editing form, showing Parquet file management capabilities.'
      }
    }
  }
}

export const InDataSourceDashboard: Story = {
  render: (args) => (
    <div className="bg-background rounded-lg p-6 border max-w-2xl space-y-6">
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Sales Analytics Data Source</h2>
        <p className="text-muted-foreground">Customer transaction data for Q4 2024 analysis</p>
      </div>
      
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium text-muted-foreground">Configuration</label>
          <div className="mt-2 p-3 bg-muted/50 rounded-md font-mono text-sm">
            class: CallCriteriaDBCache<br/>
            queries: [...]<br/>
            balance: true
          </div>
        </div>
        
        <FileAttachments {...args} />
      </div>
    </div>
  ),
  args: {
    attachedFiles: [
      'datasources/account-123/sales-analytics/transactions-q4.parquet',
      'datasources/account-123/sales-analytics/customer-segments.parquet',
      'datasources/account-123/sales-analytics/schema.json',
      'datasources/account-123/sales-analytics/config.yaml'
    ],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'FileAttachments component as it appears in the data source dashboard, showing multiple Parquet files and configuration files with full preview capabilities.'
      }
    }
  }
} 
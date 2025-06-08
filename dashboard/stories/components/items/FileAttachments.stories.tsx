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
        component: 'A file attachments component that supports both read-only and edit modes for managing file references and uploads.'
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

// Sample file lists for stories
const sampleFiles = [
  'https://example.com/documents/report.pdf',
  'https://example.com/audio/call-recording.mp3',
  '/uploads/transcript.txt'
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

// Mock upload function for stories
const mockUpload = async (file: File): Promise<string> => {
  // Simulate upload delay
  await new Promise(resolve => setTimeout(resolve, 2000))
  
  // Simulate occasional failures for demo
  if (Math.random() < 0.1) {
    throw new Error('Upload failed: Network error')
  }
  
  // Return a mock URL
  return `https://storage.example.com/uploads/${file.name}`
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
        story: 'Read-only view showing file attachments with clickable links for URLs. Perfect for display-only contexts.'
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
        story: 'Edit mode with existing files. Users can modify paths, remove files, and upload new ones.'
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

export const EditWithoutUpload: Story = {
  args: {
    attachedFiles: ['/local/file1.txt', '/local/file2.pdf'],
    readOnly: false,
    onChange: action('files-changed')
    // No onUpload provided - shows manual path entry only
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode without upload functionality. Users can only manually enter file paths.'
      }
    }
  }
}

export const EditWithUploadAndValidation: Story = {
  render: (args) => {
    const [files, setFiles] = React.useState(args.attachedFiles)
    
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
        />
        <div className="mt-4 p-4 bg-muted rounded">
          <h3 className="text-sm font-medium mb-2">Current Files:</h3>
          <pre className="text-xs">{JSON.stringify(files, null, 2)}</pre>
        </div>
      </div>
    )
  },
  args: {
    attachedFiles: ['https://example.com/sample.pdf'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload,
    maxFiles: 3,
    allowedTypes: ['application/pdf', 'text/plain', 'image/*']
  },
  parameters: {
    docs: {
      description: {
        story: 'Interactive edit mode with file type restrictions and upload limits. Try uploading different file types.'
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
    attachedFiles: sampleFiles,
    readOnly: true,
    onChange: action('files-changed')
  },
  parameters: {
    docs: {
      description: {
        story: 'How the FileAttachments component appears when used within an ItemCard component context.'
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
        <textarea className="w-full mt-1 p-2 border rounded" defaultValue="Sample item description" />
      </div>
      <FileAttachments {...args} />
    </div>
  ),
  args: {
    attachedFiles: ['/uploads/document.pdf'],
    readOnly: false,
    onChange: action('files-changed'),
    onUpload: mockUpload
  },
  parameters: {
    docs: {
      description: {
        story: 'How the FileAttachments component appears when used within a larger editable form context.'
      }
    }
  }
} 
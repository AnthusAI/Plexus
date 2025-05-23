import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import React from 'react'
import { ItemComponent, type ItemData } from '../../components/ui/item-component'

const meta: Meta<typeof ItemComponent> = {
  title: 'UI/ItemComponent',
  component: ItemComponent,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'A reusable component for displaying and editing items. Supports both grid and detail variants with full CRUD operations.'
      }
    }
  },
  argTypes: {
    variant: {
      control: { type: 'radio' },
      options: ['grid', 'detail'],
      description: 'Display variant'
    },
    isSelected: {
      control: { type: 'boolean' },
      description: 'Whether the item is selected (grid variant only)'
    },
    isFullWidth: {
      control: { type: 'boolean' },
      description: 'Whether the component is in full width mode'
    },
    readOnly: {
      control: { type: 'boolean' },
      description: 'Whether the component is in read-only mode'
    }
  }
}

export default meta
type Story = StoryObj<typeof ItemComponent>

// Sample item data
const sampleItem: ItemData = {
  id: 'item-123',
  externalId: 'CALL-2024-001',
  description: 'Customer support call regarding billing inquiry',
  text: 'Customer called about a discrepancy in their monthly bill. They noticed an extra charge of $25.99 that they didn\'t recognize. After reviewing their account, it was determined that this was a legitimate service fee for premium support.',
  metadata: {
    'call_duration': '8:45',
    'customer_tier': 'premium',
    'issue_category': 'billing',
    'resolution_status': 'resolved'
  },
  attachedFiles: [
    '/recordings/call-2024-001.mp3',
    '/transcripts/call-2024-001.txt'
  ],
  accountId: 'acc-123',
  scorecardId: 'scorecard-456',
  isEvaluation: false,
  createdAt: '2024-01-15T10:30:00Z',
  updatedAt: '2024-01-15T11:15:00Z'
}

const minimalItem: ItemData = {
  id: 'item-456',
  externalId: 'SIMPLE-001',
  text: 'A minimal item with just basic content.'
}

const newItem: ItemData = {
  id: '',
  externalId: '',
  description: '',
  text: '',
  metadata: {},
  attachedFiles: []
}

const itemWithFiles: ItemData = {
  id: 'item-789',
  externalId: 'FILE-RICH-001',
  description: 'An item with multiple attached files',
  text: 'This item demonstrates how multiple file attachments are handled in the component.',
  attachedFiles: [
    '/documents/contract.pdf',
    '/images/screenshot.png',
    '/audio/recording.wav',
    '/data/analysis.xlsx'
  ],
  metadata: {
    'file_count': '4',
    'total_size': '25.4MB'
  }
}

const spanishCallItem: ItemData = {
  id: 'item-spanish-001',
  externalId: 'CALL-ES-2024-003',
  description: 'Spanish customer call - wrong number',
  text: `Customer: Hola, buenos días. Estoy buscando un lugar donde pueda comprar decoraciones para la quinceañera de mi sobrina.

Agent: Buenos días, señora. Lo siento mucho, pero usted ha llamado a una empresa de suministros de plomería.

Customer: Oh... lo siento.`,
  metadata: {
    'language': 'spanish',
    'call_duration': '0:32',
    'call_type': 'wrong_number',
    'resolution': 'disconnected'
  },
  attachedFiles: [
    '/recordings/call-es-2024-003.wav',
    '/transcripts/call-es-2024-003.txt'
  ],
  accountId: 'acc-123',
  scorecardId: 'scorecard-456',
  isEvaluation: false,
  createdAt: '2024-01-20T14:22:00Z',
  updatedAt: '2024-01-20T14:22:32Z'
}

// Grid variant stories
export const GridDefault: Story = {
  args: {
    item: sampleItem,
    variant: 'grid',
    onClick: action('item-clicked')
  },
  parameters: {
    docs: {
      description: {
        story: 'Default grid view showing item information in a compact card format.'
      }
    }
  }
}

export const GridSelected: Story = {
  args: {
    item: sampleItem,
    variant: 'grid',
    isSelected: true,
    onClick: action('item-clicked')
  },
  parameters: {
    docs: {
      description: {
        story: 'Grid view with the item in selected state, showing the selection ring.'
      }
    }
  }
}

export const GridMinimal: Story = {
  args: {
    item: minimalItem,
    variant: 'grid',
    onClick: action('item-clicked')
  },
  parameters: {
    docs: {
      description: {
        story: 'Grid view with minimal item data to test fallback displays.'
      }
    }
  }
}

// Detail variant stories
export const DetailDefault: Story = {
  args: {
    item: sampleItem,
    variant: 'detail',
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Default detail view showing full item editing interface.'
      }
    }
  }
}

export const DetailFullWidth: Story = {
  args: {
    item: sampleItem,
    variant: 'detail',
    isFullWidth: true,
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view in full width mode, showing expanded layout.'
      }
    }
  }
}

export const DetailReadOnly: Story = {
  args: {
    item: sampleItem,
    variant: 'detail',
    readOnly: true,
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth')
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view in read-only mode, showing all fields as disabled.'
      }
    }
  }
}

export const NewItem: Story = {
  args: {
    item: newItem,
    variant: 'detail',
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view for creating a new item with empty fields.'
      }
    }
  }
}

export const WithMetadata: Story = {
  args: {
    item: sampleItem,
    variant: 'detail',
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view highlighting the metadata editor functionality.'
      }
    }
  }
}

export const WithAttachedFiles: Story = {
  args: {
    item: itemWithFiles,
    variant: 'detail',
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view showing multiple attached files and file management.'
      }
    }
  }
}

export const SpanishCallExample: Story = {
  args: {
    item: spanishCallItem,
    variant: 'detail',
    onClose: action('close-clicked'),
    onToggleFullWidth: action('toggle-fullwidth'),
    onSave: async (item) => {
      action('save-item')(item)
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Example showing a Spanish language call transcript with metadata. Demonstrates how text content can cache transcript data that also exists as an attached file.'
      }
    }
  }
}

// Container story to show grid layout
export const GridLayout: Story = {
  render: () => (
    <div className="p-4">
      <h2 className="text-lg font-semibold mb-4">Items Grid Layout</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <ItemComponent
          item={sampleItem}
          variant="grid"
          onClick={action('item-1-clicked')}
        />
        <ItemComponent
          item={minimalItem}
          variant="grid"
          isSelected={true}
          onClick={action('item-2-clicked')}
        />
        <ItemComponent
          item={itemWithFiles}
          variant="grid"
          onClick={action('item-3-clicked')}
        />
        <ItemComponent
          item={{ ...sampleItem, id: 'item-4', externalId: 'CALL-2024-002' }}
          variant="grid"
          onClick={action('item-4-clicked')}
        />
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Example of multiple items in a grid layout, demonstrating typical usage in a list view.'
      }
    }
  }
}

// Container story to show split view (grid + detail)
export const SplitView: Story = {
  render: () => (
    <div className="h-screen flex">
      <div className="w-1/2 p-4 border-r">
        <h3 className="text-md font-medium mb-4">Items List</h3>
        <div className="space-y-4">
          <ItemComponent
            item={sampleItem}
            variant="grid"
            isSelected={true}
            onClick={action('item-selected')}
          />
          <ItemComponent
            item={minimalItem}
            variant="grid"
            onClick={action('item-selected')}
          />
          <ItemComponent
            item={itemWithFiles}
            variant="grid"
            onClick={action('item-selected')}
          />
        </div>
      </div>
      <div className="w-1/2">
        <ItemComponent
          item={sampleItem}
          variant="detail"
          onClose={action('close-detail')}
          onSave={async (item) => {
            action('save-item')(item)
          }}
        />
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Example of a split view with items list on the left and detail panel on the right, showing typical dashboard usage.'
      }
    }
  }
} 
import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { IdentifierDisplay, type IdentifierItem } from '../../components/ui/identifier-display';

const meta: Meta<typeof IdentifierDisplay> = {
  title: 'Content/IdentifierDisplay',
  component: IdentifierDisplay,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A component that displays identifiers with support for expandable multiple identifiers and external links. Accepts either an array of identifier objects or a JSON string for backward compatibility.',
      },
    },
  },
  argTypes: {
    externalId: {
      control: 'text',
      description: 'Simple external ID fallback when no complex identifiers are available',
    },
    identifiers: {
      control: 'object',
      description: 'Array of identifier objects or JSON string containing array of identifiers',
    },
    iconSize: {
      control: 'select',
      options: ['sm', 'md', 'lg'],
      description: 'Size of the ID card icon',
    },
    textSize: {
      control: 'select',
      options: ['xs', 'sm', 'base'],
      description: 'Size of the text',
    },
    className: {
      control: 'text',
      description: 'Additional CSS classes',
    },
    displayMode: {
      control: 'select',
      options: ['full', 'compact'],
      description: 'Display mode: full shows all features (expand, copy buttons), compact shows only first identifier without interaction',
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

// Sample data using the standard pattern: form, report, session, ID
const sampleIdentifiers: IdentifierItem[] = [
  {
    name: 'form',
    value: '453460',
  },
  {
    name: 'report',
    value: '2090346',
  },
  {
    name: 'session',
    value: 'XCC18834SCRUFF',
  },
  {
    name: 'ID',
    value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
  }
];

// Simple external ID only
export const SimpleExternalId: Story = {
  args: {
    externalId: 'EXT-12345',
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// NEW: Single identifier using array interface
export const SingleIdentifierArray: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// NEW: Multiple identifiers using array interface
export const MultipleIdentifiersArray: Story = {
  args: {
    identifiers: sampleIdentifiers,
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// NEW: Compact mode - shows only icon and value (no labels)
export const CompactMode: Story = {
  args: {
    identifiers: sampleIdentifiers,
    iconSize: 'md',
    textSize: 'xs',
    displayMode: 'compact',
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact mode displays only the icon and value without labels, used in grid view cards.',
      },
    },
  },
};

// NEW: Comparison - Full vs Compact side by side
export const FullVsCompact: Story = {
  render: () => (
    <div className="space-y-4">
      <div>
        <h3 className="text-sm font-medium mb-2">Full Mode (Detail View)</h3>
        <IdentifierDisplay 
          identifiers={sampleIdentifiers}
          iconSize="md"
          textSize="xs"
          displayMode="full"
        />
      </div>
      <div>
        <h3 className="text-sm font-medium mb-2">Compact Mode (Grid View)</h3>
        <IdentifierDisplay 
          identifiers={sampleIdentifiers}
          iconSize="md"
          textSize="xs"
          displayMode="compact"
        />
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Side-by-side comparison of full mode (shows labels, expand/copy buttons) vs compact mode (icon + value only).',
      },
    },
  },
};

// NEW: Array interface with mixed URLs
export const MixedIdentifiersArray: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      },
      {
        name: 'report',
        value: '2090346',
        // No URL
      },
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
        url: 'https://example.com/sessions/XCC18834SCRUFF',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// LEGACY: Single complex identifier without URL (JSON string format)
export const SingleIdentifierLegacyJSON: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'form',
        id: '453460', // Note: uses 'id' field (legacy)
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Legacy JSON string format with "id" field for backward compatibility.',
      },
    },
  },
};

// LEGACY: Single complex identifier with URL (JSON string format)
export const SingleIdentifierWithLinkLegacyJSON: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'report',
        id: '2090346', // Note: uses 'id' field (legacy)
        url: 'https://example.com/reports/2090346',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Legacy JSON string format with URL support.',
      },
    },
  },
};

// Long identifier that gets truncated
export const LongIdentifier: Story = {
  args: {
    identifiers: [
      {
        name: 'ID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479-extra-long-suffix',
        url: 'https://example.com/items/f47ac10b-58cc-4372-a567-0e02b2c3d479-extra-long-suffix',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// LEGACY: Multiple identifiers (expandable) - JSON string format
export const MultipleIdentifiersLegacyJSON: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'form',
        id: '453460', // Note: uses 'id' field (legacy)
        url: 'https://example.com/forms/453460',
      },
      {
        name: 'report',
        id: '2090346', // Note: uses 'id' field (legacy)
        url: 'https://example.com/reports/2090346',
      },
      {
        name: 'session',
        id: 'XCC18834SCRUFF', // Note: uses 'id' field (legacy)
      },
      {
        name: 'ID',
        id: 'f47ac10b-58cc-4372-a567-0e02b2c3d479', // Note: uses 'id' field (legacy)
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Legacy JSON string format with multiple identifiers.',
      },
    },
  },
};

// Many identifiers for stress testing
export const ManyIdentifiers: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      },
      {
        name: 'report',
        value: '2090346',
        url: 'https://example.com/reports/2090346',
      },
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
      },
      {
        name: 'ID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
        url: 'https://example.com/items/f47ac10b-58cc-4372-a567-0e02b2c3d479',
      },
      {
        name: 'batch',
        value: 'BATCH-78901234',
      },
      {
        name: 'request',
        value: 'REQ-456789012',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Different icon sizes
export const LargeIcon: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      }
    ],
    iconSize: 'lg',
    textSize: 'base',
  },
};

export const MediumIcon: Story = {
  args: {
    identifiers: [
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
        url: 'https://example.com/sessions/XCC18834SCRUFF',
      }
    ],
    iconSize: 'md',
    textSize: 'sm',
  },
};

// Edge case: both externalId and identifiers provided (identifiers should take precedence)
export const BothExternalIdAndIdentifiers: Story = {
  args: {
    externalId: 'EXT-FALLBACK',
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Edge case: invalid JSON in identifiers (should fall back to externalId)
export const InvalidJSON: Story = {
  args: {
    externalId: 'EXT-FALLBACK',
    identifiers: 'invalid json string',
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Edge case: empty identifiers array (should fall back to externalId)
export const EmptyIdentifiers: Story = {
  args: {
    externalId: 'EXT-FALLBACK',
    identifiers: [],
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Edge case: no identifiers or externalId (should render nothing)
export const NoIdentifiers: Story = {
  args: {
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Test data exactly as specified by user
export const SpecificTestData: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
      },
      {
        name: 'report',
        value: '2090346',
      },
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
      },
      {
        name: 'ID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Test data with specific values including a long UUID to test truncation behavior.',
      },
    },
  },
};

// Test with extremely long UUID to stress test truncation
export const LongUUIDTest: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
      },
      {
        name: 'report',
        value: '2090346',
      },
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
      },
      {
        name: 'ID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479-extra-long-suffix',
      },
      {
        name: 'Very Long UUID',
        value: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee-with-additional-very-long-text',
        url: 'https://example.com/uuid/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee-with-additional-very-long-text',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Testing with very long UUIDs and identifiers to verify truncation and tooltip behavior.',
      },
    },
  },
};

// Test with just the UUID examples in different sizes
export const UUIDSizes: Story = {
  args: {
    identifiers: [
      {
        name: 'Standard UUID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479',
      },
      {
        name: 'Long UUID',
        value: 'f47ac10b-58cc-4372-a567-0e02b2c3d479-extended-identifier',
      }
    ],
    iconSize: 'md',
    textSize: 'sm',
  },
  parameters: {
    docs: {
      description: {
        story: 'Focus on UUID examples with medium sizing to better see the truncation behavior.',
      },
    },
  },
};

// Container with dark background to test contrast
export const OnDarkBackground: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      },
      {
        name: 'session',
        value: 'XCC18834SCRUFF',
      }
    ],
    iconSize: 'sm',
    textSize: 'xs',
  },
  decorators: [
    (Story) => (
      <div className="bg-slate-800 p-4 rounded">
        <Story />
      </div>
    ),
  ],
};

// NEW: Compact mode stories demonstrating grid view behavior
export const CompactModeSimple: Story = {
  args: {
    externalId: 'EXT-12345',
    displayMode: 'compact',
    iconSize: 'md',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact mode with simple external ID - no copy button for grid view.',
      },
    },
  },
};

export const CompactModeSingleIdentifier: Story = {
  args: {
    identifiers: [
      {
        name: 'form',
        value: '453460',
        url: 'https://example.com/forms/453460',
      }
    ],
    displayMode: 'compact',
    iconSize: 'md',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact mode with single identifier - no copy button, links still work.',
      },
    },
  },
};

export const CompactModeMultipleIdentifiers: Story = {
  args: {
    identifiers: sampleIdentifiers,
    displayMode: 'compact',
    iconSize: 'md',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Compact mode with multiple identifiers - only shows first one, no expand caret or copy button.',
      },
    },
  },
};

// Comparison: Full vs Compact modes side by side
export const FullModeComparison: Story = {
  args: {
    identifiers: sampleIdentifiers,
    displayMode: 'full',
    iconSize: 'md',
    textSize: 'xs',
  },
  parameters: {
    docs: {
      description: {
        story: 'Full mode (default) - shows expand caret and copy buttons for detail view.',
      },
    },
  },
};
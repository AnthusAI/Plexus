import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { IdentifierDisplay, type IdentifierItem } from '../../components/ui/identifier-display';

const meta: Meta<typeof IdentifierDisplay> = {
  title: 'UI/IdentifierDisplay',
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
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

// Sample data for new array-based interface
const sampleIdentifiers: IdentifierItem[] = [
  {
    name: 'Customer ID',
    value: 'CUST-789012',
    url: 'https://example.com/customers/789012',
  },
  {
    name: 'Order ID',
    value: 'ORD-345678',
    url: 'https://example.com/orders/345678',
  },
  {
    name: 'Transaction ID',
    value: 'TXN-901234',
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
        name: 'Customer ID',
        value: 'CUST-789012',
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

// NEW: Array interface with mixed URLs
export const MixedIdentifiersArray: Story = {
  args: {
    identifiers: [
      {
        name: 'Customer ID',
        value: 'CUST-123456',
        url: 'https://example.com/customers/123456',
      },
      {
        name: 'Internal ID',
        value: 'INT-789012',
        // No URL
      },
      {
        name: 'Reference',
        value: 'REF-345678',
        url: 'https://example.com/references/345678',
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
        name: 'Customer ID',
        id: 'CUST-789012', // Note: uses 'id' field (legacy)
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
        name: 'Ticket ID',
        id: 'TICK-456789', // Note: uses 'id' field (legacy)
        url: 'https://example.com/tickets/456789',
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
        name: 'Long ID',
        value: 'VERY-LONG-IDENTIFIER-THAT-EXCEEDS-FIFTEEN-CHARACTERS',
        url: 'https://example.com/items/VERY-LONG-IDENTIFIER-THAT-EXCEEDS-FIFTEEN-CHARACTERS',
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
        name: 'Customer ID',
        id: 'CUST-789012', // Note: uses 'id' field (legacy)
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        id: 'ORD-345678', // Note: uses 'id' field (legacy)
        url: 'https://example.com/orders/345678',
      },
      {
        name: 'Transaction ID',
        id: 'TXN-901234', // Note: uses 'id' field (legacy)
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
        name: 'Customer ID',
        value: 'CUST-789012',
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        value: 'ORD-345678',
        url: 'https://example.com/orders/345678',
      },
      {
        name: 'Transaction ID',
        value: 'TXN-901234',
      },
      {
        name: 'Session ID',
        value: 'SESS-567890',
        url: 'https://example.com/sessions/567890',
      },
      {
        name: 'Request ID',
        value: 'REQ-123456789',
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
        name: 'Item ID',
        value: 'ITEM-123456',
        url: 'https://example.com/items/123456',
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
        name: 'Item ID',
        value: 'ITEM-123456',
        url: 'https://example.com/items/123456',
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
        name: 'Primary ID',
        value: 'PRIM-123456',
        url: 'https://example.com/primary/123456',
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

// Container with dark background to test contrast
export const OnDarkBackground: Story = {
  args: {
    identifiers: [
      {
        name: 'Customer ID',
        value: 'CUST-789012',
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        value: 'ORD-345678',
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
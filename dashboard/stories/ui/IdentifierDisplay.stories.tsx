import type { Meta, StoryObj } from '@storybook/react';
import { IdentifierDisplay } from '@/components/ui/identifier-display';

const meta: Meta<typeof IdentifierDisplay> = {
  title: 'UI/IdentifierDisplay',
  component: IdentifierDisplay,
  parameters: {
    layout: 'centered',
    docs: {
      description: {
        component: 'A component that displays identifiers with support for expandable multiple identifiers and external links.',
      },
    },
  },
  argTypes: {
    externalId: {
      control: 'text',
      description: 'Simple external ID fallback when no complex identifiers are available',
    },
    identifiers: {
      control: 'text',
      description: 'JSON string containing array of identifier objects with name, id, and optional url',
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

// Simple external ID only
export const SimpleExternalId: Story = {
  args: {
    externalId: 'EXT-12345',
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Single complex identifier without URL
export const SingleIdentifier: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Customer ID',
        id: 'CUST-789012',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Single complex identifier with URL
export const SingleIdentifierWithLink: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Ticket ID',
        id: 'TICK-456789',
        url: 'https://example.com/tickets/456789',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Long identifier that gets truncated
export const LongIdentifier: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Long ID',
        id: 'VERY-LONG-IDENTIFIER-THAT-EXCEEDS-FIFTEEN-CHARACTERS',
        url: 'https://example.com/items/VERY-LONG-IDENTIFIER-THAT-EXCEEDS-FIFTEEN-CHARACTERS',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Multiple identifiers (expandable)
export const MultipleIdentifiers: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Customer ID',
        id: 'CUST-789012',
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        id: 'ORD-345678',
        url: 'https://example.com/orders/345678',
      },
      {
        name: 'Transaction ID',
        id: 'TXN-901234',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Many identifiers for stress testing
export const ManyIdentifiers: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Customer ID',
        id: 'CUST-789012',
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        id: 'ORD-345678',
        url: 'https://example.com/orders/345678',
      },
      {
        name: 'Transaction ID',
        id: 'TXN-901234',
      },
      {
        name: 'Session ID',
        id: 'SESS-567890',
        url: 'https://example.com/sessions/567890',
      },
      {
        name: 'Request ID',
        id: 'REQ-123456789',
      }
    ]),
    iconSize: 'sm',
    textSize: 'xs',
  },
};

// Different icon sizes
export const LargeIcon: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Item ID',
        id: 'ITEM-123456',
        url: 'https://example.com/items/123456',
      }
    ]),
    iconSize: 'lg',
    textSize: 'base',
  },
};

export const MediumIcon: Story = {
  args: {
    identifiers: JSON.stringify([
      {
        name: 'Item ID',
        id: 'ITEM-123456',
        url: 'https://example.com/items/123456',
      }
    ]),
    iconSize: 'md',
    textSize: 'sm',
  },
};

// Edge case: both externalId and identifiers provided (identifiers should take precedence)
export const BothExternalIdAndIdentifiers: Story = {
  args: {
    externalId: 'EXT-FALLBACK',
    identifiers: JSON.stringify([
      {
        name: 'Primary ID',
        id: 'PRIM-123456',
        url: 'https://example.com/primary/123456',
      }
    ]),
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
    identifiers: JSON.stringify([]),
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
    identifiers: JSON.stringify([
      {
        name: 'Customer ID',
        id: 'CUST-789012',
        url: 'https://example.com/customers/789012',
      },
      {
        name: 'Order ID',
        id: 'ORD-345678',
      }
    ]),
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
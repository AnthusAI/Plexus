import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import ItemCard, { ItemData } from '../components/items/ItemCard'

// Get the current date and time
const now = new Date();

// Function to create a date relative to now
const relativeDate = (days: number, hours: number, minutes: number) => {
  const date = new Date(now);
  date.setDate(date.getDate() - days);
  date.setHours(date.getHours() - hours, date.getMinutes() - minutes);
  return date.toISOString();
};

// Sample items using the new interface structure
const sampleItems: ItemData[] = [
  { 
    id: "item-001", 
    timestamp: relativeDate(0, 0, 5),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 12 }
    ],
    externalId: "CALL-20241201-001",
    createdAt: relativeDate(0, 0, 8), // Started 8 minutes ago
    updatedAt: relativeDate(0, 0, 5), // Finished 5 minutes ago (3 minute duration)
    isNew: true
  },
  { 
    id: "item-002", 
    timestamp: relativeDate(0, 0, 15),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 8 },
      { scorecardId: "sc-2", scorecardName: "Compliance", resultCount: 5 }
    ],
    externalId: "CALL-20241201-002",
    createdAt: relativeDate(0, 0, 22), // Started 22 minutes ago
    updatedAt: relativeDate(0, 0, 15), // Finished 15 minutes ago (7 minute duration)
  },
  { 
    id: "item-003", 
    timestamp: relativeDate(0, 0, 30),
    scorecards: [
      { scorecardId: "sc-3", scorecardName: "Sales Effectiveness", resultCount: 15 }
    ],
    externalId: "CALL-20241201-003",
    createdAt: relativeDate(0, 0, 32), // Started 32 minutes ago
    updatedAt: relativeDate(0, 0, 30), // Finished 30 minutes ago (2 minute duration)
  },
  { 
    id: "item-004", 
    timestamp: relativeDate(0, 1, 0),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 9 },
      { scorecardId: "sc-2", scorecardName: "Compliance", resultCount: 7 },
      { scorecardId: "sc-4", scorecardName: "Customer Satisfaction", resultCount: 4 }
    ],
    externalId: "CALL-20241201-004",
    createdAt: relativeDate(0, 1, 11), // Started 1 hour 11 minutes ago
    updatedAt: relativeDate(0, 1, 0), // Finished 1 hour ago (11 minute duration)
    isLoadingResults: true
  },
  { 
    id: "item-005", 
    timestamp: relativeDate(0, 1, 30),
    scorecards: [
      { scorecardId: "sc-2", scorecardName: "Compliance", resultCount: 11 },
      { scorecardId: "sc-5", scorecardName: "Technical Support", resultCount: 13 }
    ],
    externalId: "CALL-20241201-005",
    createdAt: relativeDate(0, 1, 34), // Started 1 hour 34 minutes ago
    updatedAt: relativeDate(0, 1, 30), // Finished 1 hour 30 minutes ago (4 minute duration)
  },
  { 
    id: "item-006", 
    timestamp: relativeDate(0, 2, 0),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 19 }
    ],
    externalId: "CALL-20241201-006",
    createdAt: relativeDate(0, 2, 9), // Started 2 hours 9 minutes ago
    updatedAt: relativeDate(0, 2, 0), // Finished 2 hours ago (9 minute duration)
  },
  { 
    id: "item-007", 
    timestamp: relativeDate(0, 4, 0),
    scorecards: [
      { scorecardId: "sc-6", scorecardName: "Emergency Response", resultCount: 16 }
    ],
    externalId: "EMRG-20241201-001",
    createdAt: relativeDate(0, 4, 0), // Started and finished at same time (no processing duration)
    updatedAt: relativeDate(0, 4, 0),
  },
  { 
    id: "item-008", 
    timestamp: relativeDate(0, 5, 0),
    scorecards: [
      { scorecardId: "sc-7", scorecardName: "Product Demo", resultCount: 17 },
      { scorecardId: "sc-8", scorecardName: "Lead Qualification", resultCount: 6 }
    ],
    externalId: "DEMO-20241201-001",
    createdAt: relativeDate(0, 5, 2), // Started 5 hours 2 minutes ago
    updatedAt: relativeDate(0, 5, 0), // Finished 5 hours ago (2 minute duration)
  },
  { 
    id: "item-009", 
    timestamp: relativeDate(0, 6, 0),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 13 },
      { scorecardId: "sc-9", scorecardName: "Escalation Handling", resultCount: 8 }
    ],
    externalId: "ESCL-20241201-001",
    createdAt: relativeDate(0, 6, 13), // Started 6 hours 13 minutes ago
    updatedAt: relativeDate(0, 6, 0), // Finished 6 hours ago (13 minute duration)
  },
  { 
    id: "item-010", 
    timestamp: relativeDate(1, 0, 0),
    scorecards: [
      { scorecardId: "sc-10", scorecardName: "Quick Support", resultCount: 3 }
    ],
    externalId: "QUICK-20241130-001",
    createdAt: relativeDate(1, 0, 1), // Started 1 day and 1 minute ago
    updatedAt: relativeDate(1, 0, 0), // Finished 1 day ago (45 second duration)
  },
  { 
    id: "item-011", 
    timestamp: relativeDate(1, 2, 0),
    scorecards: [
      { scorecardId: "sc-1", scorecardName: "Call Quality", resultCount: 18 },
      { scorecardId: "sc-2", scorecardName: "Compliance", resultCount: 12 },
      { scorecardId: "sc-11", scorecardName: "Training Session", resultCount: 22 }
    ],
    externalId: "TRAIN-20241130-001",
    createdAt: relativeDate(1, 2, 20), // Started 1 day 2 hours 20 minutes ago
    updatedAt: relativeDate(1, 2, 0), // Finished 1 day 2 hours ago (20 minute duration)
  },
  { 
    id: "item-012", 
    timestamp: relativeDate(1, 4, 0),
    scorecards: [
      { scorecardId: "sc-12", scorecardName: "Billing Inquiry", resultCount: 16 }
    ],
    externalId: "BILL-20241130-001",
    createdAt: relativeDate(1, 4, 5), // Started 1 day 4 hours 5 minutes ago
    updatedAt: relativeDate(1, 4, 0), // Finished 1 day 4 hours ago (5 minute duration)
  },
];

// Function to get badge variant based on status
const getBadgeVariant = (status: string) => {
  switch (status) {
    case 'New':
    case 'Scoring':
      return 'bg-neutral text-primary-foreground h-6';
    case 'Done':
      return 'bg-true text-primary-foreground h-6';
    case 'Error':
      return 'bg-destructive text-destructive-foreground dark:text-primary-foreground h-6';
    default:
      return 'bg-muted text-muted-foreground h-6';
  }
};

// Create a wrapper component for the detail variant to handle state
const ItemCardDetailWrapper = (args: any) => {
  const [isFullWidth, setIsFullWidth] = React.useState(false);
  
  return (
    <div className="h-[400px] w-full">
      <ItemCard
        {...args}
        isFullWidth={isFullWidth}
        onToggleFullWidth={() => setIsFullWidth(!isFullWidth)}
        getBadgeVariant={getBadgeVariant}
      />
    </div>
  );
};

const meta = {
  title: 'Scorecards/ItemCard',
  component: ItemCard,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  argTypes: {
    variant: {
      control: 'radio',
      options: ['grid', 'detail'],
    },
    item: {
      control: 'object',
    },
    isSelected: {
      control: 'boolean',
    },
  },
  args: {
    getBadgeVariant,
  },
} satisfies Meta<typeof ItemCard>;

export default meta;
type Story = StoryObj<typeof meta>;

// Grid variant stories showcasing different scenarios
export const GridSingleScorecard: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[0], // Single scorecard with duration
    isSelected: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Item card with a single scorecard, showing ID, timestamp, elapsed processing time, and result count.'
      }
    }
  }
};

export const GridMultipleScorecards: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[1], // Multiple scorecards
    isSelected: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Item card with multiple scorecards, showing combined result count and elapsed processing time.'
      }
    }
  }
};

export const GridNoDuration: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[6], // No elapsed time (same createdAt and updatedAt)
    isSelected: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Item card with no elapsed processing time - elapsed time display is hidden when timestamps are the same.'
      }
    }
  }
};

export const GridLoadingResults: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[3], // Loading state
    isSelected: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Item card showing loading state for results.'
      }
    }
  }
};

export const GridSelected: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[0],
    isSelected: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Selected item card with visual selection state.'
      }
    }
  }
};

// Detail variant stories
export const DetailSingleScorecard: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[0], // Single scorecard
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view of an item with a single scorecard.'
      }
    }
  }
};

export const DetailMultipleScorecards: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[10], // Multiple scorecards with long duration
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view of an item with multiple scorecards and extended breakdown.'
      }
    }
  }
};

export const DetailLoadingResults: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[3], // Loading state
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view showing loading state for results.'
      }
    }
  }
};

// Responsive grid layout story showing multiple cards with different characteristics
export const ResponsiveGrid: Story = {
  render: () => (
    <div className="w-full p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3">
        {sampleItems.slice(0, 8).map((item) => (
          <ItemCard
            key={item.id}
            variant="grid"
            item={item}
            isSelected={false}
            onClick={() => console.log(`Clicked item ${item.id}`)}
            getBadgeVariant={getBadgeVariant}
          />
        ))}
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[0], // Provide a default item (though not used in render)
    getBadgeVariant,
  },
  parameters: {
    docs: {
      description: {
        story: 'Responsive grid layout showing various item cards with different scorecard configurations, elapsed processing times, and states. Demonstrates how the cards adapt to different screen sizes and show various data combinations.'
      }
    }
  }
}; 
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

// Mock score results data for detailed view stories
const mockScoreResults = {
  'sc-1': {
    scorecardId: 'sc-1',
    scorecardName: 'Call Quality Assessment',
    scorecardExternalId: 'QUALITY-V2.1',
    scores: [
      {
        id: 'sr-001',
        value: 'PASS',
        explanation: 'Agent demonstrated excellent active listening throughout the call, acknowledging customer concerns and asking clarifying questions when needed. Professional tone maintained consistently.',
        confidence: 0.92,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-1',
        scoreId: 's-1',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-1',
          name: 'Call Quality Assessment',
          externalId: 'QUALITY-V2.1'
        },
        score: {
          id: 's-1',
          name: 'Active Listening',
          externalId: 'ACT-LISTEN-001'
        }
      },
      {
        id: 'sr-002',
        value: 'EXCELLENT',
        explanation: 'Customer was greeted warmly with proper introduction including agent name and company. Professional and friendly tone established from the beginning.',
        confidence: 0.98,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-1',
        scoreId: 's-2',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-1',
          name: 'Call Quality Assessment',
          externalId: 'QUALITY-V2.1'
        },
        score: {
          id: 's-2',
          name: 'Opening & Greeting',
          externalId: 'OPEN-GREET-001'
        }
      },
      {
        id: 'sr-003',
        value: 'NEEDS_IMPROVEMENT',
        explanation: 'While the agent provided accurate information, they missed an opportunity to offer additional services that could have benefited the customer. The resolution was effective but could have been more comprehensive.',
        confidence: 0.85,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-1',
        scoreId: 's-3',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-1',
          name: 'Call Quality Assessment',
          externalId: 'QUALITY-V2.1'
        },
        score: {
          id: 's-3',
          name: 'Problem Resolution',
          externalId: 'PROB-RESOL-001'
        }
      },
      {
        id: 'sr-004',
        value: 'PASS',
        explanation: 'Agent successfully verified customer identity using appropriate security questions and confirmed account details before proceeding with the inquiry.',
        confidence: 0.94,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-1',
        scoreId: 's-4',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-1',
          name: 'Call Quality Assessment',
          externalId: 'QUALITY-V2.1'
        },
        score: {
          id: 's-4',
          name: 'Security & Verification',
          externalId: 'SEC-VERIFY-001'
        }
      }
    ]
  },
  'sc-2': {
    scorecardId: 'sc-2',
    scorecardName: 'Compliance Checklist',
    scorecardExternalId: 'COMP-2024-Q4',
    scores: [
      {
        id: 'sr-005',
        value: 'COMPLIANT',
        explanation: 'All required disclosures were provided to the customer in clear, understandable language. Agent confirmed customer understanding before proceeding.',
        confidence: 0.96,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-2',
        scoreId: 's-5',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-2',
          name: 'Compliance Checklist',
          externalId: 'COMP-2024-Q4'
        },
        score: {
          id: 's-5',
          name: 'Required Disclosures',
          externalId: 'REQ-DISC-001'
        }
      },
      {
        id: 'sr-006',
        value: 'COMPLIANT',
        explanation: 'Customer consent was properly obtained and documented before accessing account information. Clear explanation of data usage provided.',
        confidence: 0.91,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-2',
        scoreId: 's-6',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-2',
          name: 'Compliance Checklist',
          externalId: 'COMP-2024-Q4'
        },
        score: {
          id: 's-6',
          name: 'Privacy & Consent',
          externalId: 'PRIV-CONSENT-001'
        }
      },
      {
        id: 'sr-007',
        value: 'NON_COMPLIANT',
        explanation: 'Agent failed to offer the required privacy policy review during account modification. This is a mandatory step for all account changes per regulatory requirements.',
        confidence: 0.88,
        itemId: 'item-001',
        accountId: 'acc-1',
        scorecardId: 'sc-2',
        scoreId: 's-7',
        updatedAt: relativeDate(0, 0, 5),
        createdAt: relativeDate(0, 0, 8),
        scorecard: {
          id: 'sc-2',
          name: 'Compliance Checklist',
          externalId: 'COMP-2024-Q4'
        },
        score: {
          id: 's-7',
          name: 'Regulatory Requirements',
          externalId: 'REG-REQ-001'
        }
      }
    ]
  }
};

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
  title: 'Content/ItemCard',
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
export const DetailWithScoreResults: Story = {
  render: (args) => <ItemCardWithMockScoreResults {...args} />,
  args: {
    variant: 'detail',
    item: {
      ...sampleItems[0],
      id: 'item-001', // Match our mock data
      externalId: 'CALL-20241201-001',
      description: 'Customer service call regarding billing inquiry. Customer contacted support to resolve unrecognized charges on their monthly statement. Agent provided account review and charge explanation services.',
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
        }
      ],
      text: 'Hello, thank you for calling our customer service line. My name is Sarah and I\'ll be helping you today. Can I please get your account number to start?\n\nCustomer: Hi Sarah, yes my account number is 12345678.\n\nGreat, thank you. I see your account here. How can I help you today?\n\nCustomer: I\'m having trouble with my recent bill. It seems like there are some charges I don\'t recognize.\n\nI understand your concern about the charges on your bill. Let me take a look at your account details and we can go through each charge together to make sure everything is accurate. Can you tell me which specific charges you\'re questioning?',
      scorecards: [
        { scorecardId: "sc-1", scorecardName: "Call Quality Assessment", resultCount: 4 },
        { scorecardId: "sc-2", scorecardName: "Compliance Checklist", resultCount: 3 }
      ]
    },
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Complete detail view showing actual score results from multiple scorecards with realistic data. This is the primary example demonstrating the full ItemCard detail experience including: **Multiple identifier types** (form, report, session, ID) with expandable display and external links, **Call transcript text** showing the conversation content, and **Comprehensive score results** with values (PASS, EXCELLENT, NEEDS_IMPROVEMENT, COMPLIANT, NON_COMPLIANT), detailed explanations, confidence scores (85%-98%), and grouped organization by scorecard. The mock includes both passing and failing scores with detailed explanations to showcase the complete evaluation workflow from content ingestion to assessment outcomes.'
      }
    }
  }
};

export const DetailWithScoreResultsReadOnly: Story = {
  render: (args) => <ItemCardWithMockScoreResults {...args} />,
  args: {
    variant: 'detail',
    item: {
      ...sampleItems[0],
      id: 'item-001', // Match our mock data
      externalId: 'CALL-20241201-001',
      // No description in read-only mode
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
        }
      ],
      // No text field - read-only mode
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
      scorecards: [
        { scorecardId: "sc-1", scorecardName: "Call Quality Assessment", resultCount: 4 },
        { scorecardId: "sc-2", scorecardName: "Compliance Checklist", resultCount: 3 }
      ]
    },
    readOnly: true,
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Read-only detail view focusing exclusively on score results without additional content. This clean presentation shows only the essential header information (identifiers, timestamps), metadata, attached files, and score results data, making it ideal for evaluation review workflows where the primary focus is on assessment outcomes rather than source content.'
      }
    }
  }
};

export const DetailItemEdit: Story = {
  render: (args) => <ItemCardWithMockScoreResults {...args} />,
  args: {
    variant: 'detail',
    item: {
      ...sampleItems[0],
      id: 'item-001', // Match our mock data
      externalId: 'CALL-20241201-001',
      description: 'Customer service call regarding billing inquiry. Customer contacted support to resolve unrecognized charges on their monthly statement. Agent provided account review and charge explanation services.',
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
        }
      ],
      text: 'Hello, thank you for calling our customer service line. My name is Sarah and I\'ll be helping you today. Can I please get your account number to start?\n\nCustomer: Hi Sarah, yes my account number is 12345678.\n\nGreat, thank you. I see your account here. How can I help you today?\n\nCustomer: I\'m having trouble with my recent bill. It seems like there are some charges I don\'t recognize.\n\nI understand your concern about the charges on your bill. Let me take a look at your account details and we can go through each charge together to make sure everything is accurate. Can you tell me which specific charges you\'re questioning?',
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
      scorecards: [
        { scorecardId: "sc-1", scorecardName: "Call Quality Assessment", resultCount: 4 },
        { scorecardId: "sc-2", scorecardName: "Compliance Checklist", resultCount: 3 }
      ]
    },
    readOnly: false,
    onClose: () => console.log('Close clicked'),
    onSave: async (item) => {
      console.log('Save item:', item);
      return Promise.resolve();
    }
  },
  parameters: {
    docs: {
      description: {
        story: 'Edit mode detail view showing the same scenario as "Detail Default" in ItemComponent stories. This demonstrates the full editing interface including metadata editor and file attachments in edit mode, allowing users to modify all aspects of the item including metadata entries and file uploads.'
      }
    }
  }
};

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

// Skeleton mode stories
export const GridSkeleton: Story = {
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
    isSelected: false,
    skeletonMode: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Grid view in skeleton loading state, showing placeholder elements that match the layout of the loaded state.'
      }
    }
  }
};

export const GridSelectedSkeleton: Story = {
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
    skeletonMode: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Selected grid view in skeleton loading state.'
      }
    }
  }
};

export const DetailSkeleton: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="h-[400px] w-full">
        <ItemCard
          {...args}
          getBadgeVariant={getBadgeVariant}
        />
      </div>
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[0],
    skeletonMode: true,
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view in skeleton loading state, showing placeholder elements for all components including action buttons.'
      }
    }
  }
};

export const DetailMultipleScorecardsSkeleton: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="h-[400px] w-full">
        <ItemCard
          {...args}
          getBadgeVariant={getBadgeVariant}
        />
      </div>
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[10], // Multiple scorecards
    skeletonMode: true,
    onClose: () => console.log('Close clicked'),
  },
  parameters: {
    docs: {
      description: {
        story: 'Detail view with multiple scorecards in skeleton loading state, showing placeholder elements for the expanded scorecard breakdown.'
      }
    }
  }
};

export const SkeletonComparison: Story = {
  render: () => (
    <div className="w-full p-4 space-y-6">
      <h3 className="text-lg font-semibold">Normal vs Skeleton Loading States</h3>
      
      {/* Grid comparison */}
      <div className="space-y-2">
        <h4 className="text-md font-medium">Grid View</h4>
        <div className="flex gap-4">
          <div className="max-w-sm">
            <p className="text-sm text-muted-foreground mb-2">Normal</p>
            <ItemCard
              variant="grid"
              item={sampleItems[1]}
              isSelected={false}
              getBadgeVariant={getBadgeVariant}
              skeletonMode={false}
            />
          </div>
          <div className="max-w-sm">
            <p className="text-sm text-muted-foreground mb-2">Skeleton</p>
            <ItemCard
              variant="grid"
              item={sampleItems[1]}
              isSelected={false}
              getBadgeVariant={getBadgeVariant}
              skeletonMode={true}
            />
          </div>
        </div>
      </div>

      {/* Detail comparison */}
      <div className="space-y-2">
        <h4 className="text-md font-medium">Detail View</h4>
        <div className="flex gap-4">
          <div className="w-80 h-64">
            <p className="text-sm text-muted-foreground mb-2">Normal</p>
            <ItemCard
              variant="detail"
              item={sampleItems[1]}
              getBadgeVariant={getBadgeVariant}
              skeletonMode={false}
              onClose={() => console.log('Close clicked')}
            />
          </div>
          <div className="w-80 h-64">
            <p className="text-sm text-muted-foreground mb-2">Skeleton</p>
            <ItemCard
              variant="detail"
              item={sampleItems[1]}
              getBadgeVariant={getBadgeVariant}
              skeletonMode={true}
              onClose={() => console.log('Close clicked')}
            />
          </div>
        </div>
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[0],
    getBadgeVariant,
  },
  parameters: {
    docs: {
      description: {
        story: 'Side-by-side comparison of normal and skeleton loading states for both grid and detail views, demonstrating how the skeleton maintains the same layout structure as the loaded content.'
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

// Custom demo component that shows ItemCard detail layout with mock score results
const ItemCardWithMockScoreResults = (props: any) => {
  const [isFullWidth, setIsFullWidth] = React.useState(false);
  const [isNarrowViewport, setIsNarrowViewport] = React.useState(false);
  
  React.useEffect(() => {
    const checkViewportWidth = () => {
      setIsNarrowViewport(window.innerWidth < 640)
    }
    checkViewportWidth()
    window.addEventListener('resize', checkViewportWidth)
    return () => window.removeEventListener('resize', checkViewportWidth)
  }, [])

  // Import the components we need
  const { Card, CardContent, CardHeader } = require('@/components/ui/card');
  const { MoreHorizontal, X, Square, Columns2, Info } = require('lucide-react');
  const DropdownMenu = require('@radix-ui/react-dropdown-menu');
  const { CardButton } = require('@/components/CardButton');
  const { Timestamp } = require('@/components/ui/timestamp');
  const { IdentifierDisplay } = require('@/components/ui/identifier-display');
  const ItemScoreResults = require('@/components/ItemScoreResults').default;
  const { MetadataEditor } = require('@/components/ui/metadata-editor');
  const { FileAttachments } = require('@/components/items/FileAttachments');
  
  const item = props.item;
  const readOnly = props.readOnly || false;

  return (
    <div className="h-[600px] w-full">
      <Card className="rounded-none sm:rounded-lg h-full flex flex-col bg-card border-none">
        <CardHeader className="flex-shrink-0 flex flex-row items-start justify-between py-4 px-4 sm:px-3 space-y-0">
          <div>
            <h2 className="text-xl text-muted-foreground font-semibold">Item Details</h2>
            <div className="mt-1 space-y-1">
              <IdentifierDisplay 
                externalId={item.externalId}
                identifiers={item.identifiers}
                iconSize="md"
                textSize="sm"
                displayMode="full"
              />
              <div className="text-sm text-muted-foreground">
                <Timestamp time={item.timestamp || item.date || ''} variant="relative" className="text-xs" />
              </div>
              {item.createdAt && item.updatedAt && (
                <Timestamp time={item.createdAt} completionTime={item.updatedAt} variant="elapsed" className="text-xs" />
              )}
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <DropdownMenu.Root>
              <DropdownMenu.Trigger asChild>
                <CardButton
                  icon={MoreHorizontal}
                  onClick={() => {}}
                  aria-label="More options"
                />
              </DropdownMenu.Trigger>
              <DropdownMenu.Portal>
                <DropdownMenu.Content align="end" className="min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md">
                  <DropdownMenu.Item 
                    className="relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                    onSelect={() => console.log('View Details clicked')}
                  >
                    <Info className="mr-2 h-4 w-4" />
                    View Details
                  </DropdownMenu.Item>
                </DropdownMenu.Content>
              </DropdownMenu.Portal>
            </DropdownMenu.Root>
            {!isNarrowViewport && (
              <CardButton
                icon={isFullWidth ? Columns2 : Square}
                onClick={() => setIsFullWidth(!isFullWidth)}
                aria-label={isFullWidth ? 'Exit full width' : 'Full width'}
              />
            )}
            {props.onClose && (
              <CardButton
                icon={X}
                onClick={props.onClose}
                aria-label="Close"
              />
            )}
          </div>
        </CardHeader>
        <CardContent className="flex-grow overflow-auto px-4 sm:px-3 pb-4">
          <div className="space-y-4">
            {item.description && 
             item.description.trim() && 
             !item.description.match(/^API Call - Report \d+$/) && 
             !item.description.match(/^(Call|Report|Session|Item) - .+$/) && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Description</h3>
                <div className="p-3">
                  <p className="text-sm text-muted-foreground">{item.description}</p>
                </div>
              </div>
            )}
            
            {item.text && (
              <div>
                <h3 className="text-sm font-medium text-foreground mb-2">Text</h3>
                <div className="p-3">
                  <p className="text-sm whitespace-pre-wrap">{item.text}</p>
                </div>
              </div>
            )}

            {/* Metadata editor */}
            <MetadataEditor
              value={item.metadata || {}}
              onChange={(newMetadata) => {
                if (props.onSave) {
                  props.onSave({ ...item, metadata: newMetadata });
                }
              }}
              disabled={readOnly}
            />

            {/* File attachments */}
            <FileAttachments
              attachedFiles={item.attachedFiles || []}
              readOnly={readOnly}
              onChange={(newFiles) => {
                if (props.onSave) {
                  props.onSave({ ...item, attachedFiles: newFiles });
                }
              }}
              onUpload={async (file) => {
                return Promise.resolve(`/uploads/${file.name}`);
              }}
            />
            
            <ItemScoreResults
              groupedResults={mockScoreResults}
              isLoading={false}
              error={null}
              itemId={String(item.id)}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
};


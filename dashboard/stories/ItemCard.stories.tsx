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

// Sample items for the stories
const sampleItems: ItemData[] = [
  { 
    id: 1, 
    scorecard: "CS3 Services v2", 
    score: "Email Compliance Assessment", 
    date: relativeDate(0, 0, 5), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 2, 
    scorecard: "CS3 Audigy", 
    score: "Phone Call Quality Review", 
    date: relativeDate(0, 0, 15), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 3, 
    scorecard: "AW IB Sales", 
    score: "Web Chat Support Evaluation", 
    date: relativeDate(0, 0, 30), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 4, 
    scorecard: "CS3 Nexstar v1", 
    score: "Customer Satisfaction Analysis", 
    date: relativeDate(0, 1, 0), 
    status: "Error", 
    results: 2, 
    inferences: 4, 
    cost: "$0.005" 
  },
  { 
    id: 5, 
    scorecard: "SelectQuote Term Life v1", 
    score: "Email Security Compliance Check", 
    date: relativeDate(0, 1, 30), 
    status: "Scoring", 
    results: 6, 
    inferences: 24, 
    cost: "$0.031" 
  },
  { 
    id: 6, 
    scorecard: "AW IB Sales", 
    score: "Telephone Transcript Analysis", 
    date: relativeDate(0, 2, 0), 
    status: "Done", 
    results: 19, 
    inferences: 152, 
    cost: "$0.199" 
  },
  { 
    id: 7, 
    scorecard: "CS3 Services v2", 
    score: "Live Chat Performance Review", 
    date: relativeDate(0, 4, 0), 
    status: "Done", 
    results: 16, 
    inferences: 32, 
    cost: "$0.042" 
  },
  { 
    id: 8, 
    scorecard: "CS3 Nexstar v1", 
    score: "Customer Experience Evaluation", 
    date: relativeDate(0, 5, 0), 
    status: "Done", 
    results: 17, 
    inferences: 68, 
    cost: "$0.089" 
  },
  { 
    id: 9, 
    scorecard: "SelectQuote Term Life v1", 
    score: "Communication Quality Assessment", 
    date: relativeDate(0, 6, 0), 
    status: "Done", 
    results: 13, 
    inferences: 52, 
    cost: "$0.068" 
  },
  { 
    id: 10, 
    scorecard: "CS3 Services v2", 
    score: "Digital Channel Compliance", 
    date: relativeDate(1, 0, 0), 
    status: "Done", 
    results: 15, 
    inferences: 30, 
    cost: "$0.039" 
  },
  { 
    id: 11, 
    scorecard: "AW IB Sales", 
    score: "Voice Interaction Analysis", 
    date: relativeDate(1, 2, 0), 
    status: "Done", 
    results: 18, 
    inferences: 144, 
    cost: "$0.188" 
  },
  { 
    id: 12, 
    scorecard: "CS3 Audigy", 
    score: "Multi Channel Support Review", 
    date: relativeDate(1, 4, 0), 
    status: "Done", 
    results: 16, 
    inferences: 64, 
    cost: "$0.084" 
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

// Grid variant stories
export const GridNew: Story = {
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
  },
};

export const GridError: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[3],
    isSelected: false,
  },
};

export const GridDone: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <div className="max-w-sm">
        <ItemCard {...args} />
      </div>
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[5],
    isSelected: false,
  },
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
};

// Detail variant stories
export const DetailNew: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[0],
    onClose: () => console.log('Close clicked'),
  },
};

export const DetailError: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[3],
    onClose: () => console.log('Close clicked'),
  },
};

export const DetailDone: Story = {
  render: (args) => (
    <div className="w-full p-4">
      <ItemCardDetailWrapper {...args} />
    </div>
  ),
  args: {
    variant: 'detail',
    item: sampleItems[5],
    onClose: () => console.log('Close clicked'),
  },
};

// Responsive grid layout story showing multiple cards
export const ResponsiveGrid: Story = {
  render: () => (
    <div className="w-full p-4">
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3">
        {sampleItems.slice(0, 6).map((item) => (
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
    item: sampleItems[0],
    getBadgeVariant,
  },
  parameters: {
    docs: {
      description: {
        story: 'Responsive grid layout that adapts to different screen sizes. Resize the viewport to see how the cards respond.'
      }
    }
  }
}; 
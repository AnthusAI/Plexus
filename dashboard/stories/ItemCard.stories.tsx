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
    score: 80, 
    date: relativeDate(0, 0, 5), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 2, 
    scorecard: "CS3 Audigy", 
    score: 89, 
    date: relativeDate(0, 0, 15), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 3, 
    scorecard: "AW IB Sales", 
    score: 96, 
    date: relativeDate(0, 0, 30), 
    status: "New", 
    results: 0, 
    inferences: 0, 
    cost: "$0.000" 
  },
  { 
    id: 4, 
    scorecard: "CS3 Nexstar v1", 
    score: 88, 
    date: relativeDate(0, 1, 0), 
    status: "Error", 
    results: 2, 
    inferences: 4, 
    cost: "$0.005" 
  },
  { 
    id: 5, 
    scorecard: "SelectQuote Term Life v1", 
    score: 83, 
    date: relativeDate(0, 1, 30), 
    status: "Scoring", 
    results: 6, 
    inferences: 24, 
    cost: "$0.031" 
  },
  { 
    id: 6, 
    scorecard: "AW IB Sales", 
    score: 94, 
    date: relativeDate(0, 2, 0), 
    status: "Done", 
    results: 19, 
    inferences: 152, 
    cost: "$0.199" 
  },
  { 
    id: 7, 
    scorecard: "CS3 Services v2", 
    score: 79, 
    date: relativeDate(0, 4, 0), 
    status: "Done", 
    results: 16, 
    inferences: 32, 
    cost: "$0.042" 
  },
  { 
    id: 8, 
    scorecard: "CS3 Nexstar v1", 
    score: 91, 
    date: relativeDate(0, 5, 0), 
    status: "Done", 
    results: 17, 
    inferences: 68, 
    cost: "$0.089" 
  },
  { 
    id: 9, 
    scorecard: "SelectQuote Term Life v1", 
    score: 89, 
    date: relativeDate(0, 6, 0), 
    status: "Done", 
    results: 13, 
    inferences: 52, 
    cost: "$0.068" 
  },
  { 
    id: 10, 
    scorecard: "CS3 Services v2", 
    score: 82, 
    date: relativeDate(1, 0, 0), 
    status: "Done", 
    results: 15, 
    inferences: 30, 
    cost: "$0.039" 
  },
  { 
    id: 11, 
    scorecard: "AW IB Sales", 
    score: 93, 
    date: relativeDate(1, 2, 0), 
    status: "Done", 
    results: 18, 
    inferences: 144, 
    cost: "$0.188" 
  },
  { 
    id: 12, 
    scorecard: "CS3 Audigy", 
    score: 87, 
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
    <div className="h-[400px] w-full max-w-[800px]">
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
  title: 'Items/ItemCard',
  component: ItemCard,
  parameters: {
    layout: 'centered',
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
  args: {
    variant: 'grid',
    item: sampleItems[0],
    isSelected: false,
  },
};

export const GridError: Story = {
  args: {
    variant: 'grid',
    item: sampleItems[3],
    isSelected: false,
  },
};

export const GridDone: Story = {
  args: {
    variant: 'grid',
    item: sampleItems[5],
    isSelected: false,
  },
};

export const GridSelected: Story = {
  args: {
    variant: 'grid',
    item: sampleItems[0],
    isSelected: true,
  },
};

// Detail variant stories
export const DetailNew: Story = {
  render: (args) => <ItemCardDetailWrapper {...args} />,
  args: {
    variant: 'detail',
    item: sampleItems[0],
    onClose: () => console.log('Close clicked'),
  },
};

export const DetailError: Story = {
  render: (args) => <ItemCardDetailWrapper {...args} />,
  args: {
    variant: 'detail',
    item: sampleItems[3],
    onClose: () => console.log('Close clicked'),
  },
};

export const DetailDone: Story = {
  render: (args) => <ItemCardDetailWrapper {...args} />,
  args: {
    variant: 'detail',
    item: sampleItems[5],
    onClose: () => console.log('Close clicked'),
  },
};

// Grid layout story showing multiple cards
export const GridLayout: Story = {
  render: () => (
    <div className="w-full max-w-[1200px]">
      <div className="@container">
        <div className="grid grid-cols-2 @[500px]:grid-cols-3 @[700px]:grid-cols-4 @[900px]:grid-cols-5 @[1100px]:grid-cols-6 gap-3">
          {sampleItems.map((item) => (
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
    </div>
  ),
  args: {
    variant: 'grid',
    item: sampleItems[0],
    getBadgeVariant,
  },
}; 
import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import ScoreInfo from '@/components/blocks/ScoreInfo';

const meta: Meta<typeof BlockRenderer> = {
  title: 'Reports/Blocks/ScoreInfo',
  component: BlockRenderer,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="bg-card p-6 rounded-lg">
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof BlockRenderer>;

export const Basic: Story = {
  args: {
    name: 'Score Information',
    output: {
      data: {
        name: 'Temperature Check',
        description: 'A score that measures the customer\'s sentiment',
        accuracy: 0.92,
        value: 0.78,
        updatedAt: '2023-10-27T10:05:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 0,
    config: {
      class: 'ScoreInfo',
      scorecard: 'example-scorecard-2',
      score: 'Temperature Check'
    }
  },
};

export const GoodPerformance: Story = {
  args: {
    name: 'Agent Effectiveness',
    output: {
      data: {
        name: 'Agent Effectiveness',
        description: 'Measures how effective the agent was in resolving customer issues',
        accuracy: 0.95,
        value: 0.88,
        updatedAt: '2023-11-15T14:30:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 1,
    config: {
      class: 'ScoreInfo',
      scorecard: 'customer_service_v2',
      score: 'Agent Effectiveness'
    }
  },
};

export const MediumPerformance: Story = {
  args: {
    name: 'Product Knowledge',
    output: {
      data: {
        name: 'Product Knowledge',
        description: 'Evaluates the agent\'s knowledge of products and services',
        accuracy: 0.87,
        value: 0.62,
        updatedAt: '2023-11-10T09:15:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 2,
    config: {
      class: 'ScoreInfo',
      scorecard: 'customer_service_v2',
      score: 'Product Knowledge'
    }
  },
};

export const PoorPerformance: Story = {
  args: {
    name: 'Issue Resolution Time',
    output: {
      data: {
        name: 'Issue Resolution Time',
        description: 'Measures how quickly the agent was able to resolve the customer\'s issue',
        accuracy: 0.91,
        value: 0.43,
        updatedAt: '2023-11-05T16:20:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 3,
    config: {
      class: 'ScoreInfo',
      scorecard: 'customer_service_v2',
      score: 'Issue Resolution Time'
    }
  },
};

export const MissingData: Story = {
  args: {
    name: 'Partial Information',
    output: {
      data: {
        name: 'Follow-up Quality',
        description: 'Evaluates the quality of follow-up communication',
        updatedAt: '2023-10-20T11:45:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 4,
    config: {
      class: 'ScoreInfo',
      scorecard: 'customer_service_v2',
      score: 'Follow-up Quality'
    }
  },
}; 
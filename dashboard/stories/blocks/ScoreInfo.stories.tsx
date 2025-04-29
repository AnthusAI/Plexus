import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import ScoreInfo from '@/components/blocks/ScoreInfo';

const meta: Meta<typeof ScoreInfo> = {
  title: 'Report Blocks/ScoreInfo',
  component: ScoreInfo,
  parameters: {
    layout: 'padded',
  },
};

export default meta;
type Story = StoryObj<typeof ScoreInfo>;

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
      scorecard: 'termlifev1',
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
    position: 0,
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
    position: 0,
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
    position: 0,
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
        // Missing accuracy and value
        updatedAt: '2023-10-20T11:45:00Z',
      },
      type: 'ScoreInfo'
    },
    position: 0,
    config: {
      class: 'ScoreInfo',
      scorecard: 'customer_service_v2',
      score: 'Follow-up Quality'
    }
  },
}; 
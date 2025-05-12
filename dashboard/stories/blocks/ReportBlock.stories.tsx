import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { BlockRenderer } from '@/components/blocks/BlockRegistry';
import ReportBlock from '@/components/blocks/ReportBlock';

const meta: Meta<typeof BlockRenderer> = {
  title: 'Report Blocks/ReportBlock',
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

// Update stories to use BlockRenderer and pass appropriate props
// NOTE: These stories now test BlockRenderer rendering the default ReportBlock

export const Basic: Story = {
  args: {
    name: 'Default Score Info Block',
    output: {
      name: 'Temperature Check',
      description: 'A score that measures the customer\'s sentiment',
      accuracy: 0.92,
      value: 0.78,
      updatedAt: '2023-10-27T10:05:00Z',
    },
    position: 0,
    config: {
      class: 'default',
    },
  },
};

export const LongContent: Story = {
  args: {
    name: 'Default Feedback Analysis Block',
    output: {
      feedback_categories: {
        positive: [
          'User interface is intuitive',
          'Customer service is responsive',
          'Navigation is clear and logical',
          'Documentation is helpful and detailed',
          'Search functionality works well',
        ],
        negative: [
          'Loading times could be improved',
          'Occasional errors when submitting forms',
          'Missing advanced filtering options',
          'Limited export capabilities',
          'Some features are difficult to discover',
        ],
        neutral: [
          'Would like to see more customization options',
          'Instructions could be clearer in some areas',
          'Not sure about the pricing model',
          'Integration with other tools is adequate',
          'Update frequency is reasonable but could be faster',
        ],
      },
      sentiment_analysis: {
        overall_score: 0.65,
        breakdown: {
          positive: 0.72,
          negative: 0.23,
          neutral: 0.05,
        },
        trend: 'Improving',
        commonWords: ['easy', 'helpful', 'slow', 'confusing', 'reliable', 'intuitive'],
        longTextExample: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.',
      },
    },
    position: 1,
    config: {
      class: 'default',
    },
  },
};

// This story tests the BlockRenderer's handling of unknown types
export const UnknownBlockType: Story = {
  args: {
    name: 'Original Name Before Error',
    output: {
      type: 'UnknownType',
      data: {
        someKey: 'someValue',
        anotherKey: 123,
        nestedData: { foo: 'bar', items: [1, 2, 3] }
      }
    },
    position: 2,
    config: {
      class: 'UnknownType',
      someParam: 'value'
    }
  },
};

// Keep ComplexData if needed, showing default rendering
export const ComplexDataDefault: Story = {
  args: {
    name: 'Default Complex Data Block',
    output: {
      type: 'ComplexData',
      data: {
        metrics: [
          { name: 'Accuracy', value: 0.95 },
          { name: 'Precision', value: 0.87 },
          { name: 'Recall', value: 0.92 },
        ],
        analysis: {
          summary: 'This is a complex data structure that would be rendered by the ReportBlock',
          details: 'When no specialized block component is available, ReportBlock provides a fallback visualization'
        },
        timestamps: {
          started: '2023-10-15T08:30:00Z',
          completed: '2023-10-15T09:45:00Z',
          duration: '1h 15m'
        }
      }
    },
    position: 3,
    config: {
      class: 'default',
      analysisType: 'comprehensive'
    }
  },
}; 
import type { Meta, StoryObj } from '@storybook/react';
import ItemScoreResults from '@/components/ItemScoreResults';
import { GroupedScoreResults } from '@/hooks/useItemScoreResults';

const meta: Meta<typeof ItemScoreResults> = {
  title: 'Components/ItemScoreResults',
  component: ItemScoreResults,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays score results for an item, organized by scorecard with lazy loading support.',
      },
    },
  },
  tags: ['autodocs'],
};

export default meta;
type Story = StoryObj<typeof meta>;

// Sample grouped results for stories
const sampleGroupedResults: GroupedScoreResults = {
  'scorecard-1': {
    scorecardId: 'scorecard-1',
    scorecardName: 'Customer Service Quality',
    scores: [
      {
        id: 'result-1',
        value: 'Yes',
        explanation: 'The agent provided a warm and professional greeting at the beginning of the call, clearly stating their name and asking how they could help.',
        confidence: 0.95,
        itemId: 'item-123',
        accountId: 'account-1',
        scorecardId: 'scorecard-1',
        scoreId: 'score-1',
        createdAt: '2024-01-15T10:30:00Z',
        updatedAt: '2024-01-15T10:30:00Z',
        scorecard: {
          id: 'scorecard-1',
          name: 'Customer Service Quality'
        },
        score: {
          id: 'score-1',
          name: 'Friendly Greeting'
        }
      },
      {
        id: 'result-2',
        value: 'No',
        explanation: 'The agent did not ask for the customer\'s permission before placing them on hold during the call.',
        confidence: 0.88,
        itemId: 'item-123',
        accountId: 'account-1',
        scorecardId: 'scorecard-1',
        scoreId: 'score-2',
        createdAt: '2024-01-15T10:31:00Z',
        updatedAt: '2024-01-15T10:31:00Z',
        scorecard: {
          id: 'scorecard-1',
          name: 'Customer Service Quality'
        },
        score: {
          id: 'score-2',
          name: 'Hold Permission'
        }
      },
      {
        id: 'result-3',
        value: '85',
        explanation: 'Overall customer satisfaction score based on tone analysis and resolution effectiveness.',
        confidence: 0.92,
        itemId: 'item-123',
        accountId: 'account-1',
        scorecardId: 'scorecard-1',
        scoreId: 'score-3',
        createdAt: '2024-01-15T10:32:00Z',
        updatedAt: '2024-01-15T10:32:00Z',
        scorecard: {
          id: 'scorecard-1',
          name: 'Customer Service Quality'
        },
        score: {
          id: 'score-3',
          name: 'Customer Satisfaction Score'
        }
      }
    ]
  },
  'scorecard-2': {
    scorecardId: 'scorecard-2',
    scorecardName: 'Compliance & Legal',
    scores: [
      {
        id: 'result-4',
        value: 'No',
        explanation: 'No profanity was detected during the call analysis.',
        confidence: 0.99,
        itemId: 'item-123',
        accountId: 'account-1',
        scorecardId: 'scorecard-2',
        scoreId: 'score-4',
        createdAt: '2024-01-15T10:33:00Z',
        updatedAt: '2024-01-15T10:33:00Z',
        scorecard: {
          id: 'scorecard-2',
          name: 'Compliance & Legal'
        },
        score: {
          id: 'score-4',
          name: 'Profanity Detection'
        }
      },
      {
        id: 'result-5',
        value: 'Yes',
        explanation: 'The agent properly disclosed all required legal information as per company policy.',
        confidence: 0.87,
        itemId: 'item-123',
        accountId: 'account-1',
        scorecardId: 'scorecard-2',
        scoreId: 'score-5',
        createdAt: '2024-01-15T10:34:00Z',
        updatedAt: '2024-01-15T10:34:00Z',
        scorecard: {
          id: 'scorecard-2',
          name: 'Compliance & Legal'
        },
        score: {
          id: 'score-5',
          name: 'Legal Disclosure'
        }
      }
    ]
  }
};

const emptyGroupedResults: GroupedScoreResults = {};

export const Default: Story = {
  args: {
    groupedResults: sampleGroupedResults,
    isLoading: false,
    error: null,
    itemId: 'item-123'
  },
};

export const Loading: Story = {
  args: {
    groupedResults: emptyGroupedResults,
    isLoading: true,
    error: null,
    itemId: 'item-123'
  },
};

export const Error: Story = {
  args: {
    groupedResults: emptyGroupedResults,
    isLoading: false,
    error: 'Failed to load score results. Please try again.',
    itemId: 'item-123'
  },
};

export const NoResults: Story = {
  args: {
    groupedResults: emptyGroupedResults,
    isLoading: false,
    error: null,
    itemId: 'item-123'
  },
};

export const SingleScorecard: Story = {
  args: {
    groupedResults: {
      'scorecard-1': sampleGroupedResults['scorecard-1']
    },
    isLoading: false,
    error: null,
    itemId: 'item-123'
  },
};

export const MultipleScorecardsExpanded: Story = {
  args: {
    groupedResults: sampleGroupedResults,
    isLoading: false,
    error: null,
    itemId: 'item-123'
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows multiple scorecards with their score results. All accordions are expanded by default.',
      },
    },
  },
};
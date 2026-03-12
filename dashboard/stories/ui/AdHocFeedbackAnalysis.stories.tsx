import React from 'react';
import type { Meta, StoryObj } from '@storybook/react';
import { AdHocFeedbackAnalysis } from '@/components/ui/ad-hoc-feedback-analysis';

const meta: Meta<typeof AdHocFeedbackAnalysis> = {
  title: 'UI/AdHocFeedbackAnalysis',
  component: AdHocFeedbackAnalysis,
  parameters: {
    layout: 'padded',
  },
  argTypes: {
    scorecardId: {
      control: 'text',
      description: 'ID of the scorecard to analyze'
    },
    scoreId: {
      control: 'text',
      description: 'ID of the specific score to analyze'
    },
    showConfiguration: {
      control: 'boolean',
      description: 'Whether to show the configuration panel'
    },
    defaultDays: {
      control: 'number',
      description: 'Default number of days for analysis'
    },
    title: {
      control: 'text',
      description: 'Custom title for the analysis'
    }
  },
  decorators: [
    (Story) => (
      <div className="h-screen bg-background">
        <Story />
      </div>
    ),
  ]
};

export default meta;
type Story = StoryObj<typeof AdHocFeedbackAnalysis>;

// Mock Amplify client for Storybook
const mockAmplifyClient = {
  graphql: async ({ query, variables }: any) => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Mock response based on query type
    if (query.includes('listFeedbackItems')) {
      return {
        data: {
          listFeedbackItems: {
            items: generateMockFeedbackItems(variables?.filter?.scoreId?.eq || 'score1')
          }
        }
      };
    }
    
    return { data: { listFeedbackItems: { items: [] } } };
  }
};

// Mock feedback data generator
function generateMockFeedbackItems(scoreId: string) {
  const mockItems = [];
  const labels = ['Yes', 'No', 'Maybe'];
  const scoreNames = {
    'score1': 'Agent Empathy',
    'score2': 'Problem Resolution', 
    'score3': 'Product Knowledge'
  };
  
  // Generate 50 mock feedback items
  for (let i = 0; i < 50; i++) {
    const initialValue = labels[Math.floor(Math.random() * labels.length)];
    const finalValue = Math.random() > 0.25 ? initialValue : labels[Math.floor(Math.random() * labels.length)]; // 75% agreement
    
    mockItems.push({
      id: `feedback-${i}`,
      itemId: `item-${i}`,
      scoreId: scoreId,
      initialAnswerValue: initialValue,
      finalAnswerValue: finalValue,
      editedAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      updatedAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      createdAt: new Date(Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000).toISOString(),
      score: {
        id: scoreId,
        name: scoreNames[scoreId as keyof typeof scoreNames] || 'Unknown Score',
        scorecard: {
          id: 'scorecard1',
          name: 'Test Scorecard'
        }
      },
      item: {
        id: `item-${i}`,
        externalId: `ext-${i}`,
        description: `Mock feedback item ${i}`
      }
    });
  }
  
  return mockItems;
}

// Mock the generateClient function for Storybook
const originalGenerateClient = (global as any).generateClient;
(global as any).generateClient = () => mockAmplifyClient;

export const ScoreAnalysis: Story = {
  args: {
    scoreId: 'score1',
    title: 'Score Feedback Analysis',
    showConfiguration: true,
    defaultDays: 30
  }
};

export const ScorecardAnalysis: Story = {
  args: {
    scorecardId: 'scorecard1',
    title: 'Scorecard Feedback Analysis',
    showConfiguration: true,
    defaultDays: 30
  }
};

export const WithoutConfiguration: Story = {
  args: {
    scoreId: 'score1',
    title: 'Quick Analysis',
    showConfiguration: false,
    defaultDays: 7
  }
};

export const CustomTitle: Story = {
  args: {
    scoreId: 'score2',
    title: 'Problem Resolution Performance Analysis',
    showConfiguration: true,
    defaultDays: 14
  }
};

export const ExtendedPeriod: Story = {
  args: {
    scorecardId: 'scorecard1',
    title: 'Quarterly Feedback Review',
    showConfiguration: true,
    defaultDays: 90
  }
};

export const MultipleScores: Story = {
  args: {
    scoreIds: ['score1', 'score2', 'score3'],
    title: 'Multi-Score Analysis',
    showConfiguration: true,
    defaultDays: 30
  }
};

// Component for demonstrating error states
const ErrorDemo = () => {
  const [showError, setShowError] = React.useState(false);
  
  // Override the mock to return an error
  React.useEffect(() => {
    if (showError) {
      (global as any).generateClient = () => ({
        graphql: async () => {
          await new Promise(resolve => setTimeout(resolve, 500));
          throw new Error('Failed to fetch feedback data. Check your network connection.');
        }
      });
    } else {
      (global as any).generateClient = () => mockAmplifyClient;
    }
  }, [showError]);
  
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button 
          onClick={() => setShowError(!showError)}
          className="px-4 py-2 bg-destructive text-destructive-foreground rounded"
        >
          {showError ? 'Show Success' : 'Show Error'}
        </button>
      </div>
      <AdHocFeedbackAnalysis
        scoreId="score1"
        title="Error State Demo"
        showConfiguration={true}
        defaultDays={30}
      />
    </div>
  );
};

export const ErrorState: Story = {
  render: () => <ErrorDemo />
};

// Component for demonstrating loading states
const LoadingDemo = () => {
  const [slowMode, setSlowMode] = React.useState(false);
  
  React.useEffect(() => {
    (global as any).generateClient = () => ({
      graphql: async ({ query, variables }: any) => {
        // Simulate slow API
        await new Promise(resolve => setTimeout(resolve, slowMode ? 5000 : 1000));
        
        if (query.includes('listFeedbackItems')) {
          return {
            data: {
              listFeedbackItems: {
                items: generateMockFeedbackItems(variables?.filter?.scoreId?.eq || 'score1')
              }
            }
          };
        }
        
        return { data: { listFeedbackItems: { items: [] } } };
      }
    });
  }, [slowMode]);
  
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <button 
          onClick={() => setSlowMode(!slowMode)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded"
        >
          {slowMode ? 'Fast Mode' : 'Slow Mode (5s)'}
        </button>
      </div>
      <AdHocFeedbackAnalysis
        scoreId="score1"
        title="Loading State Demo"
        showConfiguration={true}
        defaultDays={30}
      />
    </div>
  );
};

export const LoadingState: Story = {
  render: () => <LoadingDemo />
};

// Component for demonstrating empty data state
const EmptyDataDemo = () => {
  React.useEffect(() => {
    (global as any).generateClient = () => ({
      graphql: async () => {
        await new Promise(resolve => setTimeout(resolve, 1000));
        return {
          data: {
            listFeedbackItems: {
              items: [] // No feedback items
            }
          }
        };
      }
    });
  }, []);
  
  return (
    <AdHocFeedbackAnalysis
      scoreId="score1"
      title="Empty Data Demo"
      showConfiguration={true}
      defaultDays={30}
    />
  );
};

export const EmptyData: Story = {
  render: () => <EmptyDataDemo />
};

// Restore original function after stories
if (originalGenerateClient) {
  (global as any).generateClient = originalGenerateClient;
}
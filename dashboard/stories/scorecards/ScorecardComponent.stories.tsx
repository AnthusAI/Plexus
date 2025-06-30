import React from 'react'
import { Meta, StoryObj } from '@storybook/react'
import ScorecardComponent from '../../components/scorecards/ScorecardComponent'
import { AccountProvider } from '@/app/contexts/AccountContext'

export default {
  title: 'Scorecards/ScorecardComponent',
  component: ScorecardComponent,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <AccountProvider>
        <div className="w-full max-w-6xl">
          <Story />
        </div>
      </AccountProvider>
    ),
  ],
} satisfies Meta<typeof ScorecardComponent>
type Story = StoryObj<typeof ScorecardComponent>

const mockScorecard = {
  id: '123',
  name: 'Customer Service Scorecard',
  description: 'Evaluates quality of customer service interactions',
  scoreCount: 4, // Add the scoreCount property
  icon: null, // Add the icon property
  externalId: 'CS-001', // Add the externalId property
  sections: {
    items: [
      {
        id: 'section-1',
        name: 'Greeting & Introduction',
        scores: {
          items: [
            {
              id: 'score-1',
              name: 'Agent Introduction',
              description: 'Agent properly introduced themselves and the company',
              type: 'simple_llm_score'
            },
            {
              id: 'score-2',
              name: 'Verified Customer',
              description: 'Agent verified customer identity according to protocol',
              type: 'keyword_classifier'
            }
          ]
        }
      },
      {
        id: 'section-2',
        name: 'Problem Resolution',
        scores: {
          items: [
            {
              id: 'score-3',
              name: 'Issue Understanding',
              description: 'Agent demonstrated understanding of the customer issue',
              type: 'semantic_classifier'
            },
            {
              id: 'score-4',
              name: 'Solution Offered',
              description: 'Agent offered appropriate solution(s) to address the customer issue',
              type: 'programmatic_score'
            }
          ]
        }
      }
    ]
  },
  createdAt: '2025-04-01T00:00:00.000Z',
  updatedAt: '2025-04-01T00:00:00.000Z'
}

export const Default: Story = {
  args: {
    score: mockScorecard, // Changed from scorecard to score to match the component's props
    variant: 'detail', // Added variant prop
    isExpanded: true,
    onScorecardUpdate: () => console.log('Scorecard updated'),
    onDeleteSection: () => console.log('Section deleted'),
    onMoveSection: () => console.log('Section moved'),
    onDeleteScore: () => console.log('Score deleted'),
    onMoveScore: () => console.log('Score moved'),
  }
}

export const Collapsed: Story = {
  args: {
    ...Default.args,
    isExpanded: false,
  }
}

export const GridVariant: Story = {
  args: {
    ...Default.args,
    variant: 'grid',
  }
}
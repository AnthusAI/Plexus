import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import { ScoreVersionHistory } from '../components/ui/score-version-history'

// Helper to get a date from X minutes ago
const getTimeAgo = (minutes: number) => {
  const date = new Date()
  date.setMinutes(date.getMinutes() - minutes)
  return date.toISOString()
}

const mockUsers = {
  rp: {
    name: "Ryan Porter",
    avatar: "/user-avatar.png",
    initials: "RP"
  },
  jd: {
    name: "John Doe",
    avatar: "/avatar-1.png",
    initials: "JD"
  },
  as: {
    name: "Alice Smith",
    avatar: "/avatar-2.png",
    initials: "AS"
  }
}

const mockVersions = [
  {
    id: '1',
    scoreId: 'score1',
    configuration: JSON.stringify({
      name: 'Original Version',
      externalId: 'SCORE_V1'
    }),
    isFeatured: false,
    createdAt: getTimeAgo(60), // 1 hour ago
    updatedAt: getTimeAgo(60),
    comment: "Added initial score configuration with basic validation rules",
    user: mockUsers.rp
  },
  {
    id: '2',
    scoreId: 'score1',
    configuration: JSON.stringify({
      name: 'Updated Name',
      externalId: 'SCORE_V2'
    }),
    isFeatured: true,
    createdAt: getTimeAgo(30), // 30 mins ago
    updatedAt: getTimeAgo(30),
    comment: "Improved accuracy by adjusting thresholds and adding edge case handling",
    user: mockUsers.jd
  },
  {
    id: '3',
    scoreId: 'score1',
    configuration: JSON.stringify({
      name: 'Latest Version',
      externalId: 'SCORE_V3'
    }),
    isFeatured: false,
    createdAt: getTimeAgo(5), // 5 mins ago
    updatedAt: getTimeAgo(5),
    comment: "Optimized model parameters based on production feedback",
    user: mockUsers.as
  }
]

const meta = {
  title: 'UI/ScoreVersionHistory',
  component: ScoreVersionHistory,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    onToggleFeature: { action: 'toggled feature' }
  }
} satisfies Meta<typeof ScoreVersionHistory>

export default meta
type Story = StoryObj<typeof ScoreVersionHistory>

export const WithChampion: Story = {
  args: {
    versions: mockVersions,
    championVersionId: '3'
  }
}

export const WithFeatured: Story = {
  args: {
    versions: mockVersions,
    championVersionId: '2'
  }
}

export const SingleVersion: Story = {
  args: {
    versions: [mockVersions[0]],
    championVersionId: mockVersions[0].id
  }
}

export const LongComments: Story = {
  args: {
    versions: [
      {
        ...mockVersions[0],
        comment: `Comprehensive update to improve scoring reliability:

- Adjusted core parameters for better edge case handling
- Added validation rules for special characters
- Implemented QA team feedback about false positives
- Early testing shows 15% accuracy improvement`,
        user: mockUsers.rp
      },
      ...mockVersions.slice(1)
    ],
    championVersionId: '3'
  }
}

export const Empty: Story = {
  args: {
    versions: []
  }
}

export const AllVariants: Story = {
  render: () => {
    const handleToggleFeature = action('toggled feature');

    return (
      <div className="space-y-8 w-[600px]">
        <div>
          <div className="text-sm text-muted-foreground mb-2">With Champion Version</div>
          <ScoreVersionHistory 
            versions={mockVersions} 
            championVersionId="3"
            onToggleFeature={handleToggleFeature}
          />
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">Without Champion</div>
          <ScoreVersionHistory 
            versions={mockVersions}
            onToggleFeature={handleToggleFeature}
          />
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">Single Version</div>
          <ScoreVersionHistory 
            versions={[mockVersions[0]]}
            championVersionId={mockVersions[0].id}
            onToggleFeature={handleToggleFeature}
          />
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">Long Comments</div>
          <ScoreVersionHistory 
            versions={[
              {
                ...mockVersions[0],
                comment: "This is a much longer comment that describes in detail the changes made to this version. We updated the scoring criteria, improved accuracy by 15%, and added new validation rules for edge cases that were previously not handled correctly.",
                user: mockUsers.rp
              },
              ...mockVersions.slice(1)
            ]}
            championVersionId="3"
            onToggleFeature={handleToggleFeature}
          />
        </div>
        <div>
          <div className="text-sm text-muted-foreground mb-2">Empty State</div>
          <ScoreVersionHistory 
            versions={[]}
            onToggleFeature={handleToggleFeature}
          />
        </div>
      </div>
    );
  }
} 
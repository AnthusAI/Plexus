import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import { ScoreSidebarVersionHistory } from '../components/ui/score-sidebar-version-history'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../components/ui/tabs'
import { stringify as stringifyYaml } from 'yaml'

// Helper to get a date from X minutes ago
const getTimeAgo = (minutes: number) => {
  const date = new Date()
  date.setMinutes(date.getMinutes() - minutes)
  return date.toISOString()
}

const mockVersions = [
  {
    id: 'champion-version',
    scoreId: 'score1',
    configuration: stringifyYaml({
      name: 'Champion Score',
      externalId: 'SCORE_CHAMPION'
    }),
    guidelines: 'These are the champion guidelines for scoring.',
    isFeatured: false,
    createdAt: getTimeAgo(120), // 2 hours ago
    updatedAt: getTimeAgo(120),
    note: "Champion version with optimized parameters"
  },
  {
    id: 'version-2',
    scoreId: 'score1',
    configuration: stringifyYaml({
      name: 'Previous Version',
      externalId: 'SCORE_V2'
    }),
    guidelines: 'Previous version guidelines.',
    isFeatured: true,
    createdAt: getTimeAgo(60), // 1 hour ago
    updatedAt: getTimeAgo(60),
    note: "Improved accuracy by adjusting thresholds"
  },
  {
    id: 'version-3',
    scoreId: 'score1',
    configuration: stringifyYaml({
      name: 'Latest Test',
      externalId: 'SCORE_V3'
    }),
    guidelines: 'Latest test version guidelines.',
    isFeatured: false,
    createdAt: getTimeAgo(15), // 15 mins ago
    updatedAt: getTimeAgo(15),
    note: "Experimental changes for edge case handling"
  },
  {
    id: 'version-4',
    scoreId: 'score1',
    configuration: stringifyYaml({
      name: 'Bug Fix Version',
      externalId: 'SCORE_V4'
    }),
    guidelines: 'Bug fix version guidelines.',
    isFeatured: false,
    createdAt: getTimeAgo(5), // 5 mins ago
    updatedAt: getTimeAgo(5),
    note: "Fixed validation issue with special characters"
  }
]

// Interactive wrapper component that manages its own state for Storybook
const InteractiveStoryWrapper = ({ 
  versions = [], 
  championVersionId, 
  initialSelectedVersionId,
  initialIsSidebarCollapsed = false
}: {
  versions?: any[]
  championVersionId?: string
  initialSelectedVersionId?: string
  initialIsSidebarCollapsed?: boolean
}) => {
  const [selectedVersionId, setSelectedVersionId] = React.useState(initialSelectedVersionId)
  const [isSidebarCollapsed, setIsSidebarCollapsed] = React.useState(initialIsSidebarCollapsed)
  const [activeTab, setActiveTab] = React.useState<'guidelines' | 'code'>('guidelines')

  const handleVersionSelect = (version: any) => {
    setSelectedVersionId(version.id)
    action('version selected')(version)
  }

  const handleToggleSidebar = () => {
    setIsSidebarCollapsed(!isSidebarCollapsed)
    action('sidebar toggled')(!isSidebarCollapsed)
  }

  return (
    <div className="h-screen p-4 w-full max-w-full">
      <div className="flex h-full bg-background rounded-lg overflow-hidden w-full max-w-full">
        {/* Left Sidebar - Version History */}
        <ScoreSidebarVersionHistory
          versions={versions}
          championVersionId={championVersionId}
          selectedVersionId={selectedVersionId}
          onVersionSelect={handleVersionSelect}
          isSidebarCollapsed={isSidebarCollapsed}
          onToggleSidebar={handleToggleSidebar}
        />
        
        {/* Right Content Area - Mock Score Content */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Version Header */}
          {selectedVersionId && (
            <div className="p-3 flex-shrink-0">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div>
                    <h3 className="font-medium text-sm">
                      {selectedVersionId === championVersionId ? 'Champion Version' : 'Version'}
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      {versions.find(v => v.id === selectedVersionId)?.note || 'No note available'}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
          
                    {/* Mock Content Tabs */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'guidelines' | 'code')} className="flex-1 flex flex-col min-h-0">
              <TabsList className="h-auto p-0 bg-transparent border-b border-border justify-start">
                <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-4 py-2">Guidelines</TabsTrigger>
                <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-4 py-2">Code</TabsTrigger>
              </TabsList>
              
              <TabsContent value="guidelines" className="flex-1 flex flex-col min-h-0 mt-0">
                <div className="flex-1 p-4 overflow-y-auto bg-background">
                  <div className="text-sm text-muted-foreground space-y-2">
                    <p>This is a mock guidelines section to demonstrate the layout.</p>
                    <p>In the actual component, this would show the score guidelines and allow editing.</p>
                    <p>The content is responsive and should not cause width overflow issues.</p>
                    <p>Guidelines help evaluators understand how to consistently apply the scoring criteria.</p>
                    <p>They provide context, examples, and edge case handling instructions.</p>
                  </div>
                </div>
              </TabsContent>
              
              <TabsContent value="code" className="flex-1 flex flex-col min-h-0 mt-0">
                <div className="flex-1 p-4 overflow-auto bg-background">
                  <pre className="text-xs text-muted-foreground bg-muted/50 rounded p-3 overflow-x-auto">
{`name: "Sample Score"
type: "SimpleLLMScore"
description: "A sample score configuration"
prompt: |
  Analyze the following content and provide a score.

  Content: {{content}}

  Respond with either "Yes" or "No".
output_schema:
  type: "string"
  enum: ["Yes", "No"]`}
                  </pre>
                </div>
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
    </div>
  )
}

const meta = {
  title: 'Scorecards/ScoreSidebarVersionHistory',
  component: InteractiveStoryWrapper,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  argTypes: {
    versions: { control: 'object' },
    championVersionId: { control: 'text' },
    initialSelectedVersionId: { control: 'text' },
    initialIsSidebarCollapsed: { control: 'boolean' }
  }
} satisfies Meta<typeof InteractiveStoryWrapper>

export default meta
type Story = StoryObj<typeof InteractiveStoryWrapper>

export const Default: Story = {
  args: {
    versions: mockVersions,
    championVersionId: 'champion-version',
    initialSelectedVersionId: 'version-3',
    initialIsSidebarCollapsed: false
  }
}

export const Collapsed: Story = {
  args: {
    versions: mockVersions,
    championVersionId: 'champion-version',
    initialSelectedVersionId: 'champion-version',
    initialIsSidebarCollapsed: true
  }
}

export const NoChampion: Story = {
  args: {
    versions: mockVersions.slice(1), // Remove champion version
    initialSelectedVersionId: 'version-2',
    initialIsSidebarCollapsed: false
  }
}

export const SingleVersion: Story = {
  args: {
    versions: [mockVersions[0]],
    championVersionId: mockVersions[0].id,
    initialSelectedVersionId: mockVersions[0].id,
    initialIsSidebarCollapsed: false
  }
}

export const ManyVersions: Story = {
  args: {
    versions: [
      ...mockVersions,
      ...Array.from({ length: 10 }, (_, i) => ({
        id: `version-${i + 5}`,
        scoreId: 'score1',
        configuration: stringifyYaml({
          name: `Version ${i + 5}`,
          externalId: `SCORE_V${i + 5}`
        }),
        guidelines: `Guidelines for version ${i + 5}`,
        isFeatured: false,
        createdAt: getTimeAgo((i + 1) * 30),
        updatedAt: getTimeAgo((i + 1) * 30),
        note: `Version ${i + 5} with various improvements and bug fixes`
      }))
    ],
    championVersionId: 'champion-version',
    initialSelectedVersionId: 'version-7',
    initialIsSidebarCollapsed: false
  }
}

export const Empty: Story = {
  args: {
    versions: [],
    initialIsSidebarCollapsed: false
  }
}

export const Interactive: Story = {
  args: {
    versions: mockVersions,
    championVersionId: 'champion-version',
    initialSelectedVersionId: 'version-3',
    initialIsSidebarCollapsed: false
  }
}

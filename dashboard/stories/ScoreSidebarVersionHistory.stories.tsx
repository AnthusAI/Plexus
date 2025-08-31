import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { action } from '@storybook/addon-actions'
import { Crown, Expand, X } from 'lucide-react'
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
  const [isFullscreen, setIsFullscreen] = React.useState(false)
  const [hasChanges, setHasChanges] = React.useState(false)

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
                {selectedVersionId === championVersionId && (
                  <Crown className="h-6 w-6 text-muted-foreground" />
                )}
              </div>
            </div>
          )}
          
                    {/* Mock Content Tabs */}
          <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
            <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'guidelines' | 'code')} className="flex-1 flex flex-col min-h-0">
              <div className="flex items-center justify-between border-b border-border">
                <TabsList className="h-auto p-0 bg-transparent justify-start">
                  <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Guidelines</TabsTrigger>
                  <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Code</TabsTrigger>
                </TabsList>
                <div className="flex gap-1 pr-3">
                  <button 
                    className="p-1 rounded hover:bg-accent" 
                    aria-label="Open fullscreen editor"
                    onClick={() => setIsFullscreen(true)}
                  >
                    <Expand className="h-4 w-4" />
                  </button>
                </div>
              </div>
              
              <TabsContent value="guidelines" className="flex-1 p-4 overflow-y-auto bg-background mt-0 data-[state=inactive]:hidden">
                <div className="text-sm text-muted-foreground space-y-2">
                  <p>This is a mock guidelines section to demonstrate the layout.</p>
                  <p>In the actual component, this would show the score guidelines and allow editing.</p>
                  <p>The content is responsive and should not cause width overflow issues.</p>
                  <p>Guidelines help evaluators understand how to consistently apply the scoring criteria.</p>
                  <p>They provide context, examples, and edge case handling instructions.</p>
                </div>
              </TabsContent>
              
              <TabsContent value="code" className="flex-1 p-4 overflow-auto bg-background mt-0 data-[state=inactive]:hidden">
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
              </TabsContent>
            </Tabs>
          </div>
        </div>
      </div>
      
      {/* Fullscreen Interface */}
      {isFullscreen && (
        <div className="absolute inset-0 z-50 bg-background flex flex-col">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as 'guidelines' | 'code')} className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center justify-between border-b border-border">
              <TabsList className="h-auto p-0 bg-transparent justify-start">
                <TabsTrigger value="guidelines" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Guidelines</TabsTrigger>
                <TabsTrigger value="code" className="bg-transparent data-[state=active]:bg-transparent data-[state=active]:shadow-none border-b-2 border-transparent data-[state=active]:border-primary rounded-none px-3 py-2">Code</TabsTrigger>
              </TabsList>
              <div className="flex gap-2 pr-4">
                <button 
                  className="p-1 rounded hover:bg-accent" 
                  aria-label="Close fullscreen"
                  onClick={() => setIsFullscreen(false)}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            
            {/* Guidelines Tab - 50/50 split */}
            <TabsContent value="guidelines" className="flex-1 mt-0 data-[state=inactive]:hidden">
              <div className="flex h-full">
                <div className="w-1/2 border-r border-border p-4">
                  <div className="text-sm font-medium mb-2">Markdown Editor</div>
                  <textarea 
                    className="w-full h-full resize-none border rounded p-2 font-mono text-sm"
                    placeholder="Edit guidelines here..."
                    defaultValue="# Guidelines&#10;&#10;This is where you would edit the guidelines in markdown format.&#10;&#10;## Features&#10;- Real-time preview&#10;- Markdown syntax&#10;- Full-screen editing"
                    onChange={() => setHasChanges(true)}
                  />
                </div>
                <div className="w-1/2 p-4 overflow-y-auto bg-background">
                  <div className="text-sm font-medium mb-2">Preview</div>
                  <div className="prose prose-sm max-w-none">
                    <h1>Guidelines</h1>
                    <p>This is where you would edit the guidelines in markdown format.</p>
                    <h2>Features</h2>
                    <ul>
                      <li>Real-time preview</li>
                      <li>Markdown syntax</li>
                      <li>Full-screen editing</li>
                    </ul>
                  </div>
                </div>
              </div>
            </TabsContent>
            
            {/* Code Tab - 2/3 + 1/3 split */}
            <TabsContent value="code" className="flex-1 mt-0 data-[state=inactive]:hidden">
              <div className="flex h-full">
                <div className="w-2/3 border-r border-border p-4">
                  <div className="text-sm font-medium mb-2">YAML Editor</div>
                  <textarea 
                    className="w-full h-full resize-none border rounded p-2 font-mono text-sm"
                    defaultValue={`name: "Sample Score"
type: "SimpleLLMScore"
description: "A sample score configuration"
prompt: |
  Analyze the following content and provide a score.

  Content: {{content}}

  Respond with either "Yes" or "No".
output_schema:
  type: "string"
  enum: ["Yes", "No"]`}
                    onChange={() => setHasChanges(true)}
                  />
                </div>
                <div className="w-1/3 p-4 bg-background">
                  <div className="text-sm font-medium mb-2">Validation</div>
                  <div className="text-xs text-green-600 bg-green-50 rounded p-2">
                    ✓ YAML syntax is valid<br/>
                    ✓ All required fields present<br/>
                    ✓ Schema validation passed
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
          
          {/* Save/Cancel Bar - only show when there are changes */}
          {hasChanges && (
            <div className="flex items-center gap-3 p-4 border-t border-border">
              <button 
                className="px-3 py-1.5 text-sm border rounded hover:bg-accent" 
                onClick={() => setIsFullscreen(false)}
              >
                Cancel
              </button>
              <textarea
                placeholder="Please say what you changed and why..."
                className="flex-1 px-3 py-2 rounded-md bg-background border text-sm resize-none
                         placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                rows={1}
              />
              <button 
                className="px-3 py-1.5 text-sm bg-primary text-primary-foreground rounded hover:bg-primary/90"
                onClick={() => setHasChanges(false)}
              >
                Save
              </button>
            </div>
          )}
        </div>
      )}
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

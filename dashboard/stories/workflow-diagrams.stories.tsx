import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import Workflow from '../components/landing/workflow'
import MultiModelWorkflow from '../components/workflow/layouts/multi-model-workflow'
import ItemListWorkflow from '../components/workflow/layouts/item-list-workflow'

const Container = ({ children }: { children: React.ReactNode }) => (
  <div className="resize overflow-auto border-2 border-red-500 rounded-lg p-4 bg-background" 
       style={{ 
         width: '90vw', 
         height: '90vh', 
         minWidth: '420px',
         background: 'linear-gradient(45deg, #f0f0f0 25%, transparent 25%, transparent 75%, #f0f0f0 75%, #f0f0f0) 0 0, linear-gradient(45deg, #f0f0f0 25%, transparent 25%, transparent 75%, #f0f0f0 75%, #f0f0f0) 20px 20px',
         backgroundSize: '40px 40px'
       }}>
    <div className="w-full h-full border border-blue-500 bg-white">
      {children}
    </div>
  </div>
)

const meta = {
  title: 'Landing Pages/Pictograms/Diagrams',
  component: Workflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof Workflow>

export default meta
type Story = StoryObj<typeof Workflow>

export const Base: Story = {
  render: () => (
    <Container>
      <Workflow />
    </Container>
  ),
}

export const MultiModel: Story = {
  render: () => (
    <Container>
      <MultiModelWorkflow />
    </Container>
  ),
}

// Create a separate meta for ItemList stories
const itemListMeta = {
  title: 'Workflow Pictograms/Diagrams/Item List',
  component: ItemListWorkflow,
  parameters: {
    layout: 'centered',
  },
} satisfies Meta<typeof ItemListWorkflow>

type ItemListStory = StoryObj<typeof ItemListWorkflow>

// Base ItemList story with all media types and shapes
export const ItemListBase: ItemListStory = {
  render: () => (
    <Container>
      <ItemListWorkflow />
    </Container>
  ),
}

// Call Center QA - Audio only with simple checks
export const CallCenterQA: ItemListStory = {
  render: () => (
    <Container>
      <ItemListWorkflow 
        allowedMediaTypes={["audio"]} 
        allowedShapes={["circle"]}
        resultTypes={[
          { type: "check" },
          { type: "check" },
          { type: "check" },
          { type: "check" }
        ]}
      />
    </Container>
  ),
}

// Call Center QA - Multi-model with different shapes
export const CallCenterQAMultiModel: ItemListStory = {
  render: () => (
    <Container>
      <ItemListWorkflow 
        allowedMediaTypes={["audio"]} 
        fixedShapeSequence={["square", "circle", "triangle", "hexagon"]}
        resultTypes={[
          { type: "check" },
          { type: "check" },
          { type: "check" },
          { type: "check" }
        ]}
      />
    </Container>
  ),
}

// Call Center QA - Multi-type with different shapes and results
export const CallCenterQAMultiType: ItemListStory = {
  render: () => (
    <Container>
      <ItemListWorkflow 
        allowedMediaTypes={["audio"]} 
        fixedShapeSequence={["square", "pill", "triangle", "circle"]}
        resultTypes={[
          { 
            type: "text", 
            values: [
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "yes", color: "true" },
              { text: "no", color: "false" }
            ]
          },
          { 
            type: "text",
            values: [
              { text: "Skip", color: "muted-foreground", width: 2.5 },
              { text: "Accept", color: "true", width: 2.5 },
              { text: "Reject", color: "false", width: 2.5 },
              { text: "Report", color: "false", width: 2.5 }
            ]
          },
          { 
            type: "check"
          },
          { 
            type: "boolean",
            booleanRatio: 0.9
          }
        ]}
      />
    </Container>
  ),
} 
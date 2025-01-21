import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { DualPhaseProgressBar } from '../components/ui/dual-phase-progress-bar'
import { expect } from '@storybook/test'
import { within } from '@storybook/testing-library'

const meta = {
  title: 'Components/DualPhaseProgressBar',
  component: DualPhaseProgressBar,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
  argTypes: {
    firstPhaseProgress: {
      description: 'Progress percentage of the first phase (0-100)',
      control: { type: 'number', min: 0, max: 100 }
    },
    secondPhaseProgress: {
      description: 'Progress percentage of the second phase (0-100)',
      control: { type: 'number', min: 0, max: 100 }
    },
    isFocused: {
      description: 'Whether the progress bar is focused',
      control: 'boolean'
    },
    isFirstPhase: {
      description: 'Whether the progress bar is in the first phase',
      control: 'boolean'
    }
  }
} satisfies Meta<typeof DualPhaseProgressBar>

export default meta
type Story = StoryObj<typeof DualPhaseProgressBar>

export const Default: Story = {
  args: {
    isFirstPhase: true,
    firstPhaseProgress: 60,
    firstPhaseProcessedItems: 60,
    firstPhaseTotalItems: 100,
    secondPhaseProgress: 30,
    secondPhaseProcessedItems: 30,
    secondPhaseTotalItems: 100,
    isFocused: false
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('60%')).toBeInTheDocument()
    await expect(canvas.getByText('60')).toBeInTheDocument()
    await expect(canvas.getByText('100')).toBeInTheDocument()
  }
}

export const Focused: Story = {
  args: {
    isFirstPhase: true,
    firstPhaseProgress: 60,
    firstPhaseProcessedItems: 60,
    firstPhaseTotalItems: 100,
    secondPhaseProgress: 30,
    secondPhaseProcessedItems: 30,
    secondPhaseTotalItems: 100,
    isFocused: true
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('60%')).toBeInTheDocument()
    await expect(canvas.getByText('60')).toBeInTheDocument()
    await expect(canvas.getByText('100')).toBeInTheDocument()
  }
}

export const AllStates: Story = {
  render: () => (
    <div className="space-y-8 w-[600px]">
      <div>
        <div className="text-sm text-muted-foreground mb-2">
          Initial State - No progress
        </div>
        <DualPhaseProgressBar
          isFirstPhase={true}
          firstPhaseProgress={0}
          firstPhaseProcessedItems={0}
          firstPhaseTotalItems={100}
          secondPhaseProgress={0}
          secondPhaseProcessedItems={0}
          secondPhaseTotalItems={100}
        />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">
          First Phase In Progress - Adding scoring jobs
        </div>
        <DualPhaseProgressBar
          isFirstPhase={true}
          firstPhaseProgress={30}
          firstPhaseProcessedItems={30}
          firstPhaseTotalItems={100}
          secondPhaseProgress={0}
          secondPhaseProcessedItems={0}
          secondPhaseTotalItems={100}
        />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">
          First Phase Complete - All scoring jobs added
        </div>
        <DualPhaseProgressBar
          isFirstPhase={false}
          firstPhaseProgress={100}
          firstPhaseProcessedItems={100}
          firstPhaseTotalItems={100}
          secondPhaseProgress={0}
          secondPhaseProcessedItems={0}
          secondPhaseTotalItems={100}
        />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">
          Second Phase In Progress - Processing scoring jobs
        </div>
        <DualPhaseProgressBar
          isFirstPhase={false}
          firstPhaseProgress={100}
          firstPhaseProcessedItems={100}
          firstPhaseTotalItems={100}
          secondPhaseProgress={60}
          secondPhaseProcessedItems={60}
          secondPhaseTotalItems={100}
        />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">
          Both Phases Complete
        </div>
        <DualPhaseProgressBar
          isFirstPhase={false}
          firstPhaseProgress={100}
          firstPhaseProcessedItems={100}
          firstPhaseTotalItems={100}
          secondPhaseProgress={100}
          secondPhaseProcessedItems={100}
          secondPhaseTotalItems={100}
        />
      </div>

      <div>
        <div className="text-sm text-muted-foreground mb-2">
          Partial Progress (Focused)
        </div>
        <DualPhaseProgressBar
          isFirstPhase={true}
          firstPhaseProgress={75}
          firstPhaseProcessedItems={75}
          firstPhaseTotalItems={100}
          secondPhaseProgress={45}
          secondPhaseProcessedItems={45}
          secondPhaseTotalItems={100}
          isFocused
        />
      </div>
    </div>
  ),
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    
    // Check for presence of all expected progress values
    const progressValues = ['0%', '30%', '100%', '60%', '75%']
    for (const value of progressValues) {
      const elements = await canvas.queryAllByText(value)
      await expect(elements.length).toBeGreaterThan(0)
    }
  }
}

export const SmallBatch: Story = {
  args: {
    isFirstPhase: false,
    firstPhaseProgress: 100,
    firstPhaseProcessedItems: 3,
    firstPhaseTotalItems: 3,
    secondPhaseProgress: 66,
    secondPhaseProcessedItems: 2,
    secondPhaseTotalItems: 3,
    isFocused: false
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement)
    await expect(canvas.getByText('66%')).toBeInTheDocument()
    await expect(canvas.getByText('2')).toBeInTheDocument()
    await expect(canvas.getByText('3')).toBeInTheDocument()
  }
} 
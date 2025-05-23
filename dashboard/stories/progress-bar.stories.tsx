import React from "react"
import type { Meta, StoryObj } from '@storybook/react'
import { ProgressBar } from '../components/ui/progress-bar'

const meta = {
  title: 'General/Components/ProgressBar',
  component: ProgressBar,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof ProgressBar>

export default meta
type Story = StoryObj<typeof ProgressBar>

export const Single: Story = {
  args: {
    progress: 65,
    processedItems: 65,
    totalItems: 100,
    elapsedTime: "2m 30s",
    estimatedTimeRemaining: "1m 15s",
    color: "secondary",
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
}

export const NoTiming: Story = {
  args: {
    progress: 65,
    processedItems: 65,
    totalItems: 100,
    color: "secondary",
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
}

export const Focused: Story = {
  args: {
    progress: 65,
    processedItems: 65,
    totalItems: 100,
    elapsedTime: "2m 30s",
    estimatedTimeRemaining: "1m 15s",
    color: "secondary",
    isFocused: true,
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
}

export const InProgress: Story = {
  args: {
    progress: 65,
    processedItems: 65,
    totalItems: 100,
    elapsedTime: "2m 30s",
    estimatedTimeRemaining: "1m 15s",
    color: "secondary",
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
}

export const Complete: Story = {
  args: {
    progress: 100,
    processedItems: 100,
    totalItems: 100,
    elapsedTime: "5m 0s",
    color: "secondary",
    isFocused: false,
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[800px]">
        <Story />
      </div>
    ),
  ],
}

export const Demo: Story = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full max-w-[1200px] px-8">
        <div className="grid grid-cols-2 gap-16">
          <div className="space-y-8">
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Not Focused (with elapsed and ETA)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} 
                elapsedTime="0s" estimatedTimeRemaining="5m" />
              <ProgressBar progress={25} processedItems={25} totalItems={100} 
                elapsedTime="1m 15s" estimatedTimeRemaining="3m 45s" />
              <ProgressBar progress={50} processedItems={50} totalItems={100} 
                elapsedTime="2m 30s" estimatedTimeRemaining="2m 30s" />
              <ProgressBar progress={75} processedItems={75} totalItems={100} 
                elapsedTime="3m 45s" estimatedTimeRemaining="1m 15s" />
              <ProgressBar progress={100} processedItems={100} totalItems={100} 
                elapsedTime="5m" estimatedTimeRemaining="0s" />
            </div>
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Not Focused (elapsed only)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} 
                elapsedTime="0s" />
              <ProgressBar progress={25} processedItems={25} totalItems={100} 
                elapsedTime="1m 15s" />
              <ProgressBar progress={50} processedItems={50} totalItems={100} 
                elapsedTime="2m 30s" />
              <ProgressBar progress={75} processedItems={75} totalItems={100} 
                elapsedTime="3m 45s" />
              <ProgressBar progress={100} processedItems={100} totalItems={100} 
                elapsedTime="5m" />
            </div>
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Not Focused (no timing)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} />
              <ProgressBar progress={25} processedItems={25} totalItems={100} />
              <ProgressBar progress={50} processedItems={50} totalItems={100} />
              <ProgressBar progress={75} processedItems={75} totalItems={100} />
              <ProgressBar progress={100} processedItems={100} totalItems={100} />
            </div>
          </div>
          <div className="space-y-8">
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Focused (with elapsed and ETA)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} 
                elapsedTime="0s" estimatedTimeRemaining="5m" isFocused />
              <ProgressBar progress={25} processedItems={25} totalItems={100} 
                elapsedTime="1m 15s" estimatedTimeRemaining="3m 45s" isFocused />
              <ProgressBar progress={50} processedItems={50} totalItems={100} 
                elapsedTime="2m 30s" estimatedTimeRemaining="2m 30s" isFocused />
              <ProgressBar progress={75} processedItems={75} totalItems={100} 
                elapsedTime="3m 45s" estimatedTimeRemaining="1m 15s" isFocused />
              <ProgressBar progress={100} processedItems={100} totalItems={100} 
                elapsedTime="5m" estimatedTimeRemaining="0s" isFocused />
            </div>
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Focused (elapsed only)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} 
                elapsedTime="0s" isFocused />
              <ProgressBar progress={25} processedItems={25} totalItems={100} 
                elapsedTime="1m 15s" isFocused />
              <ProgressBar progress={50} processedItems={50} totalItems={100} 
                elapsedTime="2m 30s" isFocused />
              <ProgressBar progress={75} processedItems={75} totalItems={100} 
                elapsedTime="3m 45s" isFocused />
              <ProgressBar progress={100} processedItems={100} totalItems={100} 
                elapsedTime="5m" isFocused />
            </div>
            <div className="space-y-4">
              <h3 className="font-medium mb-2">Focused (no timing)</h3>
              <ProgressBar progress={0} processedItems={0} totalItems={100} isFocused />
              <ProgressBar progress={25} processedItems={25} totalItems={100} isFocused />
              <ProgressBar progress={50} processedItems={50} totalItems={100} isFocused />
              <ProgressBar progress={75} processedItems={75} totalItems={100} isFocused />
              <ProgressBar progress={100} processedItems={100} totalItems={100} isFocused />
            </div>
          </div>
        </div>
      </div>
    ),
  ],
} 
import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Hero } from '../components/landing/Hero'

const meta = {
  title: 'Landing/Hero',
  component: Hero,
  parameters: {
    layout: 'fullscreen',
  },
  decorators: [
    (Story) => (
      <div className="min-h-screen bg-background p-4">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof Hero>

export default meta
type Story = StoryObj<typeof Hero>

export const Desktop: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'desktop',
    },
  },
}

export const Tablet: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'tablet',
    },
  },
}

export const Mobile: Story = {
  parameters: {
    viewport: {
      defaultViewport: 'mobile1',
    },
  },
}

export const ResponsiveContainer: Story = {
  decorators: [
    (Story) => (
      <div className="resize overflow-auto border border-border rounded-lg" style={{ minWidth: '320px', width: '90vw', height: '90vh' }}>
        <Story />
      </div>
    ),
  ],
} 
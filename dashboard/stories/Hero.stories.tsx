import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { Hero } from '../components/landing/Hero'

const mockRouter = {
  push: async (url: string) => {
    console.log('Mock navigation to:', url)
  }
}

const meta = {
  title: 'Landing/Hero',
  component: Hero,
  parameters: {
    layout: 'fullscreen',
  },
  args: {
    mockRouter
  }
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
import type { Meta, StoryObj } from '@storybook/react'
import { Footer } from './Footer'

const meta = {
  title: 'Landing Pages/Footer',
  component: Footer,
  parameters: {
    layout: 'fullscreen',
    viewport: {
      defaultViewport: 'desktop',
    },
  },
} satisfies Meta<typeof Footer>

export default meta
type Story = StoryObj<typeof Footer>

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

export const Dark: Story = {
  parameters: {
    themes: {
      defaultTheme: 'dark',
    },
  },
} 
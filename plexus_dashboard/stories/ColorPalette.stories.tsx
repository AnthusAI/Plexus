import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import ColorPalette from '@/components/ColorPalette'
import { ThemeProvider } from 'next-themes'

const meta: Meta<typeof ColorPalette> = {
  title: 'Theme/ColorPalette',
  component: ColorPalette,
  decorators: [
    (Story) => (
      <ThemeProvider>
        <Story />
      </ThemeProvider>
    ),
  ],
  parameters: {
    layout: 'centered',
  },
}

export default meta
type Story = StoryObj<typeof ColorPalette>

export const Default: Story = {} 
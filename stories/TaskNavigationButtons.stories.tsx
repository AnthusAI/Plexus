import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { CardButtons } from '@/components/CardButtons'
import { Card, CardHeader } from '@/components/ui/card'

const meta = {
  title: 'Tasks/CardButtons',
  component: CardButtons,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <Card className="w-[400px]">
        <CardHeader className="flex flex-row items-center justify-end">
          <Story />
        </CardHeader>
      </Card>
    ),
  ],
} satisfies Meta<typeof CardButtons>

export default meta
type Story = StoryObj<typeof CardButtons>

export const Default: Story = {
  args: {
    isFullWidth: false,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
  },
}

export const FullWidth: Story = {
  args: {
    isFullWidth: true,
    onToggleFullWidth: () => console.log('Toggle full width'),
    onClose: () => console.log('Close'),
  },
} 
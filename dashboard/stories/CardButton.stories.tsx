import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { CardButton } from '@/components/CardButton'
import { Card, CardHeader } from '@/components/ui/card'
import { Square, X } from 'lucide-react'

const meta = {
  title: 'General/UI/CardButton',
  component: CardButton,
  parameters: {
    layout: 'centered',
  },
  decorators: [
    (Story) => (
      <Card className="w-[400px] bg-card">
        <CardHeader className="flex flex-row items-center justify-end">
          <Story />
        </CardHeader>
      </Card>
    ),
  ],
} satisfies Meta<typeof CardButton>

export default meta
type Story = StoryObj<typeof CardButton>

export const Single: Story = {
  args: {
    icon: X,
    onClick: () => console.log('Click'),
  },
}

export const SquareClose: Story = {
  render: () => (
    <div className="flex items-center space-x-2">
      <CardButton
        icon={Square}
        onClick={() => console.log('Toggle fullscreen')}
      />
      <CardButton
        icon={X}
        onClick={() => console.log('Close')}
      />
    </div>
  ),
} 
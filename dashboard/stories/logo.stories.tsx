import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import SquareLogo, { LogoVariant } from '../components/logo-square'

const meta = {
  title: 'Logo/Plexus Logo',
  component: SquareLogo,
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="bg-background p-8 rounded-lg">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof SquareLogo>

export default meta
type Story = StoryObj<typeof SquareLogo>

export const Square = {
  parameters: {
    layout: 'padded',
  },
  decorators: [
    (Story) => (
      <div className="w-full flex justify-center bg-background p-8">
        <div className="w-1/2">
          <Story />
        </div>
      </div>
    ),
  ],
  args: {
    variant: LogoVariant.Square,
    className: 'w-full',
  },
}

export const Wide = {
  args: {
    variant: LogoVariant.Wide,
    className: 'w-128',
  },
}

export const Narrow = {
  decorators: [
    (Story) => (
      <div className="w-24 aspect-square">
        <Story />
      </div>
    ),
  ],
  args: {
    variant: LogoVariant.Narrow,
    className: 'w-full h-full',
  },
}

export const AllVariants = {
  render: () => (
    <div className="space-y-8">
      <div>
        <div className="text-sm text-muted-foreground mb-2">Square Logo</div>
        <SquareLogo variant={LogoVariant.Square} className="w-64" />
      </div>
      
      <div>
        <div className="text-sm text-muted-foreground mb-2">Wide Logo</div>
        <SquareLogo variant={LogoVariant.Wide} className="w-128" />
      </div>
      
      <div>
        <div className="text-sm text-muted-foreground mb-2">Narrow Logo</div>
        <SquareLogo variant={LogoVariant.Narrow} className="w-24" />
      </div>
      
      <div>
        <div className="text-sm text-muted-foreground mb-2">Different Sizes</div>
        <div className="flex items-end space-x-4">
          <SquareLogo variant={LogoVariant.Square} className="w-32" />
          <SquareLogo variant={LogoVariant.Square} className="w-48" />
          <SquareLogo variant={LogoVariant.Square} className="w-64" />
        </div>
      </div>
    </div>
  ),
} 
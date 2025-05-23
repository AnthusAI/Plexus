import React from 'react'
import type { Meta, StoryObj, StoryFn } from '@storybook/react'
import SquareLogo, { LogoVariant } from '../components/logo-square'

const meta = {
  title: 'Theme/Logo',
  component: SquareLogo,
  parameters: {
    layout: 'padded',
  },
  args: {
    variant: LogoVariant.Square,
    className: 'w-full',
  },
} satisfies Meta<typeof SquareLogo>

export default meta
type Story = StoryObj<typeof SquareLogo>

export const Square = {
  parameters: {
    layout: 'padded',
  },
  args: {
    variant: LogoVariant.Square,
    className: 'w-full',
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full flex justify-center bg-background p-8">
        <div className="w-1/2">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const Wide = {
  args: {
    variant: LogoVariant.Wide,
    className: 'w-128',
  },
} satisfies Story

export const Narrow = {
  args: {
    variant: LogoVariant.Narrow,
    className: 'w-full',
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>) => (
      <div className="w-24 aspect-square">
        <Story {...Narrow.args} />
      </div>
    ),
  ],
} satisfies Story

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
} satisfies Story 
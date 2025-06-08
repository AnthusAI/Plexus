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
      <div className="w-full h-screen flex justify-center items-center bg-white p-8">
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
    className: 'w-full',
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full h-screen flex justify-center items-center bg-white p-8">
        <div className="w-1/2">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const Narrow = {
  args: {
    variant: LogoVariant.Narrow,
    className: 'w-full',
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full h-screen flex justify-center items-center bg-white p-8">
        <div className="w-24 aspect-square">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const WithShadow = {
  args: {
    variant: LogoVariant.Square,
    className: 'w-64',
    shadowEnabled: true,
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full h-screen flex justify-center items-center p-8" style={{ backgroundColor: '#ffffff' }}>
        <div className="w-1/2">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const WideWithShadow = {
  args: {
    variant: LogoVariant.Wide,
    className: 'w-full',
    shadowEnabled: true,
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full h-screen flex justify-center items-center p-8" style={{ backgroundColor: '#ffffff' }}>
        <div className="w-1/2">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const NarrowWithShadow = {
  args: {
    variant: LogoVariant.Narrow,
    className: 'w-full',
    shadowEnabled: true,
  },
  decorators: [
    (Story: StoryFn<typeof SquareLogo>, context) => (
      <div className="w-full h-screen flex justify-center items-center p-8" style={{ backgroundColor: '#ffffff' }}>
        <div className="w-24 aspect-square">
          <Story {...context.args} />
        </div>
      </div>
    ),
  ],
} satisfies Story

export const ShadowWidths = {
  render: () => (
    <div className="space-y-8 p-8" style={{ backgroundColor: '#ffffff' }}>
      <div className="text-lg font-bold">Shadow Widths</div>
      <div className="flex items-center justify-around">
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">12px</div>
          <SquareLogo variant={LogoVariant.Wide} className="w-96" shadowEnabled shadowWidth="12px" />
        </div>
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">24px (default)</div>
          <SquareLogo variant={LogoVariant.Wide} className="w-96" shadowEnabled />
        </div>
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">48px</div>
          <SquareLogo variant={LogoVariant.Wide} className="w-96" shadowEnabled shadowWidth="48px" />
        </div>
      </div>
    </div>
  ),
} satisfies Story

export const ShadowIntensities = {
  render: () => (
    <div className="space-y-8 p-8" style={{ backgroundColor: '#ffffff' }}>
      <div className="text-lg font-bold">Shadow Intensities</div>
      <div className="flex items-center justify-around">
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">0.25</div>
          <SquareLogo variant={LogoVariant.Narrow} className="w-24" shadowEnabled shadowIntensity={0.25} />
        </div>
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">0.5 (default)</div>
          <SquareLogo variant={LogoVariant.Narrow} className="w-24" shadowEnabled />
        </div>
        <div className="text-center">
          <div className="text-sm text-muted-foreground mb-2">0.9</div>
          <SquareLogo variant={LogoVariant.Narrow} className="w-24" shadowEnabled shadowIntensity={0.9} />
        </div>
      </div>
    </div>
  ),
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
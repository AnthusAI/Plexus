import type { Meta, StoryObj } from '@storybook/react'
import { Spinner } from '@/components/ui/spinner'

export default {
  title: 'General/Components/Spinner',
  component: Spinner,
  tags: ['autodocs'],
  parameters: {
    docs: {
      description: {
        component: 'A consistent, customizable spinner component based on the thick spinner design from the reports page. Provides different sizes and color variants.'
      }
    }
  }
} satisfies Meta<typeof Spinner>

type Story = StoryObj<typeof Spinner>

export const Default: Story = {
  args: {},
  decorators: [
    (Story) => (
      <div className="bg-card p-6 rounded-lg flex items-center justify-center">
        <Story />
      </div>
    )
  ]
}

export const Sizes: Story = {
  render: () => (
    <div className="bg-card p-6 rounded-lg">
      <div className="grid grid-cols-4 gap-6 items-center justify-items-center">
        <div className="text-center">
          <Spinner size="sm" />
          <p className="text-xs mt-2 text-muted-foreground">Small</p>
        </div>
        <div className="text-center">
          <Spinner size="md" />
          <p className="text-xs mt-2 text-muted-foreground">Medium</p>
        </div>
        <div className="text-center">
          <Spinner size="lg" />
          <p className="text-xs mt-2 text-muted-foreground">Large</p>
        </div>
        <div className="text-center">
          <Spinner size="xl" />
          <p className="text-xs mt-2 text-muted-foreground">Extra Large</p>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Available sizes: sm (16px), md (24px), lg (32px), xl (40px). The xl size matches the thick spinner used on the reports page.'
      }
    }
  }
}

export const Variants: Story = {
  render: () => (
    <div className="bg-card p-6 rounded-lg">
      <div className="grid grid-cols-3 gap-6 items-center justify-items-center">
        <div className="text-center">
          <Spinner variant="primary" size="lg" />
          <p className="text-xs mt-2 text-muted-foreground">Primary</p>
        </div>
        <div className="text-center">
          <Spinner variant="secondary" size="lg" />
          <p className="text-xs mt-2 text-muted-foreground">Secondary</p>
        </div>
        <div className="text-center">
          <Spinner variant="muted" size="lg" />
          <p className="text-xs mt-2 text-muted-foreground">Muted</p>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Available color variants: primary (blue), secondary (purple), and muted (gray). Secondary is the default and matches the reports page styling.'
      }
    }
  }
}

export const InUse: Story = {
  render: () => (
    <div className="space-y-6">
      {/* Loading overlay example */}
      <div className="bg-card p-6 rounded-lg">
        <h3 className="text-sm font-medium mb-4">Loading Overlay</h3>
        <div className="relative bg-background p-8 rounded border-2 border-dashed border-muted">
          <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center rounded">
            <Spinner size="xl" variant="secondary" />
          </div>
          <p className="text-muted-foreground">Content underneath the loading overlay</p>
        </div>
      </div>

      {/* Button loading example */}
      <div className="bg-card p-6 rounded-lg">
        <h3 className="text-sm font-medium mb-4">Button Loading</h3>
        <div className="flex gap-4">
          <button className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded">
            <Spinner size="sm" variant="primary" className="border-primary-foreground" />
            Loading...
          </button>
          <button className="flex items-center gap-2 px-4 py-2 bg-secondary text-secondary-foreground rounded">
            <Spinner size="sm" variant="secondary" className="border-secondary-foreground" />
            Processing...
          </button>
        </div>
      </div>

      {/* Card loading example */}
      <div className="bg-card p-6 rounded-lg">
        <h3 className="text-sm font-medium mb-4">Card Loading</h3>
        <div className="bg-background p-6 rounded border flex flex-col items-center justify-center min-h-[120px]">
          <Spinner size="lg" variant="secondary" />
          <p className="text-sm text-muted-foreground mt-3">Loading content...</p>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'Common usage patterns for the spinner component in different contexts: loading overlays, button states, and card loading states.'
      }
    }
  }
}

export const CustomStyling: Story = {
  render: () => (
    <div className="bg-card p-6 rounded-lg">
      <div className="grid grid-cols-2 gap-6 items-center justify-items-center">
        <div className="text-center">
          <Spinner size="xl" className="border-green-500" />
          <p className="text-xs mt-2 text-muted-foreground">Custom Green</p>
        </div>
        <div className="text-center">
          <Spinner size="xl" className="border-red-500 animate-bounce" />
          <p className="text-xs mt-2 text-muted-foreground">Custom Red + Bounce</p>
        </div>
      </div>
    </div>
  ),
  parameters: {
    docs: {
      description: {
        story: 'The spinner can be customized with additional className props to override colors or add different animations.'
      }
    }
  }
}
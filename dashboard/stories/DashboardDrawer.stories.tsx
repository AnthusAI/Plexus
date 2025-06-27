import React from 'react'
import type { Meta, StoryObj } from '@storybook/react'
import { DashboardDrawer, DashboardDrawerTrigger } from '@/components/DashboardDrawer'
import { Button } from '@/components/ui/button'
import { Gauge } from 'lucide-react'
import { AccountProvider } from '@/app/contexts/AccountContext'

// Mock account data for Storybook
const mockAccount = {
  id: 'story-account-123',
  name: 'Storybook Account',
  email: 'storybook@example.com'
}

// Mock AccountProvider for Storybook
const MockAccountProvider = ({ children }: { children: React.ReactNode }) => (
  <AccountProvider value={{ 
    selectedAccount: mockAccount, 
    setSelectedAccount: () => {}, 
    accounts: [mockAccount],
    isLoading: false 
  }}>
    {children}
  </AccountProvider>
)

const meta: Meta<typeof DashboardDrawer> = {
  title: 'Items/DashboardDrawer',
  component: DashboardDrawer,
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div className="h-screen flex items-center justify-center bg-background">
          <Story />
        </div>
      </MockAccountProvider>
    ),
  ],
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component: 'DashboardDrawer component with ItemsGauges metrics. Can be triggered by button click or keyboard shortcut. Designed for use in /lab/ routes.',
      },
    },
  },
  argTypes: {
    open: {
      control: { type: 'boolean' },
      description: 'Controls whether the drawer is open',
    },
    onOpenChange: {
      action: 'onOpenChange',
      description: 'Callback when drawer open state changes',
    },
  },
} satisfies Meta<typeof DashboardDrawer>

export default meta
type Story = StoryObj<typeof meta>

export const WithButton: Story = {
  render: () => (
    <DashboardDrawer>
      <Button variant="outline" className="gap-2">
        <Gauge className="h-4 w-4" />
        Open Dashboard
      </Button>
    </DashboardDrawer>
  ),
  parameters: {
    docs: {
      description: {
        story: 'DashboardDrawer with a custom trigger button. Click the button to open the drawer.',
      },
    },
  },
}

export const WithTrigger: Story = {
  render: () => <DashboardDrawerTrigger />,
  parameters: {
    docs: {
      description: {
        story: 'Pre-built DashboardDrawerTrigger component with standard styling.',
      },
    },
  },
}

export const Controlled: Story = {
  render: () => {
    const [open, setOpen] = React.useState(false)
    
    return (
      <div className="space-y-4">
        <div className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">
            Controlled drawer example - use the buttons to control the drawer state
          </p>
          <div className="flex gap-2 justify-center">
            <Button 
              variant="outline" 
              onClick={() => setOpen(true)}
              disabled={open}
            >
              Open Drawer
            </Button>
            <Button 
              variant="outline" 
              onClick={() => setOpen(false)}
              disabled={!open}
            >
              Close Drawer
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            Drawer is currently: <strong>{open ? 'Open' : 'Closed'}</strong>
          </p>
        </div>
        
        <DashboardDrawer 
          open={open} 
          onOpenChange={setOpen}
        >
          <Button className="gap-2">
            <Gauge className="h-4 w-4" />
            Dashboard
          </Button>
        </DashboardDrawer>
      </div>
    )
  },
  parameters: {
    docs: {
      description: {
        story: 'Controlled DashboardDrawer example showing how to manage open state externally.',
      },
    },
  },
}

export const AlwaysOpen: Story = {
  render: () => (
    <DashboardDrawer open={true} onOpenChange={() => {}}>
      <Button className="gap-2">
        <Gauge className="h-4 w-4" />
        Dashboard (Always Open)
      </Button>
    </DashboardDrawer>
  ),
  parameters: {
    docs: {
      description: {
        story: 'DashboardDrawer that stays open - useful for testing the drawer content and layout.',
      },
    },
  },
}

export const KeyboardShortcutDemo: Story = {
  render: () => {
    const [open, setOpen] = React.useState(false)
    
    React.useEffect(() => {
      const handleKeydown = (event: KeyboardEvent) => {
        if (event.key === '.') {
          event.preventDefault()
          setOpen(prev => !prev)
        }
      }
      
      document.addEventListener('keydown', handleKeydown)
      return () => document.removeEventListener('keydown', handleKeydown)
    }, [])
    
    return (
      <div className="space-y-4">
        <div className="text-center space-y-2">
          <p className="text-sm text-muted-foreground">
            Press the <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded">.</kbd> key to toggle the drawer
          </p>
          <p className="text-xs text-muted-foreground">
            Drawer is currently: <strong>{open ? 'Open' : 'Closed'}</strong>
          </p>
        </div>
        
        <DashboardDrawer 
          open={open} 
          onOpenChange={setOpen}
        >
          <Button className="gap-2">
            <Gauge className="h-4 w-4" />
            Dashboard (Keyboard: .)
          </Button>
        </DashboardDrawer>
      </div>
    )
  },
  parameters: {
    docs: {
      description: {
        story: 'Demonstration of keyboard shortcut functionality. Press the period key (.) to toggle the drawer open/closed.',
      },
    },
  },
}

export const ResponsiveLayout: Story = {
  render: () => (
    <DashboardDrawer>
      <Button className="gap-2">
        <Gauge className="h-4 w-4" />
        Test Responsive Layout
      </Button>
    </DashboardDrawer>
  ),
  decorators: [
    (Story) => (
      <MockAccountProvider>
        <div className="h-screen flex items-center justify-center bg-background p-4">
          <div className="text-center space-y-4">
            <p className="text-sm text-muted-foreground max-w-md">
              The drawer content is responsive and will adapt to different screen sizes. 
              Try resizing your browser window after opening the drawer to see how the 
              ItemsGauges component adjusts its layout.
            </p>
            <Story />
          </div>
        </div>
      </MockAccountProvider>
    ),
  ],
  parameters: {
    docs: {
      description: {
        story: 'Test the responsive behavior of the drawer content. The ItemsGauges component inside adapts to different container widths.',
      },
    },
  },
}
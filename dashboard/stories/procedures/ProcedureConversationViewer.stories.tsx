import type { Meta, StoryObj } from '@storybook/react'
import ProcedureConversationViewer from '@/components/procedure-conversation-viewer'

const meta = {
  title: 'Chat/Views/Procedure Wrapper',
  component: ProcedureConversationViewer,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ProcedureConversationViewer>

export default meta
type Story = StoryObj<typeof meta>

export const Default: Story = {
  args: {
    procedureId: 'proc-123',
    onSessionCountChange: (count) => console.log('Session count changed:', count),
    onFullscreenChange: (isFullscreen) => console.log('Fullscreen changed:', isFullscreen)
  }
}

export const WithManyConversations: Story = {
  args: {
    ...Default.args,
    procedureId: 'proc-with-many-conversations'
  }
}

export const EmptyState: Story = {
  args: {
    ...Default.args,
    procedureId: 'proc-empty'
  }
}

"use client"

import ConversationViewer from "@/components/ui/conversation-viewer"

interface ConsoleChatElementsAdapterProps {
  procedureId: string
  accountId?: string
  selectedSessionId?: string
  onSessionSelect?: (sessionId: string) => void
}

/**
 * Adapter boundary for the Console chat surface.
 *
 * This currently reuses the existing conversation + HITL renderer while the
 * Vercel AI Elements composition is introduced behind this boundary.
 */
export default function ConsoleChatElementsAdapter({
  procedureId,
  accountId,
  selectedSessionId,
  onSessionSelect,
}: ConsoleChatElementsAdapterProps) {
  return (
    <ConversationViewer
      procedureId={procedureId}
      defaultAccountIdForNewSession={accountId}
      selectedSessionId={selectedSessionId}
      onSessionSelect={onSessionSelect}
      forceProcedureIdForDispatch={procedureId}
      enableHitlActions
      defaultSidebarCollapsed={false}
      enableSidebarResize
      className="h-full"
    />
  )
}

"use client"
import React from "react"
import ConversationViewer from "@/components/ui/conversation-viewer"

interface ProcedureConversationViewerProps {
  procedureId: string
  onSessionCountChange?: (count: number) => void
  onFullscreenChange?: (isFullscreen: boolean) => void
}

export default function ProcedureConversationViewer({ 
  procedureId, 
  onSessionCountChange, 
  onFullscreenChange 
}: ProcedureConversationViewerProps) {
  const handleSessionDelete = (sessionId: string) => {
    // TODO: Implement actual delete functionality
    console.log('Delete session:', sessionId)
    // For now, just show a placeholder alert
    alert(`Delete session ${sessionId} - Not implemented yet`)
  }

  return (
    <div className="bg-background rounded-lg overflow-hidden h-[500px]">
      <ConversationViewer
        procedureId={procedureId}
        onSessionDelete={handleSessionDelete}
        onSessionCountChange={onSessionCountChange}
      />
    </div>
  )
}
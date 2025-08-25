"use client"
import React from "react"
import ConversationViewer from "@/components/ui/conversation-viewer"

interface ExperimentConversationViewerProps {
  experimentId: string
  onSessionCountChange?: (count: number) => void
  isFullscreen?: boolean
}

export default function ExperimentConversationViewer({ experimentId, onSessionCountChange, isFullscreen = false }: ExperimentConversationViewerProps) {
  const handleSessionDelete = (sessionId: string) => {
    // TODO: Implement actual delete functionality
    console.log('Delete session:', sessionId)
    // For now, just show a placeholder alert
    alert(`Delete session ${sessionId} - Not implemented yet`)
  }

  return (
    <div className={`bg-background rounded-lg overflow-hidden ${isFullscreen ? 'h-full' : 'h-[500px]'}`}>
      <ConversationViewer
        experimentId={experimentId}
        onSessionDelete={handleSessionDelete}
        onSessionCountChange={onSessionCountChange}
      />
    </div>
  )
}


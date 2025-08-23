"use client"
import React from "react"
import ConversationViewer from "@/components/ui/conversation-viewer"

interface ExperimentConversationViewerProps {
  experimentId: string
}

export default function ExperimentConversationViewer({ experimentId }: ExperimentConversationViewerProps) {
  const handleSessionDelete = (sessionId: string) => {
    // TODO: Implement actual delete functionality
    console.log('Delete session:', sessionId)
    // For now, just show a placeholder alert
    alert(`Delete session ${sessionId} - Not implemented yet`)
  }

  return (
    <div className="h-[500px] bg-background rounded-lg overflow-hidden">
      <ConversationViewer
        experimentId={experimentId}
        onSessionDelete={handleSessionDelete}
      />
    </div>
  )
}


"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import ConversationViewer, { ChatMessage, ChatSession } from "@/components/ui/conversation-viewer"

const client = generateClient<Schema>()

interface ExperimentConversationViewerProps {
  experimentId: string
}

export default function ExperimentConversationViewer({ experimentId }: ExperimentConversationViewerProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const loadConversationData = async () => {
      if (!experimentId) return

      try {
        setIsLoading(true)
        
        // Load chat sessions for the experiment
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByExperimentIdAndCreatedAt as any)({
          experimentId: experimentId,
          limit: 100
        })

        if (sessionsData) {
          const formattedSessions: ChatSession[] = sessionsData.map((session: any) => ({
            id: session.id,
            name: `Session ${session.id.slice(0, 8)}`,
            status: session.status,
            createdAt: session.createdAt,
            messageCount: 0 // Will be updated when we load messages
          }))
          setSessions(formattedSessions)
          
          if (formattedSessions.length > 0) {
            setSelectedSessionId(formattedSessions[0].id)
          }
        }

        // Load ALL messages for this experiment
        const { data: messagesData } = await (client.models.ChatMessage.listChatMessageByExperimentIdAndCreatedAt as any)({
          experimentId: experimentId,
          limit: 1000
        })

        if (messagesData) {
          const formattedMessages: ChatMessage[] = messagesData.map((msg: any) => ({
            id: msg.id,
            content: msg.content || '',
            role: msg.role as 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL',
            messageType: msg.messageType as 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE',
            toolName: msg.toolName,
            toolParameters: msg.toolParameters ? JSON.parse(msg.toolParameters) : undefined,
            toolResponse: msg.toolResponse ? JSON.parse(msg.toolResponse) : undefined,
            createdAt: msg.createdAt,
            sequenceNumber: msg.sequenceNumber,
            sessionId: msg.sessionId // Add sessionId for filtering
          }))
          
          setMessages(formattedMessages)
          
          // Update session message counts
          const sessionCounts = formattedMessages.reduce((acc: Record<string, number>, msg: any) => {
            acc[msg.sessionId] = (acc[msg.sessionId] || 0) + 1
            return acc
          }, {})
          
          setSessions(prev => prev.map(session => ({
            ...session,
            messageCount: sessionCounts[session.id] || 0
          })))
        }
        
      } catch (error) {
        console.error('Error loading conversation data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadConversationData()
  }, [experimentId])

  if (isLoading) {
    return (
      <div className="h-[500px] bg-background rounded-lg overflow-hidden flex items-center justify-center">
        <div className="text-muted-foreground">Loading conversation...</div>
      </div>
    )
  }

  return (
    <div className="h-[500px] bg-background rounded-lg overflow-hidden">
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId={selectedSessionId}
        onSessionSelect={setSelectedSessionId}
      />
    </div>
  )
}


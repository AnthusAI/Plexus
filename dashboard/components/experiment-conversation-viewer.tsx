"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { ConversationViewer } from "@/components/ui/conversation-viewer"
import type { ChatMessage, ChatSession } from "@/components/ui/conversation-viewer"

interface ExperimentConversationViewerProps {
  experimentId: string
}

const client = generateClient<Schema>()

export default function ExperimentConversationViewer({ experimentId }: ExperimentConversationViewerProps) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [selectedSessionId, setSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load chat sessions and messages
  useEffect(() => {
    if (!experimentId) {
      setIsLoading(false)
      return
    }

    loadChatData()
  }, [experimentId])

  const loadChatData = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      console.log('ExperimentConversationViewer: Loading sessions for experiment ID:', experimentId)
      
      // Query chat sessions for this experiment using GSI
      const { data: sessionsData, errors } = await (client.models.ChatSession.listChatSessionByExperimentIdAndCreatedAt as any)({
        experimentId: experimentId,
        limit: 100
      })

      console.log('ExperimentConversationViewer: Sessions response:', { sessionsData, errors })

      if (errors) {
        console.error('GraphQL errors loading chat sessions:', errors)
        setError('Failed to load chat sessions: ' + errors.map((e: any) => e.message).join(', '))
        return
      }

      if (!sessionsData || sessionsData.length === 0) {
        console.log('ExperimentConversationViewer: No sessions found for experiment', experimentId)
        setSessions([])
        setMessages([])
        setIsLoading(false)
        return
      }

      console.log('ExperimentConversationViewer: Found', sessionsData.length, 'sessions')
      
      // Transform sessions to match ConversationViewer interface
      const transformedSessions: ChatSession[] = sessionsData.map((session: any) => ({
        id: session.id,
        name: session.name || `Session ${session.id.slice(0, 8)}`,
        status: session.status || 'ACTIVE',
        createdAt: session.createdAt,
        messageCount: 0 // Will be updated after loading messages
      }))
      
      setSessions(transformedSessions)
      
      // Load ALL messages for this experiment
      await loadAllMessages()
      
      // Set the first session as selected by default
      if (sessionsData.length > 0) {
        const firstSession = sessionsData[0] as any
        setSelectedSessionId(firstSession.id)
      }
      
    } catch (err) {
      console.error('Error loading chat data:', err)
      setError(err instanceof Error ? err.message : 'Failed to load chat data')
    } finally {
      setIsLoading(false)
    }
  }

  const loadAllMessages = async () => {
    try {
      console.log('ExperimentConversationViewer: Loading messages for experiment', experimentId)
      
      // Query all chat messages for this experiment using GSI
      const { data: messagesData, errors: messageErrors } = await (client.models.ChatMessage.listChatMessageByExperimentIdAndCreatedAt as any)({
        experimentId: experimentId,
        limit: 1000
      })

      console.log('ExperimentConversationViewer: Messages response:', { 
        messagesCount: messagesData ? messagesData.length : 0, 
        errors: messageErrors 
      })

      if (messageErrors) {
        console.error('GraphQL errors loading chat messages:', messageErrors)
        setError('Failed to load chat messages: ' + messageErrors.map((e: any) => e.message).join(', '))
        return
      }

      if (!messagesData || messagesData.length === 0) {
        console.log('ExperimentConversationViewer: No messages found for experiment', experimentId)
        setMessages([])
        return
      }

      // Transform messages to match ConversationViewer interface
      const transformedMessages: ChatMessage[] = messagesData.map((message: any) => ({
        id: message.id,
        content: message.content,
        role: message.role,
        messageType: message.messageType,
        toolName: message.toolName,
        toolParameters: message.toolParameters ? JSON.parse(message.toolParameters) : undefined,
        toolResponse: message.toolResponse ? JSON.parse(message.toolResponse) : undefined,
        createdAt: message.createdAt,
        sequenceNumber: message.sequenceNumber,
        sessionId: message.sessionId // This is needed for filtering
      }))

      setMessages(transformedMessages)
      
      // Update session message counts
      const sessionMessageCounts = transformedMessages.reduce((acc: Record<string, number>, message) => {
        const sessionId = (message as any).sessionId
        if (sessionId) {
          acc[sessionId] = (acc[sessionId] || 0) + 1
        }
        return acc
      }, {})
      
      setSessions(prev => prev.map(session => ({
        ...session,
        messageCount: sessionMessageCounts[session.id] || 0
      })))

      console.log('ExperimentConversationViewer: Loaded', transformedMessages.length, 'total messages')
      
    } catch (err) {
      console.error('Error loading messages:', err)
      setError(err instanceof Error ? err.message : 'Failed to load messages')
    }
  }

  if (isLoading) {
    return (
      <div className="h-[500px] flex items-center justify-center bg-background rounded-lg border">
        <div className="text-center">
          <div className="text-sm text-muted-foreground">Loading conversation...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-[500px] flex items-center justify-center bg-background rounded-lg border">
        <div className="text-center">
          <div className="text-sm text-red-600">Error: {error}</div>
          <button 
            onClick={loadChatData}
            className="mt-2 text-xs text-blue-600 hover:underline"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="h-[500px] bg-background rounded-lg border overflow-hidden">
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId={selectedSessionId}
        onSessionSelect={setSelectedSessionId}
        className="h-full"
      />
    </div>
  )
}

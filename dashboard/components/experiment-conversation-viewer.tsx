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

  // Load initial conversation data
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
            name: session.name,
            category: session.category,
            status: session.status,
            createdAt: session.createdAt,
            updatedAt: session.updatedAt,
            messageCount: 0 // Will be updated when we load messages
          }))
          
          // Sort sessions by createdAt in descending order (most recent first)
          const sortedSessions = formattedSessions.sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )
          
          setSessions(sortedSessions)
          
          if (sortedSessions.length > 0) {
            // Select the most recent session (first in sorted array)
            setSelectedSessionId(sortedSessions[0].id)
          }
        }

        // Load ALL messages for this experiment with proper pagination
        console.log('Starting to fetch ChatMessages for experiment:', experimentId)
        
        let allMessages: any[] = []
        let nextToken: string | null = null
        let pageCount = 0
        
        do {
          pageCount++
          console.log('Fetching ChatMessage page:', {
            pageNumber: pageCount,
            nextToken,
            experimentId
          })

          const response = await (client.models.ChatMessage.listChatMessageByExperimentIdAndCreatedAt as any)({
            experimentId,
            limit: 1000,
            nextToken,
          })
          
          if (response?.data) {
            allMessages = [...allMessages, ...response.data]
          }
          
          nextToken = response.nextToken
        } while (nextToken)

        console.log(`Loaded ${allMessages.length} total messages across ${pageCount} pages`)

        if (allMessages.length > 0) {
          const formattedMessages: ChatMessage[] = allMessages.map((msg: any) => ({
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
          
          // Sort all messages in memory by sequence number and creation time
          const sortedMessages = formattedMessages.sort((a, b) => {
            if (a.sequenceNumber && b.sequenceNumber) {
              return a.sequenceNumber - b.sequenceNumber
            }
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          })
          
          setMessages(sortedMessages)
          
          // Update session message counts
          const sessionCounts = sortedMessages.reduce((acc: Record<string, number>, msg: any) => {
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

  // Realtime subscription for new chat messages
  useEffect(() => {
    // Only subscribe if we have both experimentId and selectedSessionId
    if (!experimentId || !selectedSessionId) {
      return
    }

    console.log('Setting up chat message subscription for experiment:', experimentId, 'session:', selectedSessionId)

    // Set up subscription for new chat messages in the current session
    const subscription = (client.graphql({
      query: `
        subscription OnCreateChatMessage($sessionId: String!, $experimentId: String!) {
          onCreateChatMessage(sessionId: $sessionId, experimentId: $experimentId) {
            id
            content
            role
            messageType
            toolName
            toolParameters
            toolResponse
            createdAt
            sequenceNumber
            sessionId
            experimentId
          }
        }
      `,
      variables: {
        sessionId: selectedSessionId,
        experimentId: experimentId
      }
    }) as any).subscribe({
      next: ({ data }: { data?: { onCreateChatMessage: any } }) => {
        if (data?.onCreateChatMessage) {
          const newMessage = data.onCreateChatMessage
          
          // Format the new message to match our ChatMessage interface
          const formattedMessage: ChatMessage = {
            id: newMessage.id,
            content: newMessage.content || '',
            role: newMessage.role as 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL',
            messageType: newMessage.messageType as 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE',
            toolName: newMessage.toolName,
            toolParameters: newMessage.toolParameters ? JSON.parse(newMessage.toolParameters) : undefined,
            toolResponse: newMessage.toolResponse ? JSON.parse(newMessage.toolResponse) : undefined,
            createdAt: newMessage.createdAt,
            sequenceNumber: newMessage.sequenceNumber,
            sessionId: newMessage.sessionId
          }
          
          // Add the new message to our local state
          setMessages(prevMessages => {
            // Check if message already exists to prevent duplicates
            const exists = prevMessages.some(msg => msg.id === formattedMessage.id)
            if (exists) {
              return prevMessages
            }
            
            // Add the new message and sort by sequence number
            const updatedMessages = [...prevMessages, formattedMessage]
            return updatedMessages.sort((a, b) => {
              if (a.sequenceNumber && b.sequenceNumber) {
                return a.sequenceNumber - b.sequenceNumber
              }
              return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
            })
          })
          
          // Update message count for the session
          setSessions(prevSessions => prevSessions.map(session => 
            session.id === selectedSessionId 
              ? { ...session, messageCount: (session.messageCount || 0) + 1 }
              : session
          ))
          
          console.log('Received new chat message in realtime:', formattedMessage)
        }
      },
      error: (error: Error) => {
        console.error('Chat message subscription error:', error)
      }
    })

    // Cleanup subscription on unmount or when dependencies change
    return () => {
      console.log('Cleaning up chat message subscription')
      subscription.unsubscribe()
    }
  }, [experimentId, selectedSessionId]) // Re-subscribe when experiment or session changes

  if (isLoading) {
    return (
      <div className="h-[500px] bg-background rounded-lg overflow-hidden flex items-center justify-center">
        <div className="text-muted-foreground">Loading conversation...</div>
      </div>
    )
  }

  const handleSessionDelete = (sessionId: string) => {
    // TODO: Implement actual delete functionality
    console.log('Delete session:', sessionId)
    // For now, just show a placeholder alert
    alert(`Delete session ${sessionId} - Not implemented yet`)
  }

  return (
    <div className="h-[500px] bg-background rounded-lg overflow-hidden">
      <ConversationViewer
        sessions={sessions}
        messages={messages}
        selectedSessionId={selectedSessionId}
        onSessionSelect={setSelectedSessionId}
        onSessionDelete={handleSessionDelete}
      />
    </div>
  )
}


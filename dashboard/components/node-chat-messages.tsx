"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Badge } from "@/components/ui/badge"
import { 
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  Clock,
  ChevronDown,
  ChevronRight
} from "lucide-react"
import { Timestamp } from "@/components/ui/timestamp"
import {
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"

// Types based on our GraphQL schema
type ChatMessage = Schema['ChatMessage']['type']
type ChatSession = Schema['ChatSession']['type']

interface ChatMessageWithDetails {
  id: string
  sessionId: string
  experimentId: string
  role?: string
  content: string
  messageType?: string
  toolName?: string
  parentMessageId?: string
  sequenceNumber?: number
  createdAt: string
  updatedAt: string
  parentMessage?: ChatMessageWithDetails
  childMessages?: ChatMessageWithDetails[]
}

const client = generateClient<Schema>()

// Message type icons and colors
const getMessageIcon = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') {
    return <Wrench className="h-3 w-3 text-blue-500" />
  }
  if (messageType === 'TOOL_RESPONSE') {
    return <Settings className="h-3 w-3 text-green-500" />
  }
  
  switch (role) {
    case 'USER':
      return <User className="h-3 w-3 text-purple-500" />
    case 'ASSISTANT':
      return <Bot className="h-3 w-3 text-blue-500" />
    case 'SYSTEM':
      return <Settings className="h-3 w-3 text-orange-500" />
    case 'TOOL':
      return <Wrench className="h-3 w-3 text-green-500" />
    default:
      return <MessageSquare className="h-3 w-3 text-gray-500" />
  }
}

const getMessageTypeColor = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') {
    return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
  }
  if (messageType === 'TOOL_RESPONSE') {
    return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
  }
  
  switch (role) {
    case 'USER':
      return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
    case 'ASSISTANT':
      return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
    case 'SYSTEM':
      return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
    case 'TOOL':
      return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
    default:
      return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
  }
}

// Get display label for message type
const getMessageTypeLabel = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') {
    return 'tool'
  }
  if (messageType === 'TOOL_RESPONSE') {
    return 'response'
  }
  
  switch (role) {
    case 'USER':
      return 'user'
    case 'ASSISTANT':
      return 'assistant'
    case 'SYSTEM':
      return 'system'
    case 'TOOL':
      return 'tool'
    default:
      return 'message'
  }
}

// Check if message should use monospace font
const shouldUseMonospace = (role?: string, messageType?: string) => {
  return messageType === 'TOOL_CALL' || messageType === 'TOOL_RESPONSE'
}

interface Props {
  nodeId: string
}

export default function NodeChatMessages({ nodeId }: Props) {
  const [messages, setMessages] = useState<ChatMessageWithDetails[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load chat messages for this specific node
  useEffect(() => {
    const loadNodeChatMessages = async () => {
      if (!nodeId) {
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        
        console.log('NodeChatMessages: Loading sessions for node ID:', nodeId)
        
        // Query chat sessions for this specific node
        const { data: sessionsData, errors: sessionErrors } = await (client.models.ChatSession.list as any)({
          filter: { nodeId: { eq: nodeId } }
        })

        if (sessionErrors) {
          console.error('GraphQL errors loading chat sessions:', sessionErrors)
          setError('Failed to load chat sessions: ' + sessionErrors.map((e: any) => e.message).join(', '))
          setIsLoading(false)
          return
        }

        if (!sessionsData || sessionsData.length === 0) {
          console.log('NodeChatMessages: No sessions found for node', nodeId)
          setMessages([])
          setIsLoading(false)
          return
        }

        console.log('NodeChatMessages: Found', sessionsData.length, 'sessions for node')
        
        // Load messages from all sessions for this node
        const allMessages: ChatMessageWithDetails[] = []
        
        for (const session of sessionsData as any[]) {
          const { data: messagesData, errors: messageErrors } = await (client.models.ChatMessage.list as any)({
            filter: { sessionId: { eq: session.id } }
          })

          if (messageErrors) {
            console.error('GraphQL errors loading messages:', messageErrors)
            continue
          }

          if (messagesData) {
            allMessages.push(...(messagesData as ChatMessageWithDetails[]))
          }
        }
        
        // Sort all messages by creation time
        const sortedMessages = allMessages.sort((a, b) => {
          const timeA = a.createdAt ? new Date(a.createdAt).getTime() : 0
          const timeB = b.createdAt ? new Date(b.createdAt).getTime() : 0
          return timeA - timeB
        })
        
        console.log('NodeChatMessages: Loaded', sortedMessages.length, 'total messages for node', nodeId)
        setMessages(sortedMessages)
        
      } catch (err) {
        console.error('Error loading node chat messages:', err)
        setError(err instanceof Error ? err.message : 'Failed to load chat messages')
      } finally {
        setIsLoading(false)
      }
    }

    loadNodeChatMessages()
  }, [nodeId])

  // Don't render anything if there are no messages
  if (isLoading) {
    return null // Don't show loading state for inline component
  }

  if (error) {
    return null // Don't show errors for inline component
  }

  if (messages.length === 0) {
    return null // Don't show anything if no messages
  }

  return (
    <AccordionItem value="chat-messages" className="border-b-0">
      <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
        <div className="flex items-center gap-2">
          <MessageSquare className="h-3 w-3 text-muted-foreground" />
          <span className="text-sm font-medium leading-none text-muted-foreground">
            Messages ({messages.length})
          </span>
          <ChevronRight className="h-3 w-3 text-muted-foreground transition-transform duration-200 group-data-[state=open]:hidden" />
          <ChevronDown className="h-3 w-3 text-muted-foreground transition-transform duration-200 hidden group-data-[state=open]:block" />
        </div>
      </AccordionTrigger>
      <AccordionContent className="pt-0 pb-4">
        <div className="space-y-2">
          {messages.map((message, index) => (
            <div key={message.id || index} className="bg-card rounded-md">
              {/* Header with message type and timestamp */}
              <div className="flex items-center justify-between px-3 py-2 border-b border-border">
                <div className="flex items-center gap-2">
                  <div className="flex-shrink-0">
                    {getMessageIcon(message.role, message.messageType)}
                  </div>
                  
                  <Badge 
                    variant="secondary" 
                    className={`text-xs ${getMessageTypeColor(message.role, message.messageType)}`}
                  >
                    {getMessageTypeLabel(message.role, message.messageType)}
                  </Badge>
                  
                  {message.toolName && (
                    <Badge variant="outline" className="text-xs">
                      {message.toolName}
                    </Badge>
                  )}
                  
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    <Timestamp time={message.createdAt} variant="relative" />
                  </div>
                </div>
              </div>
              
              {/* Message content with separate padding */}
              <div className="px-3 py-2">
                <div className={`text-xs ${shouldUseMonospace(message.role, message.messageType) ? 'font-mono' : ''}`}>
                  <p className="whitespace-pre-wrap break-words leading-relaxed">
                    {message.content}
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </AccordionContent>
    </AccordionItem>
  )
}
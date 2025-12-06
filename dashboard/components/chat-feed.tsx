"use client"

import { useState, useEffect, useRef } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import { Timestamp } from "@/components/ui/timestamp"
import { getMessageIcon, getMessageTypeColor, getMessageTypeLabel } from "@/components/ui/message-utils"
import { InteractiveMessage, type InteractiveMessageMetadata } from "@/components/ui/interactive-message"
import { RichMessageContent } from "@/components/ui/rich-message-content"

const client = generateClient<Schema>()

/**
 * Chat Message
 *
 * Universal message format supporting both legacy plain content and new rich metadata.
 *
 * @see message-metadata-spec.md for complete specification
 */
export interface ChatMessage {
  /** Unique message identifier */
  id: string

  /**
   * Legacy plain content field (still supported for backward compatibility)
   * If metadata is present, this may be empty
   */
  content: string

  /** Message sender role */
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'

  /** Message type classification */
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'

  /**
   * Human interaction type - determines visual styling and behavior
   *
   * Standard: CHAT, CHAT_ASSISTANT, INTERNAL
   * Notifications: NOTIFICATION
   * Alerts: ALERT_INFO, ALERT_WARNING, ALERT_ERROR, ALERT_CRITICAL
   * Pending: PENDING_APPROVAL, PENDING_INPUT, PENDING_REVIEW
   * Status: RESPONSE, TIMED_OUT, CANCELLED
   */
  humanInteraction?: string

  /** Tool name (for TOOL_CALL/TOOL_RESPONSE messages) */
  toolName?: string

  /** Associated procedure ID */
  procedureId?: string

  /** ISO 8601 timestamp */
  createdAt: string

  /**
   * Rich message metadata (new format)
   *
   * Supports:
   * - Markdown content
   * - Collapsible sections (all message types)
   * - Interactive buttons (PENDING messages only)
   * - Input fields (PENDING messages only)
   *
   * @see RichMessageMetadata
   * @see InteractiveMessageMetadata
   */
  metadata?: any
}

interface ChatFeedViewProps {
  messages: ChatMessage[]
  isLoading?: boolean
  error?: string | null
  className?: string
}

// Presentational component for Storybook
export function ChatFeedView({ messages, isLoading = false, error = null, className = '' }: ChatFeedViewProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (isLoading) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <Spinner size="lg" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-center">
          <p className="text-red-500 mb-2">Error loading messages</p>
          <p className="text-sm text-muted-foreground">{error}</p>
        </div>
      </div>
    )
  }

  if (messages.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="text-center">
          <p className="text-muted-foreground">No messages yet</p>
          <p className="text-sm text-muted-foreground mt-2">
            Messages from procedures will appear here
          </p>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea className={`h-full ${className}`} ref={scrollAreaRef}>
      <div className="space-y-4 p-4">
        {messages.map((message) => (
          <div key={message.id} className="flex items-start gap-3">
            <div className="flex-shrink-0 mt-1">
              {getMessageIcon(message.role, message.messageType, message.humanInteraction)}
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <Badge
                  variant="secondary"
                  className={`text-xs ${getMessageTypeColor(message.role, message.messageType, message.humanInteraction)}`}
                >
                  {getMessageTypeLabel(message.role, message.messageType, message.humanInteraction)}
                </Badge>

                {message.toolName && (
                  <Badge variant="outline" className="text-xs">
                    {message.toolName}
                  </Badge>
                )}

                <Timestamp time={message.createdAt} variant="relative" className="text-xs text-muted-foreground" />
              </div>

              <div className="text-sm">
                {/* Interactive messages (with buttons/inputs) */}
                {message.metadata && (message.humanInteraction === 'PENDING_APPROVAL' ||
                                      message.humanInteraction === 'PENDING_INPUT' ||
                                      message.humanInteraction === 'PENDING_REVIEW') ? (
                  <InteractiveMessage
                    metadata={message.metadata as InteractiveMessageMetadata}
                    onSubmit={async (data) => {
                      console.log('Interactive message response:', data)
                      // TODO: Handle submission (send to backend)
                    }}
                  />
                ) : message.metadata ? (
                  /* Rich content messages (with collapsible sections but no buttons) */
                  <RichMessageContent
                    metadata={message.metadata}
                  />
                ) : (
                  /* Legacy plain content */
                  <RichMessageContent
                    content={message.content}
                  />
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </ScrollArea>
  )
}

interface ChatFeedProps {
  accountId: string
  className?: string
}

// Container component with data fetching
export function ChatFeed({ accountId, className = '' }: ChatFeedProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Load messages for account
  const loadMessages = async () => {
    try {
      setIsLoading(true)
      setError(null)

      console.log('[ChatFeed] Loading messages for account:', accountId)

      // Use the accountId GSI for efficient querying
      const response: { data?: any[], nextToken?: string } = await (client.models.ChatMessage.listChatMessageByAccountIdAndCreatedAt as any)({
        accountId: accountId,
        sortDirection: 'ASC',
        limit: 500,
      }, {
        selectionSet: [
          'id',
          'content',
          'role',
          'messageType',
          'humanInteraction',
          'toolName',
          'procedureId',
          'accountId',
          'createdAt',
          'metadata'
        ]
      })

      if (response.data) {
        const formattedMessages = response.data.map((msg: any) => {
          // Parse metadata if it's a JSON string
          let parsedMetadata = msg.metadata
          if (typeof msg.metadata === 'string') {
            try {
              parsedMetadata = JSON.parse(msg.metadata)

              // Fix escaped newlines in content and collapsible sections
              if (parsedMetadata?.content) {
                parsedMetadata.content = parsedMetadata.content.replace(/\\n/g, '\n')
              }
              if (parsedMetadata?.collapsibleSections) {
                parsedMetadata.collapsibleSections = parsedMetadata.collapsibleSections.map((section: any) => ({
                  ...section,
                  content: section.content?.replace(/\\n/g, '\n') || section.content
                }))
              }
            } catch (e) {
              console.error('[ChatFeed] Failed to parse metadata:', e)
              parsedMetadata = null
            }
          }

          return {
            id: msg.id,
            content: msg.content || '',
            role: msg.role as 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL',
            messageType: msg.messageType as 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE' | undefined,
            humanInteraction: msg.humanInteraction,
            toolName: msg.toolName,
            procedureId: msg.procedureId,
            createdAt: msg.createdAt,
            metadata: parsedMetadata,
          }
        })

        // Filter: Only show messages intended for human viewing
        // Hide all INTERNAL messages (agent reasoning, tool calls, etc.)
        const visibleMessages = formattedMessages.filter((msg: ChatMessage) => {
          // If humanInteraction is explicitly set to INTERNAL, hide it
          if (msg.humanInteraction === 'INTERNAL') {
            return false
          }
          // Show all other messages (CHAT, NOTIFICATION, PENDING_*, ALERT_*, etc.)
          return true
        })

        // Sort by creation time (oldest first)
        const sortedMessages = visibleMessages.sort((a: ChatMessage, b: ChatMessage) => {
          return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
        })

        console.log('[ChatFeed] Loaded messages:', sortedMessages.length)
        setMessages(sortedMessages)
      }
    } catch (err) {
      console.error('[ChatFeed] Error loading messages:', err)
      setError(err instanceof Error ? err.message : 'Failed to load messages')
    } finally {
      setIsLoading(false)
    }
  }

  // Load initial messages
  useEffect(() => {
    if (accountId) {
      loadMessages()
    }
  }, [accountId])

  // Real-time subscription for new messages
  useEffect(() => {
    if (!accountId) return

    console.log('[ChatFeed] Setting up real-time subscription')

    let subscription: { unsubscribe: () => void } | null = null

    try {
      // @ts-ignore - Amplify Gen2 subscription type complexity
      subscription = client.models.ChatMessage.onCreate().subscribe({
        next: () => {
          console.log('[ChatFeed] New message notification received')
          loadMessages()
        },
        error: (err: any) => {
          console.error('[ChatFeed] Subscription error:', err)
        }
      })
    } catch (error) {
      console.error('[ChatFeed] Failed to set up subscription:', error)
    }

    return () => {
      if (subscription) {
        console.log('[ChatFeed] Unsubscribing from messages')
        subscription.unsubscribe()
      }
    }
  }, [accountId])

  // Render using the presentational component
  return (
    <ChatFeedView
      messages={messages}
      isLoading={isLoading}
      error={error}
      className={className}
    />
  )
}

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

  /** Associated account ID */
  accountId?: string

  /** Associated session ID */
  sessionId?: string

  /** Associated procedure ID */
  procedureId?: string

  /** Parent message ID (for threading and responses) */
  parentMessageId?: string

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
  onHitlSubmit?: (message: ChatMessage, data: Record<string, any>) => Promise<void>
  submittedMessages?: Set<string>
  submittingMessages?: Set<string>
}

// Presentational component for Storybook
export function ChatFeedView({
  messages,
  isLoading = false,
  error = null,
  className = '',
  onHitlSubmit,
  submittedMessages = new Set(),
  submittingMessages = new Set()
}: ChatFeedViewProps) {
  const scrollAreaRef = useRef<HTMLDivElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    console.log('[ChatFeedView] Auto-scroll triggered, messages count:', messages.length)
    if (messagesEndRef.current) {
      console.log('[ChatFeedView] Scrolling to bottom...')
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })
    } else {
      console.log('[ChatFeedView] messagesEndRef.current is null')
    }
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

                {/* Show submission status for PENDING messages */}
                {message.humanInteraction?.startsWith('PENDING_') && submittedMessages.has(message.id) && (
                  <Badge variant="outline" className="text-xs text-green-600 border-green-600">
                    ✓ Response submitted
                  </Badge>
                )}

                {message.humanInteraction?.startsWith('PENDING_') && submittingMessages.has(message.id) && (
                  <Badge variant="outline" className="text-xs text-blue-600 border-blue-600">
                    <Spinner size="sm" className="mr-1" />
                    Submitting...
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
                      console.log('[ChatFeedView] InteractiveMessage onSubmit called with data:', data)
                      const messageId = message.id
                      console.log('[ChatFeedView] Message ID:', messageId)
                      console.log('[ChatFeedView] Submitted messages:', Array.from(submittedMessages))
                      console.log('[ChatFeedView] Submitting messages:', Array.from(submittingMessages))

                      // Prevent double-submit
                      if (submittedMessages.has(messageId) || submittingMessages.has(messageId)) {
                        console.log('[ChatFeedView] Double-submit prevented')
                        return
                      }

                      // Call the parent handler
                      console.log('[ChatFeedView] onHitlSubmit exists:', !!onHitlSubmit)
                      if (onHitlSubmit) {
                        console.log('[ChatFeedView] Calling onHitlSubmit...')
                        await onHitlSubmit(message, data)
                        console.log('[ChatFeedView] onHitlSubmit completed')
                      } else {
                        console.error('[ChatFeedView] onHitlSubmit is undefined!')
                      }
                    }}
                    disabled={submittedMessages.has(message.id) || submittingMessages.has(message.id)}
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
  const [submittedMessages, setSubmittedMessages] = useState<Set<string>>(new Set())
  const [submittingMessages, setSubmittingMessages] = useState<Set<string>>(new Set())

  // Build response content based on message type
  const buildResponseContent = (
    requestType: string | undefined,
    submissionData: Record<string, any>,
    pendingMetadata: any
  ): Record<string, any> => {
    const responded_at = new Date().toISOString()

    switch (requestType) {
      case 'PENDING_APPROVAL':
        return {
          approved: submissionData.action === 'approve' || submissionData.action === 'Approve',
          responded_at
        }

      case 'PENDING_INPUT':
        return {
          input: submissionData.input || submissionData.action || '',
          responded_at
        }

      case 'PENDING_REVIEW':
        return {
          decision: submissionData.action, // Button label clicked
          feedback: submissionData.feedback || submissionData.input || '',
          edited_artifact: submissionData.edited_artifact || null,
          responded_at
        }

      default:
        return { action: submissionData.action, responded_at }
    }
  }

  // Handle HITL response submission
  const handleHitlResponse = async (
    pendingMessage: ChatMessage,
    submissionData: Record<string, any>
  ) => {
    console.log('[ChatFeed] handleHitlResponse called')
    console.log('[ChatFeed] Pending message:', pendingMessage.id)
    console.log('[ChatFeed] Submission data:', submissionData)

    // Validate required fields
    if (!pendingMessage.sessionId) {
      throw new Error('Session ID is required for HITL response')
    }

    // Build response content based on message type
    const responseContent = buildResponseContent(
      pendingMessage.humanInteraction,
      submissionData,
      pendingMessage.metadata
    )
    console.log('[ChatFeed] Response content:', responseContent)

    // Create RESPONSE message
    console.log('[ChatFeed] Creating RESPONSE message...')
    const messageData = {
      accountId: pendingMessage.accountId,
      sessionId: pendingMessage.sessionId,
      procedureId: pendingMessage.procedureId,
      parentMessageId: pendingMessage.id,
      role: 'USER',
      humanInteraction: 'RESPONSE',
      content: JSON.stringify(responseContent),
      createdAt: new Date().toISOString(),
      metadata: JSON.stringify({
        callback_id: pendingMessage.metadata?.callback_id, // Pass through for Lambda Durable mode
        response_type: pendingMessage.humanInteraction?.replace('PENDING_', '').toLowerCase(),
        original_request: pendingMessage.id,
        submitted_at: new Date().toISOString()
      })
    }
    // @ts-ignore - Amplify generates complex union types that TypeScript can't fully infer
    const result: any = await client.models.ChatMessage.create(messageData as any)
    console.log('[ChatFeed] RESPONSE message created:', result)

    // Real-time subscription will trigger reload
  }

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
          'parentMessageId',
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
            parentMessageId: msg.parentMessageId,
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

  // Wrapped HITL handler with state management
  const handleHitlSubmit = async (message: ChatMessage, data: Record<string, any>) => {
    console.log('[ChatFeed] handleHitlSubmit called')
    console.log('[ChatFeed] Message:', message.id)
    console.log('[ChatFeed] Data:', data)

    const messageId = message.id

    // Mark as submitting
    console.log('[ChatFeed] Marking as submitting:', messageId)
    setSubmittingMessages(prev => new Set(prev).add(messageId))

    try {
      console.log('[ChatFeed] Calling handleHitlResponse...')
      await handleHitlResponse(message, data)
      console.log('[ChatFeed] handleHitlResponse completed, marking as submitted')
      setSubmittedMessages(prev => new Set(prev).add(messageId))
    } catch (error) {
      console.error('[ChatFeed] Failed to submit response:', error)
      // TODO: Add error state and display to user
    } finally {
      console.log('[ChatFeed] Removing from submitting set')
      setSubmittingMessages(prev => {
        const next = new Set(prev)
        next.delete(messageId)
        return next
      })
    }
  }

  // Render using the presentational component
  return (
    <ChatFeedView
      messages={messages}
      isLoading={isLoading}
      error={error}
      className={className}
      onHitlSubmit={handleHitlSubmit}
      submittedMessages={submittedMessages}
      submittingMessages={submittingMessages}
    />
  )
}

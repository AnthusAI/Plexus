"use client"

import { useState, useEffect, FormEvent } from 'react'
import { generateClient } from 'aws-amplify/data'
import type { Schema } from '@/amplify/data/resource'
import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Send, Mic, Headphones } from 'lucide-react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'

const client = generateClient<Schema>()

export interface ChatInterfaceViewProps {
  // Display props
  messages: ChatMessage[]
  isLoading?: boolean
  error?: string | null
  className?: string

  // Interaction props
  onSendMessage?: (message: string) => void | Promise<void>
  onVoiceInput?: () => void
  onVoiceMode?: () => void
  placeholder?: string

  // HITL props
  onHitlSubmit?: (message: ChatMessage, data: Record<string, any>) => Promise<void>
  submittedMessages?: Set<string>
  submittingMessages?: Set<string>

  // Feature flags
  showInput?: boolean
  showVoiceButtons?: boolean
  disabled?: boolean
}

/**
 * Interactive chat interface with message display and input field.
 * This is a presentation component that accepts messages and callbacks.
 */
export function ChatInterfaceView({
  messages,
  isLoading = false,
  error = null,
  className = '',
  onSendMessage,
  onVoiceInput,
  onVoiceMode,
  placeholder = 'Type a message...',
  onHitlSubmit,
  submittedMessages = new Set(),
  submittingMessages = new Set(),
  showInput = true,
  showVoiceButtons = true,
  disabled = false,
}: ChatInterfaceViewProps) {
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()

    if (!inputValue.trim() || !onSendMessage || isSending || disabled) {
      return
    }

    setIsSending(true)
    try {
      await onSendMessage(inputValue.trim())
      setInputValue('') // Clear input after successful send
    } catch (error) {
      console.error('Error sending message:', error)
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Messages Display */}
      <div className="flex-grow overflow-hidden min-h-0">
        <ChatFeedView
          messages={messages}
          isLoading={isLoading}
          error={error}
          onHitlSubmit={onHitlSubmit}
          submittedMessages={submittedMessages}
          submittingMessages={submittingMessages}
        />
      </div>

      {/* Input Area */}
      {showInput && (
        <div className="border-t border-border">
          <form onSubmit={handleSubmit} className="flex items-center p-4 gap-2">
            <Input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={placeholder}
              disabled={disabled || isSending}
              className="flex-grow bg-background"
            />
            <Button
              type="submit"
              size="icon"
              disabled={!inputValue.trim() || disabled || isSending}
            >
              <Send className="h-4 w-4" />
            </Button>
          </form>

          {/* Voice Controls */}
          {showVoiceButtons && (
            <div className="px-4 pb-2 flex gap-2">
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0"
                      onClick={onVoiceInput}
                      disabled={disabled}
                    >
                      <Mic className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Dictate Message
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>

              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-8 w-8 p-0"
                      onClick={onVoiceMode}
                      disabled={disabled}
                    >
                      <Headphones className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="top">
                    Voice Mode
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// Container component props
export interface ChatInterfaceProps {
  accountId: string
  className?: string
  placeholder?: string
  showInput?: boolean
  showVoiceButtons?: boolean
  onVoiceInput?: () => void
  onVoiceMode?: () => void
}

/**
 * Interactive chat interface with data fetching.
 * Container component that loads messages for an account and provides interactive chat UI.
 */
export function ChatInterface({
  accountId,
  className = '',
  placeholder,
  showInput = true,
  showVoiceButtons = true,
  onVoiceInput,
  onVoiceMode,
}: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [submittedMessages, setSubmittedMessages] = useState<Set<string>>(new Set())
  const [submittingMessages, setSubmittingMessages] = useState<Set<string>>(new Set())

  // Load messages for account
  const loadMessages = async () => {
    try {
      setIsLoading(true)
      setError(null)

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
          'accountId',
          'sessionId',
          'procedureId',
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
              // Failed to parse metadata, leave as null
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
            accountId: msg.accountId,
            sessionId: msg.sessionId,
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

        setMessages(sortedMessages)
      }
    } catch (err) {
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

    let subscription: { unsubscribe: () => void } | null = null

    try {
      // @ts-ignore - Amplify Gen2 subscription type complexity
      subscription = client.models.ChatMessage.onCreate().subscribe({
        next: () => {
          loadMessages()
        },
        error: () => {
          // Subscription error - will retry automatically
        }
      })
    } catch (error) {
      // Failed to set up subscription - will use polling fallback
    }

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [accountId])

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

    // Create RESPONSE message
    const result = await client.models.ChatMessage.create({
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
    }, {
      selectionSet: ['id', 'parentMessageId', 'role', 'humanInteraction', 'content', 'createdAt']
    })

    // Check for errors
    if (result.errors && result.errors.length > 0) {
      throw new Error(`Failed to create RESPONSE: ${JSON.stringify(result.errors)}`)
    }

    if (!result.data) {
      throw new Error('Failed to create RESPONSE: no data returned')
    }

    // Real-time subscription will trigger reload
  }

  // Wrapped HITL handler with state management
  const handleHitlSubmit = async (message: ChatMessage, data: Record<string, any>) => {
    const messageId = message.id

    // Mark as submitting
    setSubmittingMessages(prev => new Set(prev).add(messageId))

    try {
      await handleHitlResponse(message, data)
      setSubmittedMessages(prev => new Set(prev).add(messageId))
    } catch (error) {
      // TODO: Add error state and display to user
    } finally {
      setSubmittingMessages(prev => {
        const next = new Set(prev)
        next.delete(messageId)
        return next
      })
    }
  }

  // Handle sending a new message (placeholder - not yet implemented on backend)
  const handleSendMessage = async (message: string) => {
    // TODO: Implement message sending via GraphQL mutation
    // For now, this is just a placeholder
  }

  return (
    <ChatInterfaceView
      messages={messages}
      isLoading={isLoading}
      error={error}
      className={className}
      onSendMessage={handleSendMessage}
      onVoiceInput={onVoiceInput}
      onVoiceMode={onVoiceMode}
      placeholder={placeholder}
      onHitlSubmit={handleHitlSubmit}
      submittedMessages={submittedMessages}
      submittingMessages={submittingMessages}
      showInput={showInput}
      showVoiceButtons={showVoiceButtons}
    />
  )
}

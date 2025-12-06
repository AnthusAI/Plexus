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

  // Load messages for account
  const loadMessages = async () => {
    try {
      setIsLoading(true)
      setError(null)

      console.log('[ChatInterface] Loading messages for account:', accountId)

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
        console.log('[ChatInterface] Raw response data:', response.data)

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
              console.error('[ChatInterface] Failed to parse metadata:', e)
              parsedMetadata = null
            }
          }

          console.log('[ChatInterface] Processing message:', {
            id: msg.id,
            content: msg.content,
            metadata: parsedMetadata,
            humanInteraction: msg.humanInteraction
          })

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

        console.log('[ChatInterface] Loaded messages:', sortedMessages.length, sortedMessages)
        setMessages(sortedMessages)
      }
    } catch (err) {
      console.error('[ChatInterface] Error loading messages:', err)
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

    console.log('[ChatInterface] Setting up real-time subscription')

    let subscription: { unsubscribe: () => void } | null = null

    try {
      // @ts-ignore - Amplify Gen2 subscription type complexity
      subscription = client.models.ChatMessage.onCreate().subscribe({
        next: () => {
          console.log('[ChatInterface] New message notification received')
          loadMessages()
        },
        error: (err: any) => {
          console.error('[ChatInterface] Subscription error:', err)
        }
      })
    } catch (error) {
      console.error('[ChatInterface] Failed to set up subscription:', error)
    }

    return () => {
      if (subscription) {
        console.log('[ChatInterface] Unsubscribing from messages')
        subscription.unsubscribe()
      }
    }
  }, [accountId])

  // Handle sending a new message (placeholder - not yet implemented on backend)
  const handleSendMessage = async (message: string) => {
    console.log('[ChatInterface] Send message:', message)
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
      showInput={showInput}
      showVoiceButtons={showVoiceButtons}
    />
  )
}

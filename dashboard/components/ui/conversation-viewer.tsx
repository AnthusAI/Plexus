"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { getClient } from '@/utils/data-operations'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { 
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  Terminal,
  Clock,
  PanelLeftOpen,
  PanelLeftClose,
  MoreHorizontal,
  Trash2,
  ChevronRight
} from "lucide-react"
import { Timestamp } from "@/components/ui/timestamp"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'

const client = generateClient<Schema>()

// Types for the conversation data
export interface ChatMessage {
  id: string
  content: string
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'
  toolName?: string
  toolParameters?: any
  toolResponse?: any
  createdAt: string
  sequenceNumber?: number
  sessionId?: string
}

export interface ChatSession {
  id: string
  name?: string
  category?: string
  status?: 'ACTIVE' | 'COMPLETED' | 'ERROR'
  createdAt: string
  updatedAt?: string
  messageCount?: number
}

export interface ConversationViewerProps {
  // Data props (for manual data passing - legacy)
  sessions?: ChatSession[]
  messages?: ChatMessage[]
  selectedSessionId?: string
  onSessionSelect?: (sessionId: string) => void
  onSessionDelete?: (sessionId: string) => void
  onSessionCountChange?: (count: number) => void
  className?: string
  
  // OR automatic data loading (recommended)
  experimentId?: string
}

// Helper function to format JSON with proper newlines
const formatJsonWithNewlines = (obj: any): string => {
  // If the object has a 'result' field that's a string, try to parse it as JSON
  if (obj && typeof obj === 'object' && obj.result && typeof obj.result === 'string') {
    try {
      const parsedResult = JSON.parse(obj.result)
      // Create a new object with the parsed result
      const newObj = { ...obj, result: parsedResult }
      const jsonString = JSON.stringify(newObj, null, 2)
      return jsonString.replace(/\\n/g, '\n')
    } catch (e) {
      // If parsing fails, fall back to original behavior
      const jsonString = JSON.stringify(obj, null, 2)
      return jsonString.replace(/\\n/g, '\n')
    }
  }
  
  const jsonString = JSON.stringify(obj, null, 2)
  // Convert literal \n escape sequences to actual newlines
  return jsonString.replace(/\\n/g, '\n')
}

// Collapsible text component with Markdown support for long messages
function CollapsibleText({ 
  content, 
  maxLines = 10, 
  className = "whitespace-pre-wrap break-words",
  enableMarkdown = true
}: { 
  content: string, 
  maxLines?: number,
  className?: string,
  enableMarkdown?: boolean
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const lines = content.split('\n')
  const shouldTruncate = lines.length > maxLines
  const displayContent = shouldTruncate && !isExpanded 
    ? lines.slice(0, maxLines).join('\n') + '...'
    : content

  const renderContent = (text: string) => {
    if (!enableMarkdown) {
      return <p className={className}>{text}</p>
    }

    return (
      <div className={`max-w-none ${className}`} style={{lineHeight: 1}}>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkBreaks]}
          components={{
            p: ({ children }: { children?: React.ReactNode }) => {
              // Hide empty paragraphs that cause spacing
              if (!children || (typeof children === 'string' && children.trim() === '')) {
                return null;
              }
              return <p className="mb-0 last:mb-0 leading-tight" style={{lineHeight: '1.2', margin: 0, padding: 0, display: 'block'}}>{children}</p>;
            },
            ul: ({ children }: { children?: React.ReactNode }) => <ul className="mb-0 ml-4 list-disc leading-tight" style={{lineHeight: '1', margin: 0, padding: 0}}>{children}</ul>,
            ol: ({ children }: { children?: React.ReactNode }) => <ol className="mb-0 ml-4 list-decimal leading-tight" style={{lineHeight: '1', margin: 0, padding: 0}}>{children}</ol>,
            li: ({ children }: { children?: React.ReactNode }) => <li className="mb-0 leading-tight" style={{lineHeight: '1', margin: 0, padding: 0}}>{children}</li>,
            strong: ({ children }: { children?: React.ReactNode }) => <strong className="font-semibold text-foreground">{children}</strong>,
            em: ({ children }: { children?: React.ReactNode }) => <em className="italic">{children}</em>,
            code: ({ children }: { children?: React.ReactNode }) => <code className="bg-card px-1 py-0.5 rounded-md text-xs font-mono">{children}</code>,
            pre: ({ children }: { children?: React.ReactNode }) => <pre className="bg-card p-3 rounded-md overflow-x-auto text-sm font-mono">{children}</pre>,
            h1: ({ children }: { children?: React.ReactNode }) => <h1 className="text-lg font-semibold text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h1>,
            h2: ({ children }: { children?: React.ReactNode }) => <h2 className="text-base font-semibold text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h2>,
            h3: ({ children }: { children?: React.ReactNode }) => <h3 className="text-sm font-medium text-foreground" style={{margin: 0, padding: 0, lineHeight: 1}}>{children}</h3>,
            blockquote: ({ children }: { children?: React.ReactNode }) => <blockquote className="border-l-4 border-muted-foreground/20 pl-4 italic text-muted-foreground mb-0 leading-tight">{children}</blockquote>,
            a: ({ children, href }: { children?: React.ReactNode; href?: string }) => <a href={href} className="text-blue-600 hover:text-blue-800 underline" target="_blank" rel="noopener noreferrer">{children}</a>,
            table: ({ children }: { children?: React.ReactNode }) => <table className="border-collapse border border-border text-sm">{children}</table>,
            th: ({ children }: { children?: React.ReactNode }) => <th className="border border-border px-2 py-1 bg-muted font-medium text-left">{children}</th>,
            td: ({ children }: { children?: React.ReactNode }) => <td className="border border-border px-2 py-1">{children}</td>,
            hr: () => <hr className="my-4 border-border" />,
            br: () => <br style={{margin: 0, padding: 0, lineHeight: 0}} />,
          }}
        >
          {text}
        </ReactMarkdown>
      </div>
    )
  }

  if (!shouldTruncate) {
    return renderContent(content)
  }

  return (
    <div>
      {renderContent(displayContent)}
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsExpanded(!isExpanded)}
        className="mt-2 p-0 h-auto text-xs text-muted-foreground hover:text-foreground"
      >
        {isExpanded ? 'Show less' : `Show more (${lines.length - maxLines} more lines)`}
      </Button>
    </div>
  )
}

// Message type icons and colors
const getMessageIcon = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') {
    return <Wrench className="h-4 w-4 text-blue-500" />
  }
  if (messageType === 'TOOL_RESPONSE') {
    return <Terminal className="h-4 w-4 text-green-600" />
  }
  
  switch (role) {
    case 'SYSTEM':
      return <Settings className="h-4 w-4 text-purple-600" />
    case 'ASSISTANT':
      return <Bot className="h-4 w-4 text-blue-600" />
    case 'USER':
      return <User className="h-4 w-4 text-green-600" />
    case 'TOOL':
      return <Terminal className="h-4 w-4 text-orange-600" />
    default:
      return <MessageSquare className="h-4 w-4 text-muted-foreground" />
  }
}

const getMessageTypeColor = (role?: string, messageType?: string) => {
  if (messageType === 'TOOL_CALL') return 'bg-blue-100 text-blue-800'
  if (messageType === 'TOOL_RESPONSE') return 'bg-green-100 text-green-800'
  
  switch (role) {
    case 'SYSTEM':
      return 'bg-purple-100 text-purple-800'
    case 'ASSISTANT':
      return 'bg-blue-100 text-blue-800'
    case 'USER':
      return 'bg-green-100 text-green-800'
    case 'TOOL':
      return 'bg-orange-100 text-orange-800'
    default:
      return 'bg-gray-100 text-gray-800'
  }
}

function ConversationViewer({ 
  sessions: propSessions, 
  messages: propMessages, 
  selectedSessionId: propSelectedSessionId,
  onSessionSelect,
  onSessionDelete,
  onSessionCountChange,
  className = "",
  experimentId
}: ConversationViewerProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true)
  
  // Internal state for data loading mode
  const [internalSessions, setInternalSessions] = useState<ChatSession[]>([])
  const [internalMessages, setInternalMessages] = useState<ChatMessage[]>([])
  const [internalSelectedSessionId, setInternalSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(false)
  
  // Ref for the messages container to handle auto-scrolling
  const messagesContainerRef = React.useRef<HTMLDivElement>(null)

  // Function to scroll to the most recent message
  const scrollToLatestMessage = React.useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return

    // Find the last message element
    const messageElements = container.querySelectorAll('[data-message-id]')
    const lastMessageElement = messageElements[messageElements.length - 1] as HTMLElement
    
    if (lastMessageElement) {
      // Calculate the scroll position to show the top of the last message at the top of the container
      const containerRect = container.getBoundingClientRect()
      const messageRect = lastMessageElement.getBoundingClientRect()
      const scrollTop = container.scrollTop + (messageRect.top - containerRect.top)
      
      // Smooth scroll to the calculated position
      container.scrollTo({
        top: scrollTop,
        behavior: 'smooth'
      })
    }
  }, [])

  // Determine which data source to use
  const sessions = propSessions || internalSessions
  const messages = propMessages || internalMessages  
  const selectedSessionId = propSelectedSessionId || internalSelectedSessionId
  
  // Notify parent of session count changes
  useEffect(() => {
    if (onSessionCountChange) {
      onSessionCountChange(sessions.length)
    }
  }, [sessions.length, onSessionCountChange])
  
  const handleSessionSelect = (sessionId: string) => {
    if (onSessionSelect) {
      onSessionSelect(sessionId)
    } else {
      setInternalSelectedSessionId(sessionId)
    }
  }

  // Data loading effect for experimentId mode
  useEffect(() => {
    if (!experimentId) return

    const loadConversationData = async () => {
      try {
        setIsLoading(true)
        
        // Load chat sessions for the procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: experimentId,
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
          
          setInternalSessions(sortedSessions)
          
          if (sortedSessions.length > 0) {
            // Select the most recent session (first in sorted array)
            setInternalSelectedSessionId(sortedSessions[0].id)
          }
        }

        // Load ALL messages for this experiment with proper pagination
        let allMessages: any[] = []
        let nextToken: string | null = null
        
        do {
          const response: { data?: any[], nextToken?: string } = await (client.models.ChatMessage.listChatMessageByProcedureIdAndCreatedAt as any)({
            procedureId: experimentId,
            limit: 1000,
            nextToken,
          }, {
            selectionSet: [
              'id',
              'content', 
              'role',
              'messageType',
              'toolName',
              'toolParameters',
              'toolResponse',
              'createdAt',
              'sequenceNumber',
              'sessionId'
            ]
          })
          
          if (response?.data) {
            allMessages = [...allMessages, ...response.data]
          }
          
          nextToken = response.nextToken || null
        } while (nextToken)

        if (allMessages.length > 0) {
          const formattedMessages: ChatMessage[] = allMessages.map((msg: any) => {
            
            // Parse tool call data from content if structured fields are missing
            let parsedToolName = msg.toolName
            let parsedToolParameters = msg.toolParameters ? JSON.parse(msg.toolParameters) : undefined
            
            if (msg.messageType === 'TOOL_CALL' && !msg.toolName && msg.content) {
              // Parse tool call from content string like: "plexus_feedback_find({'scorecard_name': 'SelectQuote HCS Medium-Risk', ...})"
              const toolCallMatch = msg.content.match(/^([^(]+)\((.+)\)$/s)
              if (toolCallMatch) {
                parsedToolName = toolCallMatch[1].trim()
                try {
                  // Convert Python-style dict to JSON and parse
                  const pythonDict = toolCallMatch[2]
                  const jsonString = pythonDict
                    .replace(/'/g, '"')  // Convert single quotes to double quotes
                    .replace(/True/g, 'true')  // Convert Python booleans
                    .replace(/False/g, 'false')
                    .replace(/None/g, 'null')
                  parsedToolParameters = JSON.parse(jsonString)
                } catch (e) {
                  console.warn('Failed to parse tool parameters from content:', e)
                }
              }
            }
            
            return {
              id: msg.id,
              content: msg.content || '',
              role: msg.role as 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL',
              messageType: msg.messageType as 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE',
              toolName: parsedToolName,
              toolParameters: parsedToolParameters,
              toolResponse: msg.toolResponse ? JSON.parse(msg.toolResponse) : undefined,
              createdAt: msg.createdAt,
              sequenceNumber: msg.sequenceNumber,
              sessionId: msg.sessionId
            }
          })
          
          // Sort all messages by sequence number and creation time
          const sortedMessages = formattedMessages.sort((a, b) => {
            if (a.sequenceNumber && b.sequenceNumber) {
              return a.sequenceNumber - b.sequenceNumber
            }
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          })
          
          setInternalMessages(sortedMessages)
          
          // Update session message counts
          const sessionCounts = sortedMessages.reduce((acc: Record<string, number>, msg: any) => {
            acc[msg.sessionId] = (acc[msg.sessionId] || 0) + 1
            return acc
          }, {})
          
          setInternalSessions(prev => prev.map(session => ({
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

  // Real-time subscription for new chat sessions - notification-based pattern
  useEffect(() => {
    if (!experimentId) return

    console.log('Setting up chat session notification subscription for experiment:', experimentId)

    const checkForNewSessions = async () => {
      try {
        console.log('Checking for new chat sessions in experiment:', experimentId)
        
        // Query for sessions in the current procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: experimentId,
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
          
          // Check if we have new sessions compared to current state
          setInternalSessions(prevSessions => {
            const currentIds = new Set(prevSessions.map(s => s.id))
            const newSessions = sortedSessions.filter(s => !currentIds.has(s.id))
            
            if (newSessions.length > 0) {
              console.log(`Found ${newSessions.length} new chat sessions in experiment`)
              
              // Auto-select the newest session when new sessions are created
              if (sortedSessions.length > 0) {
                const newestSession = sortedSessions[0]
                console.log('Auto-selecting newest session:', newestSession.id)
                
                // Use handleSessionSelect to properly manage both internal and external session selection
                if (onSessionSelect) {
                  onSessionSelect(newestSession.id)
                } else {
                  setInternalSelectedSessionId(newestSession.id)
                }
              }
              
              return sortedSessions // Replace with complete sorted list
            }
            
            return prevSessions // No changes
          })
        }
      } catch (error) {
        console.error('Error checking for new chat sessions:', error)
      }
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      const subscription = getClient().models.ChatSession.onCreate().subscribe({
        next: (param: any) => {
          console.log('Chat session notification received - checking for updates')
          console.log('Subscription param:', param)
          // Don't rely on the subscription data, just use it as a notification
          checkForNewSessions()
        },
        error: (error: Error) => {
          console.error('Chat session subscription error:', error)
        }
      })

      return () => {
        console.log('Unsubscribing from chat session notification')
        subscription.unsubscribe()
      }
    } catch (error) {
      console.error('Error setting up chat session notification:', error)
    }
  }, [experimentId, onSessionSelect])

  // Real-time subscription for new chat messages - notification-based pattern
  useEffect(() => {
    if (!experimentId) return

    console.log('Setting up chat message notification subscription for experiment:', experimentId)

    const checkForNewMessages = async () => {
      try {
        console.log('Checking for new messages in experiment')
        
        // Load ALL messages for this experiment with proper pagination
        let allMessages: any[] = []
        let nextToken: string | null = null
        
        do {
          const response: { data?: any[], nextToken?: string } = await (client.models.ChatMessage.listChatMessageByProcedureIdAndCreatedAt as any)({
            procedureId: experimentId,
            limit: 1000,
            nextToken,
          }, {
            selectionSet: [
              'id',
              'content', 
              'role',
              'messageType',
              'toolName',
              'toolParameters',
              'toolResponse',
              'createdAt',
              'sequenceNumber',
              'sessionId'
            ]
          })
          
          if (response?.data) {
            allMessages = [...allMessages, ...response.data]
          }
          
          nextToken = response.nextToken || null
        } while (nextToken)

        const messagesData = allMessages

        console.log('Raw messagesData received:', messagesData?.length || 0, 'messages')
        
        if (messagesData) {
          const formattedMessages: ChatMessage[] = messagesData.map((msg: any) => {
            // Parse tool call data from content if structured fields are missing
            let parsedToolName = msg.toolName
            let parsedToolParameters = msg.toolParameters ? JSON.parse(msg.toolParameters) : undefined
            
            if (msg.messageType === 'TOOL_CALL' && !msg.toolName && msg.content) {
              // Parse tool call from content string
              const toolCallMatch = msg.content.match(/^([^(]+)\((.+)\)$/s)
              if (toolCallMatch) {
                parsedToolName = toolCallMatch[1].trim()
                try {
                  const pythonDict = toolCallMatch[2]
                  const jsonString = pythonDict
                    .replace(/'/g, '"')
                    .replace(/True/g, 'true')
                    .replace(/False/g, 'false')
                    .replace(/None/g, 'null')
                  parsedToolParameters = JSON.parse(jsonString)
                } catch (e) {
                  console.warn('Failed to parse tool parameters:', e)
                }
              }
            }
            
            return {
              id: msg.id,
              content: msg.content || '',
              role: msg.role as 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL',
              messageType: msg.messageType as 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE',
              toolName: parsedToolName,
              toolParameters: parsedToolParameters,
              toolResponse: msg.toolResponse ? JSON.parse(msg.toolResponse) : undefined,
              createdAt: msg.createdAt,
              sequenceNumber: msg.sequenceNumber,
              sessionId: msg.sessionId
            }
          })
          
          // Sort messages by sequence number and creation time
          const sortedMessages = formattedMessages.sort((a, b) => {
            if (a.sequenceNumber && b.sequenceNumber) {
              return a.sequenceNumber - b.sequenceNumber
            }
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          })
          
          // Check if we have new messages compared to current state
          setInternalMessages(prevMessages => {
            console.log('Current state has', prevMessages.length, 'messages')
            console.log('Query returned', sortedMessages.length, 'messages')
            const currentIds = new Set(prevMessages.map(m => m.id))
            const newMessages = sortedMessages.filter(m => !currentIds.has(m.id))
            console.log('Detected', newMessages.length, 'new messages')
            
            if (newMessages.length > 0) {
              console.log(`Found ${newMessages.length} new messages in experiment`)
              
              // Auto-scroll to the latest message after a brief delay to ensure DOM has updated
              setTimeout(() => {
                scrollToLatestMessage()
              }, 100)
              
              return sortedMessages // Replace with complete sorted list
            }
            
            return prevMessages // No changes
          })
        } else {
          console.log('No messagesData returned from GraphQL query')
        }
      } catch (error) {
        console.error('Error checking for new messages:', error)
      }
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      const subscription = getClient().models.ChatMessage.onCreate().subscribe({
        next: (param: any) => {
          console.log('Chat message notification received - checking for updates')
          console.log('Subscription param:', param)
          // Don't rely on the subscription data, just use it as a notification
          checkForNewMessages()
        },
        error: (error: Error) => {
          console.error('Chat message subscription error:', error)
        }
      })

      // Also check for new messages when the subscription is first set up
      checkForNewMessages()

      return () => {
        console.log('Unsubscribing from chat message notification')
        subscription.unsubscribe()
      }
    } catch (error) {
      console.error('Error setting up chat message notification:', error)
    }
  }, [experimentId, scrollToLatestMessage])
  
  // Sort sessions by last update date in reverse chronological order (most recent first)
  const sortedSessions = [...sessions].sort((a, b) => {
    const aTime = new Date(a.updatedAt || a.createdAt).getTime()
    const bTime = new Date(b.updatedAt || b.createdAt).getTime()
    return bTime - aTime
  })
  
  // Filter messages for selected session
  const filteredMessages = selectedSessionId 
    ? messages.filter(msg => (msg as any).sessionId === selectedSessionId)
    : messages
  
  // Sort messages by sequence number or creation date
  const sortedMessages = [...filteredMessages].sort((a, b) => {
    if (a.sequenceNumber && b.sequenceNumber) {
      return a.sequenceNumber - b.sequenceNumber
    }
    return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
  })
  
  // Get the current selected session
  const selectedSession = selectedSessionId ? sessions.find(s => s.id === selectedSessionId) : null

  // Show loading state when loading data in experimentId mode
  if (isLoading && experimentId) {
    return (
      <div className={`flex h-full bg-background ${className} items-center justify-center`}>
        <div className="text-muted-foreground">Loading conversation...</div>
      </div>
    )
  }

  return (
    <div className={`flex h-full bg-background ${className}`}>
      {/* Left Sidebar - Session List */}
      <div className={`${isSidebarCollapsed ? 'w-12' : 'w-80'} transition-all duration-200 border-r border-border flex flex-col`}>
        {/* Sidebar Header */}
        <div className="p-3 border-b border-border flex items-center justify-between">
          {!isSidebarCollapsed && (
            <h3 className="text-sm font-medium">Chat Sessions ({sortedSessions.length})</h3>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            className="h-8 w-8 p-0"
          >
            {isSidebarCollapsed ? (
              <PanelLeftOpen className="h-4 w-4" />
            ) : (
              <PanelLeftClose className="h-4 w-4" />
            )}
          </Button>
        </div>
        
        {/* Session List */}
        {!isSidebarCollapsed && (
          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sortedSessions.map((session) => (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => handleSessionSelect(session.id)}
                className="w-full justify-start text-left p-2 h-auto"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <MessageSquare className="h-4 w-4 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium truncate">
                      {session.name || session.category || `Session ${session.id.slice(0, 8)}`}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {session.messageCount ? `${session.messageCount} messages` : 'No messages'}
                    </div>
                  </div>
                  {session.status && (
                    <Badge 
                      variant="outline"
                      className={`text-xs ${
                        session.status === 'COMPLETED' 
                          ? 'bg-green-100 text-green-800' 
                          : session.status === 'ERROR' 
                          ? 'bg-red-100 text-red-800' 
                          : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {session.status}
                    </Badge>
                  )}
                </div>
              </Button>
            ))}
          </div>
        )}
        
        {/* Collapsed Sidebar Content */}
        {isSidebarCollapsed && (
          <div className="flex-1 p-2 space-y-2">
            {sortedSessions.slice(0, 5).map((session) => (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => handleSessionSelect(session.id)}
                className="w-full h-8 p-0"
                title={session.name || session.category || `Session ${session.id.slice(0, 8)}`}
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Main Content - Messages */}
      <div className="flex-1 flex flex-col">
        {/* Session Header */}
        {selectedSession && (
          <div className="border-b border-border p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="h-5 w-5 text-muted-foreground" />
                <div>
                  <h3 className="font-medium text-sm">
                    {selectedSession.name || selectedSession.category || `Session ${selectedSession.id.slice(0, 8)}`}
                  </h3>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mt-1">
                    {selectedSession.status && (
                      <Badge 
                        variant="outline"
                        className={`text-xs ${
                          selectedSession.status === 'COMPLETED' 
                            ? 'bg-green-100 text-green-800' 
                            : selectedSession.status === 'ERROR' 
                            ? 'bg-red-100 text-red-800' 
                            : 'bg-blue-100 text-blue-800'
                        }`}
                      >
                        {selectedSession.status}
                      </Badge>
                    )}
                    <span>
                      {selectedSession.messageCount ? `${selectedSession.messageCount} messages` : 'No messages'}
                    </span>
                    <span>•</span>
                    <Timestamp time={selectedSession.createdAt} variant="relative" showIcon={false} />
                  </div>
                </div>
              </div>
              
              {/* Action Dropdown */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8 rounded-md border-0 shadow-none bg-border"
                    aria-label="More options"
                  >
                    <MoreHorizontal className="h-4 w-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem 
                    onSelect={() => {
                      if (onSessionDelete) {
                        onSessionDelete(selectedSession.id);
                      }
                    }}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        )}
        
        {/* Messages List */}
        <div ref={messagesContainerRef} className="flex-1 overflow-y-auto p-3">
          {!selectedSessionId ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>Select a chat session to view messages</p>
              </div>
            </div>
          ) : sortedMessages.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              <div className="text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No messages in this session</p>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {sortedMessages.map((message) => (
                <div key={message.id} data-message-id={message.id} className="flex items-start gap-3">
                  <div className="flex-shrink-0 mt-1">
                    {getMessageIcon(message.role, message.messageType)}
                  </div>
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <Badge 
                        variant="secondary" 
                        className={`text-xs ${getMessageTypeColor(message.role, message.messageType)}`}
                      >
                        {message.messageType === 'TOOL_CALL' ? 'Tool Call' :
                         message.messageType === 'TOOL_RESPONSE' ? 'Tool Response' :
                         message.role === 'SYSTEM' ? 'System' :
                         message.role === 'ASSISTANT' ? 'Assistant' :
                         message.role === 'USER' ? 'User' :
                         message.role === 'TOOL' ? 'Tool' :
                         message.messageType || message.role || 'Message'}
                      </Badge>
                      
                      {message.toolName && (
                        <Badge variant="outline" className="text-xs">
                          {message.toolName}
                        </Badge>
                      )}
                      
                      <div className="flex items-center gap-1 text-xs text-muted-foreground ml-auto">
                        <Clock className="h-3 w-3" />
                        <Timestamp time={message.createdAt} variant="relative" showIcon={false} />
                      </div>
                    </div>
                    
                    {/* Tool call parameters display - primary for tool calls */}
                    {message.messageType === 'TOOL_CALL' && message.toolParameters ? (
                      <div>
                        <div className="bg-card rounded-md p-3">
                          {message.toolName && (
                            <h4 className="font-semibold text-sm mb-2 text-foreground">{message.toolName}</h4>
                          )}
                          <div className="space-y-1">
                            {Object.entries(message.toolParameters).map(([key, value]) => (
                              <div key={key} className="grid grid-cols-3 gap-2 text-xs">
                                <div className="font-medium text-muted-foreground">{key}:</div>
                                <div className="col-span-2 font-mono text-foreground break-words">
                                  {typeof value === 'string' ? value : JSON.stringify(value)}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                        
                        {/* Raw tool call - collapsible */}
                        <div className="mt-3">
                          <Collapsible>
                            <CollapsibleTrigger asChild>
                              <Button
                                variant="ghost"
                                size="sm"
                                className="h-auto p-0 text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
                              >
                                <ChevronRight className="h-3 w-3" />
                                Raw
                              </Button>
                            </CollapsibleTrigger>
                            <CollapsibleContent>
                              <div className="mt-2 text-sm font-mono">
                                <CollapsibleText content={message.content} maxLines={10} />
                              </div>
                            </CollapsibleContent>
                          </Collapsible>
                        </div>
                      </div>
                    ) : message.messageType === 'TOOL_RESPONSE' ? (
                      // Don't show plain text content for tool responses - only show the formatted response card below
                      null
                    ) : (
                      <div className="text-sm">
                        <CollapsibleText content={message.content} maxLines={10} />
                      </div>
                    )}
                    
                    {/* Tool response display */}
                    {message.messageType === 'TOOL_RESPONSE' && message.toolResponse && (
                      <div className="mt-3">
                        <div className="bg-card rounded-md p-3 text-xs">
                          <div className="font-mono">
                            <CollapsibleText 
                              content={formatJsonWithNewlines(message.toolResponse)} 
                              maxLines={12}
                              className="whitespace-pre-wrap break-words font-mono"
                              enableMarkdown={false}
                            />
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ConversationViewer
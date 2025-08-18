"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { 
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  ChevronDown,
  ChevronRight,
  Clock,
  AlertCircle
} from "lucide-react"
import { Timestamp } from "@/components/ui/timestamp"
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"

// Types based on our GraphQL schema
type ChatMessage = Schema['ChatMessage']['type']
type ChatSession = Schema['ChatSession']['type']

interface ChatMessageWithDetails {
  id: string
  sessionId: string
  experimentId: string
  role: string
  content: string
  messageType?: string
  toolName?: string
  toolParameters?: string
  toolResponse?: string
  parentMessageId?: string
  sequenceNumber?: number
  createdAt: string
  updatedAt: string
  parentMessage?: ChatMessageWithDetails
  childMessages?: ChatMessageWithDetails[]
}

const client = generateClient<Schema>()

// Collapsible text component for long messages
function CollapsibleText({ 
  content, 
  maxLines = 10, 
  className = "whitespace-pre-wrap break-words" 
}: { 
  content: string, 
  maxLines?: number,
  className?: string 
}) {
  const [isExpanded, setIsExpanded] = useState(false)
  const lines = content.split('\n')
  const shouldTruncate = lines.length > maxLines
  const displayContent = shouldTruncate && !isExpanded 
    ? lines.slice(0, maxLines).join('\n') + '...'
    : content

  if (!shouldTruncate) {
    return <p className={className}>{content}</p>
  }

  return (
    <div>
      <p className={className}>{displayContent}</p>
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
    return <Settings className="h-4 w-4 text-green-500" />
  }
  
  switch (role) {
    case 'USER':
      return <User className="h-4 w-4 text-purple-500" />
    case 'ASSISTANT':
      return <Bot className="h-4 w-4 text-blue-500" />
    case 'SYSTEM':
      return <Settings className="h-4 w-4 text-orange-500" />
    case 'TOOL':
      return <Wrench className="h-4 w-4 text-green-500" />
    default:
      return <MessageSquare className="h-4 w-4 text-gray-500" />
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

interface Props {
  experimentId: string
}

export default function ExperimentChatMessages({ experimentId }: Props) {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [messages, setMessages] = useState<ChatMessageWithDetails[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null)

  // Load chat sessions for the experiment
  useEffect(() => {
    const loadChatSessions = async () => {
      if (!experimentId) {
        setIsLoading(false)
        return
      }

      try {
        setIsLoading(true)
        setError(null)
        
        console.log('ExperimentChatMessages: Loading sessions for experiment ID:', experimentId)
        
        // Query chat sessions for this experiment using GSI
        const { data: sessionsData, errors } = await (client.models.ChatSession.listChatSessionByExperimentIdAndCreatedAt as any)({
          experimentId: experimentId,
          limit: 100  // Reasonable limit for sessions
        })

        console.log('ExperimentChatMessages: Sessions response:', { sessionsData, errors })

        if (errors) {
          console.error('GraphQL errors loading chat sessions:', errors)
          setError('Failed to load chat sessions: ' + errors.map(e => e.message).join(', '))
          return
        }

        if (!sessionsData || sessionsData.length === 0) {
          console.log('ExperimentChatMessages: No sessions found for experiment', experimentId)
          setSessions([])
          setMessages([])
          setIsLoading(false)
          return
        }

        console.log('ExperimentChatMessages: Found', sessionsData.length, 'sessions')
        setSessions(sessionsData as any[])
        
        // Load ALL messages for this experiment using the GSI
        await loadAllMessagesForExperiment()
        
        // Set the first session as selected by default
        if (sessionsData.length > 0) {
          const firstSession = sessionsData[0] as any
          setSelectedSessionId(firstSession.id)
        }
        
      } catch (err) {
        console.error('Error loading chat sessions:', err)
        setError(err instanceof Error ? err.message : 'Failed to load chat sessions')
      } finally {
        setIsLoading(false)
      }
    }

    loadChatSessions()
  }, [experimentId])

  const loadAllMessagesForExperiment = async () => {
    try {
      console.log('Loading ALL messages for experiment:', experimentId)
      
      // Use the experimentId GSI to get all messages for this experiment  
      const result = await (client.models.ChatMessage.listChatMessageByExperimentIdAndCreatedAt as any)({
        experimentId: experimentId,
        limit: 1000  // Set a reasonable limit to get all messages
      })
      
      const messagesData = result?.data
      const errors = result?.errors

      if (errors) {
        console.error('GraphQL errors loading messages:', errors)
        setError('Failed to load messages: ' + errors.map(e => e.message).join(', '))
        return
      }

      if (messagesData) {
        // Sort all messages by session and then by sequence number
        const sortedMessages = (messagesData as any[]).sort((a: any, b: any) => {
          // First sort by sessionId to group messages
          if (a.sessionId !== b.sessionId) {
            return a.sessionId.localeCompare(b.sessionId)
          }
          // Then sort by sequence number within each session
          return (a.sequenceNumber || 0) - (b.sequenceNumber || 0)
        })
        
        console.log('Loaded', sortedMessages.length, 'total messages for experiment', experimentId)
        console.log('Sample message:', sortedMessages[0])
        console.log('All session IDs:', [...new Set(sortedMessages.map(m => m.sessionId))])
        setMessages(sortedMessages)
      }
      
    } catch (err) {
      console.error('Error loading messages:', err)
      setError(err instanceof Error ? err.message : 'Failed to load messages')
    }
  }

  const handleSessionSelect = async (sessionId: string) => {
    setSelectedSessionId(sessionId)
    // No need to reload messages since we already have all messages loaded
    // The UI will automatically filter based on selectedSessionId
  }

  if (isLoading) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          Chat Messages
        </h3>
        <Card className="bg-background border-none">
          <CardContent className="p-4">
            <div className="animate-pulse space-y-2">
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4"></div>
              <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2"></div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          Chat Messages
        </h3>
        <Card className="bg-background border-none">
          <CardContent className="p-4">
            <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <AlertCircle className="h-4 w-4" />
              <span>Error: {error}</span>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="space-y-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          Chat Messages
        </h3>
        <Card className="bg-background border-none">
          <CardContent className="p-6 text-center">
            <MessageSquare className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            <p className="text-muted-foreground">No chat sessions found</p>
            <p className="text-sm text-muted-foreground mt-1">
              Messages will appear here when AI agents run experiments
            </p>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold flex items-center gap-2">
        <MessageSquare className="h-5 w-5" />
        Chat Messages ({messages.length} message{messages.length !== 1 ? 's' : ''}, {sessions.length} session{sessions.length !== 1 ? 's' : ''})
      </h3>
      
      {/* Session selector if multiple sessions */}
      {sessions.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {sessions.map((session, index) => {
            const sessionMessageCount = messages.filter((msg: any) => msg.sessionId === session.id).length
            return (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "default" : "outline"}
                size="sm"
                onClick={() => handleSessionSelect(session.id)}
                className="text-xs"
              >
                Session {index + 1} ({sessionMessageCount} msg{sessionMessageCount !== 1 ? 's' : ''})
                <Badge 
                  variant="secondary" 
                  className={`ml-2 text-xs ${session.status === 'COMPLETED' ? 'bg-green-100 text-green-800' : session.status === 'ERROR' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}
                >
                  {session.status}
                </Badge>
              </Button>
            )
          })}
        </div>
      )}
      
      {/* Messages display */}
      <div className="space-y-3">
        {(() => {
          const filteredMessages = messages.filter((message) => !selectedSessionId || message.sessionId === selectedSessionId)
          console.log('Rendering messages:', {
            totalMessages: messages.length,
            selectedSessionId,
            filteredMessages: filteredMessages.length,
            sessionIds: [...new Set(messages.map(m => m.sessionId))]
          })
          return filteredMessages
        })()
          .map((message) => (
          <Card key={message.id} className="bg-background border-none">
            <CardContent className="p-4">
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 mt-1">
                  {getMessageIcon(message.role, message.messageType)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <Badge 
                      variant="secondary" 
                      className={`text-xs ${getMessageTypeColor(message.role, message.messageType)}`}
                    >
                      {message.messageType || message.role}
                    </Badge>
                    
                    {message.toolName && (
                      <Badge variant="outline" className="text-xs">
                        {message.toolName}
                      </Badge>
                    )}
                    
                    <div className="flex items-center gap-1 text-xs text-muted-foreground ml-auto">
                      <Clock className="h-3 w-3" />
                      <Timestamp time={message.createdAt} variant="relative" />
                    </div>
                  </div>
                  
                  <div className="text-sm">
                    <CollapsibleText content={message.content} maxLines={10} />
                  </div>
                  
                  {/* Tool parameters and responses */}
                  {(message.toolParameters || message.toolResponse) && (
                    <Collapsible className="mt-3">
                      <CollapsibleTrigger asChild>
                        <Button variant="ghost" size="sm" className="p-0 h-auto text-xs text-muted-foreground hover:text-foreground">
                          <ChevronRight className="h-3 w-3 mr-1 transition-transform group-data-[state=open]:rotate-90" />
                          View {message.toolParameters ? 'parameters' : 'response'} details
                        </Button>
                      </CollapsibleTrigger>
                      <CollapsibleContent className="mt-2">
                        <div className="bg-muted rounded-md p-3 text-xs font-mono">
                          {message.toolParameters && (
                            <div className="mb-2">
                              <div className="font-semibold mb-1">Parameters:</div>
                              <div className="font-mono text-xs">
                                <CollapsibleText 
                                  content={JSON.stringify(message.toolParameters, null, 2)} 
                                  maxLines={5}
                                />
                              </div>
                            </div>
                          )}
                          {message.toolResponse && (
                            <div>
                              <div className="font-semibold mb-1">Response:</div>
                              <div className="font-mono text-xs">
                                <CollapsibleText 
                                  content={JSON.stringify(message.toolResponse, null, 2)} 
                                  maxLines={5}
                                />
                              </div>
                            </div>
                          )}
                        </div>
                      </CollapsibleContent>
                    </Collapsible>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}
"use client"
import React, { useState, useEffect } from "react"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { 
  MessageSquare, 
  User, 
  Bot, 
  Settings, 
  Wrench,
  ChevronDown, 
  ChevronRight, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Loader2,
  Expand,
  Shrink
} from "lucide-react"
import { Timestamp } from "./ui/timestamp"
import { cn } from "@/lib/utils"

const client = generateClient<Schema>()

type ChatSession = Schema['ChatSession']['type']
type ChatMessage = Schema['ChatMessage']['type']

interface ProcedureConversationViewerProps {
  procedureId: string
  onSessionCountChange?: (count: number) => void
  onFullscreenChange?: (isFullscreen: boolean) => void
  isFullscreen?: boolean
}

const ProcedureConversationViewer: React.FC<ProcedureConversationViewerProps> = ({ 
  procedureId, 
  onSessionCountChange,
  onFullscreenChange,
  isFullscreen = false
}) => {
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expandedSessions, setExpandedSessions] = useState<Set<string>>(new Set())

  useEffect(() => {
    if (procedureId) {
      loadSessions()
    }
  }, [procedureId])

  const loadSessions = async () => {
    try {
      setIsLoading(true)
      setError(null)
      
      const result = await client.graphql({
        query: `
          query ListChatSessionsByProcedureCreatedAt(
            $procedureId: ID!
            $sortDirection: ModelSortDirection
          ) {
            listChatSessionsByProcedureCreatedAt(
              procedureId: $procedureId
              sortDirection: $sortDirection
            ) {
              items {
                id
                procedureId
                nodeId
                name
                category
                status
                metadata
                createdAt
                updatedAt
              }
            }
          }
        `,
        variables: {
          procedureId,
          sortDirection: 'DESC'
        }
      })

      const fetchedSessions = (result as any).data?.listChatSessionsByProcedureCreatedAt?.items || []
      setSessions(fetchedSessions)
      
      if (onSessionCountChange) {
        onSessionCountChange(fetchedSessions.length)
      }
    } catch (err) {
      console.error('Error loading sessions:', err)
      setError(err instanceof Error ? err.message : 'Failed to load sessions')
    } finally {
      setIsLoading(false)
    }
  }

  const loadMessagesForSession = async (sessionId: string) => {
    try {
      const result = await client.graphql({
        query: `
          query ListChatMessagesBySessionSequence(
            $sessionId: ID!
            $sortDirection: ModelSortDirection
          ) {
            listChatMessagesBySessionSequence(
              sessionId: $sessionId
              sortDirection: $sortDirection
            ) {
              items {
                id
                sessionId
                procedureId
                role
                content
                metadata
                messageType
                toolName
                toolParameters
                toolResponse
                parentMessageId
                sequenceNumber
                createdAt
              }
            }
          }
        `,
        variables: {
          sessionId,
          sortDirection: 'ASC'
        }
      })

      const fetchedMessages = (result as any).data?.listChatMessagesBySessionSequence?.items || []
      setMessages(prev => ({
        ...prev,
        [sessionId]: fetchedMessages
      }))
    } catch (err) {
      console.error('Error loading messages for session:', err)
    }
  }

  const toggleSessionExpansion = async (sessionId: string) => {
    setExpandedSessions(prev => {
      const newSet = new Set(prev)
      if (newSet.has(sessionId)) {
        newSet.delete(sessionId)
      } else {
        newSet.add(sessionId)
        // Load messages when expanding
        if (!messages[sessionId]) {
          loadMessagesForSession(sessionId)
        }
      }
      return newSet
    })
  }

  const getStatusIcon = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'active':
        return <Loader2 className="h-4 w-4 text-blue-500 animate-spin" />
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />
    }
  }

  const getStatusColor = (status?: string | null) => {
    switch (status?.toLowerCase()) {
      case 'completed':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'active':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'error':
        return 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  const getRoleIcon = (role?: string | null) => {
    switch (role?.toLowerCase()) {
      case 'user':
        return <User className="h-3 w-3" />
      case 'assistant':
        return <Bot className="h-3 w-3" />
      case 'system':
        return <Settings className="h-3 w-3" />
      case 'tool':
        return <Wrench className="h-3 w-3" />
      default:
        return <MessageSquare className="h-3 w-3" />
    }
  }

  const getRoleColor = (role?: string | null) => {
    switch (role?.toLowerCase()) {
      case 'user':
        return 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
      case 'assistant':
        return 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      case 'system':
        return 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200'
      case 'tool':
        return 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200'
      default:
        return 'bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-200'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-6 w-6 animate-spin" />
        <span className="ml-2">Loading conversations...</span>
      </div>
    )
  }

  if (error) {
    return (
      <div className="text-center text-destructive p-8">
        <p>Error loading conversations: {error}</p>
        <Button onClick={loadSessions} variant="outline" className="mt-2">
          Retry
        </Button>
      </div>
    )
  }

  if (sessions.length === 0) {
    return (
      <div className="text-center text-muted-foreground p-8">
        <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>No conversations found for this procedure.</p>
      </div>
    )
  }

  return (
    <div className={cn("space-y-4", isFullscreen && "h-full overflow-y-auto")}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Conversations</h3>
          <Badge variant="outline">{sessions.length} sessions</Badge>
        </div>
        
        {onFullscreenChange && (
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onFullscreenChange(!isFullscreen)}
            className="h-8 w-8"
          >
            {isFullscreen ? <Shrink className="h-4 w-4" /> : <Expand className="h-4 w-4" />}
          </Button>
        )}
      </div>
      
      <div className="space-y-2">
        {sessions.map((session) => {
          const isExpanded = expandedSessions.has(session.id)
          const sessionMessages = messages[session.id] || []

          return (
            <Card key={session.id}>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => toggleSessionExpansion(session.id)}
                      className="h-6 w-6 p-0"
                    >
                      {isExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </Button>
                    
                    {getStatusIcon(session.status)}
                    
                    <div>
                      <h4 className="font-medium text-sm">
                        {session.name || `Session ${session.id.slice(-8)}`}
                      </h4>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="secondary" className={getStatusColor(session.status)}>
                          {session.status || 'Unknown'}
                        </Badge>
                        {session.category && (
                          <Badge variant="outline" className="text-xs">
                            {session.category}
                          </Badge>
                        )}
                        <Timestamp time={session.updatedAt} variant="relative" className="text-xs text-muted-foreground" />
                      </div>
                    </div>
                  </div>

                  {sessionMessages.length > 0 && (
                    <Badge variant="outline" className="text-xs">
                      {sessionMessages.length} messages
                    </Badge>
                  )}
                </div>
              </CardHeader>

              {isExpanded && (
                <CardContent className="pt-0">
                  {sessionMessages.length === 0 ? (
                    <div className="text-center text-muted-foreground py-4">
                      <Loader2 className="h-4 w-4 animate-spin mx-auto mb-2" />
                      <p className="text-sm">Loading messages...</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-96 overflow-y-auto">
                      {sessionMessages.map((message) => (
                        <div
                          key={message.id}
                          className="flex gap-2 p-2 rounded-md bg-muted/50"
                        >
                          <div className="flex-shrink-0">
                            <Badge variant="secondary" className={cn("text-xs", getRoleColor(message.role))}>
                              <div className="flex items-center gap-1">
                                {getRoleIcon(message.role)}
                                <span>{message.role}</span>
                              </div>
                            </Badge>
                          </div>
                          
                          <div className="flex-1 min-w-0">
                            <div className="text-sm break-words">
                              {message.messageType === 'TOOL_CALL' && message.toolName && (
                                <div className="text-xs text-muted-foreground mb-1">
                                  Tool: {message.toolName}
                                </div>
                              )}
                              <p className="whitespace-pre-wrap">{message.content}</p>
                              {message.toolParameters && (
                                <details className="mt-1">
                                  <summary className="text-xs text-muted-foreground cursor-pointer">
                                    Parameters
                                  </summary>
                                  <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-x-auto">
                                    {JSON.stringify(message.toolParameters, null, 2)}
                                  </pre>
                                </details>
                              )}
                              {message.toolResponse && (
                                <details className="mt-1">
                                  <summary className="text-xs text-muted-foreground cursor-pointer">
                                    Response
                                  </summary>
                                  <pre className="text-xs bg-muted p-2 rounded mt-1 overflow-x-auto">
                                    {JSON.stringify(message.toolResponse, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                            
                            <div className="flex items-center gap-2 mt-1">
                              <Timestamp time={message.createdAt} variant="relative" className="text-xs text-muted-foreground" />
                              {message.sequenceNumber && (
                                <span className="text-xs text-muted-foreground">
                                  #{message.sequenceNumber}
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>
    </div>
  )
}

export default ProcedureConversationViewer

"use client"
import React, { useState } from "react"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { 
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  Terminal,
  Clock,
  ChevronRight,
  ChevronLeft,
  PanelLeftOpen,
  PanelLeftClose
} from "lucide-react"
import { Timestamp } from "@/components/ui/timestamp"

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
}

export interface ChatSession {
  id: string
  name?: string
  status?: 'ACTIVE' | 'COMPLETED' | 'ERROR'
  createdAt: string
  messageCount?: number
}

export interface ConversationViewerProps {
  sessions: ChatSession[]
  messages: ChatMessage[]
  selectedSessionId?: string
  onSessionSelect?: (sessionId: string) => void
  className?: string
}

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

export function ConversationViewer({ 
  sessions, 
  messages, 
  selectedSessionId,
  onSessionSelect,
  className = ""
}: ConversationViewerProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true)
  
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

  return (
    <div className={`flex h-full bg-background ${className}`}>
      {/* Left Sidebar - Session List */}
      <div className={`${isSidebarCollapsed ? 'w-12' : 'w-80'} transition-all duration-200 border-r border-border flex flex-col`}>
        {/* Sidebar Header */}
        <div className="p-3 border-b border-border flex items-center justify-between">
          {!isSidebarCollapsed && (
            <h3 className="text-sm font-medium">Chat Sessions ({sessions.length})</h3>
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
            {sessions.map((session) => (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onSessionSelect?.(session.id)}
                className="w-full justify-start text-left p-2 h-auto"
              >
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <MessageSquare className="h-4 w-4 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium truncate">
                      {session.name || `Session ${session.id.slice(0, 8)}`}
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
            {sessions.slice(0, 5).map((session) => (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onSessionSelect?.(session.id)}
                className="w-full h-8 p-0"
                title={session.name || `Session ${session.id.slice(0, 8)}`}
              >
                <MessageSquare className="h-4 w-4" />
              </Button>
            ))}
          </div>
        )}
      </div>

      {/* Main Content - Messages */}
      <div className="flex-1 flex flex-col">
        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-4">
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
                <div key={message.id} className="flex items-start gap-3">
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
                        <Timestamp time={message.createdAt} variant="relative" showIcon={false} />
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
                          <div className="bg-muted rounded-md p-3 text-xs">
                            {message.toolParameters && (
                              <div className="mb-2">
                                <div className="font-semibold mb-1">Parameters:</div>
                                <div className="font-mono text-xs">
                                  <CollapsibleText 
                                    content={JSON.stringify(message.toolParameters, null, 2)} 
                                    maxLines={5}
                                    className="whitespace-pre-wrap break-words font-mono"
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
                                    className="whitespace-pre-wrap break-words font-mono"
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
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ConversationViewer

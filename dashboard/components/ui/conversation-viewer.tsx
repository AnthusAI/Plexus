"use client"
import React, { useState, useEffect } from "react"
import { getClient } from '@/utils/data-operations'
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
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
  ChevronRight,
  Bell,
  Info,
  AlertTriangle,
  AlertCircle,
  XCircle
} from "lucide-react"
import { Timestamp } from "@/components/ui/timestamp"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { toast } from 'sonner'
import {
  buildResponseValue,
  getControlEnvelope,
  isPendingHumanInteraction,
  mapPendingInteractionToRequestType,
  parseMessageMetadata,
} from "@/lib/procedure-hitl"

// Types for the conversation data
export interface ChatMessage {
  id: string
  content: string
  role: 'SYSTEM' | 'ASSISTANT' | 'USER' | 'TOOL'
  messageType?: 'MESSAGE' | 'TOOL_CALL' | 'TOOL_RESPONSE'
  humanInteraction?: 'INTERNAL' | 'CHAT' | 'CHAT_ASSISTANT' | 'NOTIFICATION' | 'ALERT_INFO' | 'ALERT_WARNING' | 'ALERT_ERROR' | 'ALERT_CRITICAL' | 'PENDING_APPROVAL' | 'PENDING_INPUT' | 'PENDING_REVIEW' | 'PENDING_ESCALATION' | 'RESPONSE' | 'TIMED_OUT' | 'CANCELLED'
  toolName?: string
  toolParameters?: any
  toolResponse?: any
  metadata?: any
  parentMessageId?: string
  accountId?: string
  procedureId?: string
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
  procedureId?: string
  enableHitlActions?: boolean
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

const parseJsonField = (value: unknown): any => {
  if (value === null || value === undefined) {
    return undefined
  }
  if (typeof value !== 'string') {
    return value
  }
  if (!value.trim()) {
    return undefined
  }
  try {
    return JSON.parse(value)
  } catch {
    return undefined
  }
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
const getMessageIcon = (role?: string, messageType?: string, humanInteraction?: string) => {
  // Check humanInteraction first for special message types
  if (humanInteraction === 'NOTIFICATION') {
    return <Bell className="h-4 w-4 text-blue-500" />
  }
  if (humanInteraction === 'ALERT_INFO') {
    return <Info className="h-4 w-4 text-blue-600" />
  }
  if (humanInteraction === 'ALERT_WARNING') {
    return <AlertTriangle className="h-4 w-4 text-yellow-600" />
  }
  if (humanInteraction === 'ALERT_ERROR') {
    return <AlertCircle className="h-4 w-4 text-red-600" />
  }
  if (humanInteraction === 'ALERT_CRITICAL') {
    return <XCircle className="h-4 w-4 text-red-700" />
  }
  if (humanInteraction === 'PENDING_APPROVAL' || humanInteraction === 'PENDING_INPUT' || humanInteraction === 'PENDING_REVIEW' || humanInteraction === 'PENDING_ESCALATION') {
    return <AlertTriangle className="h-4 w-4 text-yellow-600" />
  }
  if (humanInteraction === 'RESPONSE') {
    return <User className="h-4 w-4 text-green-600" />
  }

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

const getMessageTypeColor = (role?: string, messageType?: string, humanInteraction?: string) => {
  // Check humanInteraction first for special message types
  if (humanInteraction === 'NOTIFICATION') return 'bg-blue-100 text-blue-800'
  if (humanInteraction === 'ALERT_INFO') return 'bg-blue-100 text-blue-800'
  if (humanInteraction === 'ALERT_WARNING') return 'bg-yellow-100 text-yellow-800'
  if (humanInteraction === 'ALERT_ERROR') return 'bg-red-100 text-red-800'
  if (humanInteraction === 'ALERT_CRITICAL') return 'bg-red-200 text-red-900'
  if (humanInteraction === 'PENDING_APPROVAL' || humanInteraction === 'PENDING_INPUT' || humanInteraction === 'PENDING_REVIEW' || humanInteraction === 'PENDING_ESCALATION') {
    return 'bg-yellow-100 text-yellow-800'
  }
  if (humanInteraction === 'RESPONSE') return 'bg-green-100 text-green-800'

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
  experimentId,
  procedureId,
  enableHitlActions = false,
}: ConversationViewerProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true)
  
  // Internal state for data loading mode
  const [internalSessions, setInternalSessions] = useState<ChatSession[]>([])
  const [internalMessages, setInternalMessages] = useState<ChatMessage[]>([])
  const [internalSelectedSessionId, setInternalSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(false)
  const [hitlTextByMessage, setHitlTextByMessage] = useState<Record<string, string>>({})
  const [submittingMessageIds, setSubmittingMessageIds] = useState<Set<string>>(new Set())
  const [submittedMessageIds, setSubmittedMessageIds] = useState<Set<string>>(new Set())
  const [hitlSubmitErrors, setHitlSubmitErrors] = useState<Record<string, string>>({})
  
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
  
  // Use either experimentId or procedureId (they're synonymous in this context)
  const effectiveId = experimentId || procedureId
  
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

  const markSubmitting = (messageId: string, submitting: boolean) => {
    setSubmittingMessageIds(prev => {
      const next = new Set(prev)
      if (submitting) {
        next.add(messageId)
      } else {
        next.delete(messageId)
      }
      return next
    })
  }

  const enqueueProcedureRunTask = async (
    accountId: string,
    procedureIdToRun: string,
    pendingMessageId: string,
    responseMessageId: string,
    requestId: string
  ) => {
    const client = getClient()
    const nowIso = new Date().toISOString()
    const taskMetadata = {
      dispatch_mode: 'local',
      hitl_resume: {
        pending_message_id: pendingMessageId,
        response_message_id: responseMessageId,
        request_id: requestId,
        queued_at: nowIso,
      },
    }

    const { data: existingTasks } = await (client.models.Task.listTaskByAccountIdAndUpdatedAt as any)({
      accountId,
      updatedAt: { ge: '2000-01-01T00:00:00.000Z' },
      sortDirection: 'DESC',
      limit: 200,
    })

    const matchingTask = (existingTasks || []).find((task: any) => {
      const target = task?.target || ''
      return target === `procedure/${procedureIdToRun}` || target === `procedure/run/${procedureIdToRun}`
    })

    if (matchingTask) {
      const existingMetadata = parseMessageMetadata(matchingTask.metadata) || {}
      const existingResume = (existingMetadata.hitl_resume || {}) as Record<string, unknown>
      if (existingResume.response_message_id === responseMessageId || existingResume.request_id === requestId) {
        return
      }

      await (client.models.Task.update as any)({
        id: matchingTask.id,
        status: 'PENDING',
        dispatchStatus: 'PENDING',
        target: `procedure/${procedureIdToRun}`,
        command: `procedure run ${procedureIdToRun}`,
        startedAt: null,
        completedAt: null,
        workerNodeId: null,
        errorMessage: null,
        errorDetails: null,
        stdout: null,
        stderr: null,
        metadata: JSON.stringify({
          ...existingMetadata,
          ...taskMetadata,
        }),
        updatedAt: nowIso,
      })
      return
    }

    await (client.models.Task.create as any)({
      accountId,
      type: 'Procedure Run',
      status: 'PENDING',
      dispatchStatus: 'PENDING',
      target: `procedure/${procedureIdToRun}`,
      command: `procedure run ${procedureIdToRun}`,
      description: `Resume procedure ${procedureIdToRun} after HITL response`,
      metadata: JSON.stringify(taskMetadata),
      createdAt: nowIso,
      updatedAt: nowIso,
    })
  }

  const submitHitlResponse = async (
    pendingMessage: ChatMessage,
    action: string,
    inputText?: string
  ) => {
    if (!pendingMessage.sessionId || !pendingMessage.procedureId || !pendingMessage.accountId) {
      throw new Error('Missing required pending message identifiers for HITL response')
    }

    const control = getControlEnvelope(pendingMessage.metadata)
    if (!control) {
      throw new Error('Pending HITL message is missing canonical metadata.control envelope')
    }

    const messageId = pendingMessage.id
    markSubmitting(messageId, true)
    try {
      if (submittedMessageIds.has(messageId)) {
        return
      }

      const client = getClient()

      const responseValue = buildResponseValue({
        requestType: control.request_type,
        action,
        inputText,
      })
      const respondedAt = new Date().toISOString()
      const responseMetadata = {
        control: {
          request_id: control.request_id,
          procedure_id: control.procedure_id,
          request_type: control.request_type,
          response_type: mapPendingInteractionToRequestType(pendingMessage.humanInteraction),
          pending_message_id: pendingMessage.id,
          value: responseValue,
          responded_at: respondedAt,
          responder: 'dashboard-procedure-conversation',
        },
      }

      const created = await (client.models.ChatMessage.create as any)({
        accountId: pendingMessage.accountId,
        sessionId: pendingMessage.sessionId,
        procedureId: pendingMessage.procedureId,
        parentMessageId: pendingMessage.id,
        role: 'USER',
        messageType: 'MESSAGE',
        humanInteraction: 'RESPONSE',
        content: JSON.stringify({ value: responseValue }),
        metadata: JSON.stringify(responseMetadata),
        createdAt: respondedAt,
      })
      const responseMessageId = created?.data?.id
      if (!responseMessageId) {
        throw new Error('Failed to persist RESPONSE message')
      }

      await enqueueProcedureRunTask(
        pendingMessage.accountId,
        pendingMessage.procedureId,
        pendingMessage.id,
        responseMessageId,
        control.request_id
      )

      toast.success('Response submitted. Procedure resume queued.')

      setInternalMessages(prev => {
        const responseMessage: ChatMessage = {
          id: responseMessageId,
          accountId: pendingMessage.accountId,
          sessionId: pendingMessage.sessionId,
          procedureId: pendingMessage.procedureId,
          parentMessageId: pendingMessage.id,
          role: 'USER',
          messageType: 'MESSAGE',
          humanInteraction: 'RESPONSE',
          content: JSON.stringify({ value: responseValue }),
          metadata: responseMetadata,
          createdAt: respondedAt,
        }
        const deduped = prev.filter(message => message.id !== responseMessageId)
        return [...deduped, responseMessage]
      })
      setInternalSessions(prev => prev.map((session) => (
        session.id === pendingMessage.sessionId
          ? { ...session, messageCount: (session.messageCount || 0) + 1 }
          : session
      )))
      setSubmittedMessageIds(prev => new Set(prev).add(messageId))
      setHitlTextByMessage(prev => ({
        ...prev,
        [messageId]: '',
      }))
      setHitlSubmitErrors(prev => {
        const next = { ...prev }
        delete next[messageId]
        return next
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to submit response'
      toast.error(message)
      setHitlSubmitErrors(prev => ({
        ...prev,
        [messageId]: message,
      }))
      throw error
    } finally {
      markSubmitting(messageId, false)
    }
  }

  // Data loading effect for effectiveId mode
  useEffect(() => {
    if (!effectiveId) return

    const loadConversationData = async () => {
      try {
        setIsLoading(true)
        const client = getClient()
        
        // Load chat sessions for the procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: effectiveId,
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
            procedureId: effectiveId,
            limit: 1000,
            nextToken,
          }, {
            selectionSet: [
              'id',
              'content',
              'role',
              'messageType',
              'humanInteraction',
              'toolName',
              'toolParameters',
              'toolResponse',
              'metadata',
              'parentMessageId',
              'accountId',
              'procedureId',
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
            let parsedToolParameters = parseJsonField(msg.toolParameters)
            
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
              humanInteraction: msg.humanInteraction,
              toolName: parsedToolName,
              toolParameters: parsedToolParameters,
              toolResponse: parseJsonField(msg.toolResponse),
              metadata: parseMessageMetadata(msg.metadata),
              parentMessageId: msg.parentMessageId,
              accountId: msg.accountId,
              procedureId: msg.procedureId,
              createdAt: msg.createdAt,
              sequenceNumber: msg.sequenceNumber,
              sessionId: msg.sessionId
            }
          })
          
          const visibleMessages = formattedMessages.filter(msg => {
            if (msg.humanInteraction === 'INTERNAL') {
              return msg.messageType !== 'TOOL_CALL' && msg.messageType !== 'TOOL_RESPONSE'
            }
            return true
          })

          // Sort all messages by sequence number and creation time
          const sortedMessages = visibleMessages.sort((a, b) => {
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
  }, [effectiveId])

  // Real-time subscription for new chat sessions - notification-based pattern
  useEffect(() => {
    if (!effectiveId) return

    const checkForNewSessions = async () => {
      try {
        const client = getClient()
        
        // Query for sessions in the current procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: effectiveId,
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
              // Auto-select the newest session when new sessions are created
              if (sortedSessions.length > 0) {
                const newestSession = sortedSessions[0]
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
        next: () => {
          // Don't rely on the subscription data, just use it as a notification
          checkForNewSessions()
        },
        error: (error: Error) => {
          console.error('Chat session subscription error:', error)
        }
      })

      return () => {
        subscription.unsubscribe()
      }
    } catch (error) {
      console.error('Error setting up chat session notification:', error)
    }
  }, [effectiveId, onSessionSelect])

  // Real-time subscription for new chat messages - notification-based pattern
  useEffect(() => {
    if (!effectiveId) return

    const checkForNewMessages = async () => {
      try {
        const client = getClient()
        
        // Load ALL messages for this experiment with proper pagination
        let allMessages: any[] = []
        let nextToken: string | null = null
        
        do {
          const response: { data?: any[], nextToken?: string } = await (client.models.ChatMessage.listChatMessageByProcedureIdAndCreatedAt as any)({
            procedureId: effectiveId,
            limit: 1000,
            nextToken,
          }, {
            selectionSet: [
              'id',
              'content',
              'role',
              'messageType',
              'humanInteraction',
              'toolName',
              'toolParameters',
              'toolResponse',
              'metadata',
              'parentMessageId',
              'accountId',
              'procedureId',
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

        if (messagesData) {
          const formattedMessages: ChatMessage[] = messagesData.map((msg: any) => {
            // Parse tool call data from content if structured fields are missing
            let parsedToolName = msg.toolName
            let parsedToolParameters = parseJsonField(msg.toolParameters)
            
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
              humanInteraction: msg.humanInteraction,
              toolName: parsedToolName,
              toolParameters: parsedToolParameters,
              toolResponse: parseJsonField(msg.toolResponse),
              metadata: parseMessageMetadata(msg.metadata),
              parentMessageId: msg.parentMessageId,
              accountId: msg.accountId,
              procedureId: msg.procedureId,
              createdAt: msg.createdAt,
              sequenceNumber: msg.sequenceNumber,
              sessionId: msg.sessionId
            }
          })
          
          const visibleMessages = formattedMessages.filter(msg => {
            if (msg.humanInteraction === 'INTERNAL') {
              return msg.messageType !== 'TOOL_CALL' && msg.messageType !== 'TOOL_RESPONSE'
            }
            return true
          })

          // Sort messages by sequence number and creation time
          const sortedMessages = visibleMessages.sort((a, b) => {
            if (a.sequenceNumber && b.sequenceNumber) {
              return a.sequenceNumber - b.sequenceNumber
            }
            return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
          })

          // Check if we have new messages compared to current state
          setInternalMessages(prevMessages => {
            const currentIds = new Set(prevMessages.map(m => m.id))
            const newMessages = sortedMessages.filter(m => !currentIds.has(m.id))
            
            if (newMessages.length > 0) {
              // Auto-scroll to the latest message after a brief delay to ensure DOM has updated
              setTimeout(() => {
                scrollToLatestMessage()
              }, 100)
              
              return sortedMessages // Replace with complete sorted list
            }
            
            return prevMessages // No changes
          })
        }
      } catch (error) {
        console.error('Error checking for new messages:', error)
      }
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      const subscription = getClient().models.ChatMessage.onCreate().subscribe({
        next: () => {
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
        subscription.unsubscribe()
      }
    } catch (error) {
      console.error('Error setting up chat message notification:', error)
    }
  }, [effectiveId, scrollToLatestMessage])
  
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

  const responseParentIds = new Set(
    filteredMessages
      .filter(message => message.humanInteraction === 'RESPONSE' && message.parentMessageId)
      .map(message => message.parentMessageId as string)
  )
  const unresolvedPendingMessageIds = new Set(
    filteredMessages
      .filter(message => isPendingHumanInteraction(message.humanInteraction) && !responseParentIds.has(message.id))
      .map(message => message.id)
  )

  // Sort messages by sequence number or creation date
  const sortedMessages = [...filteredMessages].sort((a, b) => {
    const aPending = unresolvedPendingMessageIds.has(a.id)
    const bPending = unresolvedPendingMessageIds.has(b.id)
    if (aPending !== bPending) {
      return aPending ? 1 : -1
    }
    if (a.sequenceNumber && b.sequenceNumber) {
      return a.sequenceNumber - b.sequenceNumber
    }
    return new Date(a.createdAt).getTime() - new Date(b.createdAt).getTime()
  })

  
  // Get the current selected session
  const selectedSession = selectedSessionId ? sessions.find(s => s.id === selectedSessionId) : null

  // Show loading state when loading data in effectiveId mode
  if (isLoading && effectiveId) {
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
              {sortedMessages.map((message) => {
                const controlEnvelope = getControlEnvelope(message.metadata)
                const requestType = (
                  controlEnvelope?.request_type
                  || mapPendingInteractionToRequestType(message.humanInteraction)
                ).toLowerCase()
                const messageIsPending = enableHitlActions && isPendingHumanInteraction(message.humanInteraction)
                const responseExists = responseParentIds.has(message.id)
                const isSubmitted = responseExists || submittedMessageIds.has(message.id)
                const isSubmitting = submittingMessageIds.has(message.id)
                const currentInput = hitlTextByMessage[message.id] || ''

                return (
                  <div key={message.id} data-message-id={message.id} className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-1">
                      {getMessageIcon(message.role, message.messageType, message.humanInteraction)}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge
                          variant="secondary"
                          className={`text-xs ${getMessageTypeColor(message.role, message.messageType, message.humanInteraction)}`}
                        >
                          {message.humanInteraction === 'NOTIFICATION' ? 'Notification' :
                           message.humanInteraction === 'ALERT_INFO' ? 'Info' :
                           message.humanInteraction === 'ALERT_WARNING' ? 'Warning' :
                           message.humanInteraction === 'ALERT_ERROR' ? 'Error' :
                           message.humanInteraction === 'ALERT_CRITICAL' ? 'Critical' :
                           message.humanInteraction === 'PENDING_APPROVAL' ? 'Pending Approval' :
                           message.humanInteraction === 'PENDING_INPUT' ? 'Pending Input' :
                           message.humanInteraction === 'PENDING_REVIEW' ? 'Pending Review' :
                           message.humanInteraction === 'PENDING_ESCALATION' ? 'Pending Escalation' :
                           message.humanInteraction === 'RESPONSE' ? 'Response' :
                           message.messageType === 'TOOL_CALL' ? 'Tool Call' :
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
                        null
                      ) : (
                        <div className="text-sm">
                          <CollapsibleText content={message.content} maxLines={10} />
                        </div>
                      )}

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

                      {messageIsPending && (
                        <div className="mt-3 rounded-md border border-border p-3 space-y-3">
                          {!controlEnvelope && (
                            <div className="text-xs text-red-600">
                              Pending request is missing canonical `metadata.control`.
                            </div>
                          )}
                          {hitlSubmitErrors[message.id] && (
                            <div className="text-xs text-red-600">
                              {hitlSubmitErrors[message.id]}
                            </div>
                          )}

                          {(requestType === 'input' || requestType === 'review' || requestType === 'escalation') && !isSubmitted && (
                            <Textarea
                              value={currentInput}
                              onChange={(event) => {
                                const value = event.target.value
                                setHitlTextByMessage((prev) => ({
                                  ...prev,
                                  [message.id]: value,
                                }))
                              }}
                              rows={requestType === 'review' ? 6 : 4}
                              placeholder={requestType === 'review' ? 'Review notes (optional)' : 'Enter response'}
                              disabled={isSubmitting}
                            />
                          )}

                          <div className="flex flex-wrap items-center gap-2">
                            {isSubmitted && (
                              <Badge variant="outline" className="text-green-700 border-green-700">
                                Response submitted
                              </Badge>
                            )}

                            {!isSubmitted && requestType === 'approval' && (
                              <>
                                <Button
                                  size="sm"
                                  disabled={isSubmitting || !controlEnvelope}
                                  onClick={async () => {
                                    try {
                                      await submitHitlResponse(message, 'approve')
                                    } catch (error) {
                                      console.error('Failed submitting approval response', error)
                                    }
                                  }}
                                >
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isSubmitting || !controlEnvelope}
                                  onClick={async () => {
                                    try {
                                      await submitHitlResponse(message, 'reject')
                                    } catch (error) {
                                      console.error('Failed submitting rejection response', error)
                                    }
                                  }}
                                >
                                  Reject
                                </Button>
                              </>
                            )}

                            {!isSubmitted && requestType === 'input' && (
                              <Button
                                size="sm"
                                disabled={isSubmitting || !controlEnvelope}
                                onClick={async () => {
                                  try {
                                    await submitHitlResponse(message, 'submit', currentInput)
                                  } catch (error) {
                                    console.error('Failed submitting input response', error)
                                  }
                                }}
                              >
                                Submit
                              </Button>
                            )}

                            {!isSubmitted && requestType === 'review' && (
                              <>
                                <Button
                                  size="sm"
                                  disabled={isSubmitting || !controlEnvelope}
                                  onClick={async () => {
                                    try {
                                      await submitHitlResponse(message, 'approve', currentInput)
                                    } catch (error) {
                                      console.error('Failed submitting review approval', error)
                                    }
                                  }}
                                >
                                  Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  disabled={isSubmitting || !controlEnvelope}
                                  onClick={async () => {
                                    try {
                                      await submitHitlResponse(message, 'request_changes', currentInput)
                                    } catch (error) {
                                      console.error('Failed submitting review feedback', error)
                                    }
                                  }}
                                >
                                  Request Changes
                                </Button>
                              </>
                            )}

                            {!isSubmitted && requestType === 'escalation' && (
                              <Button
                                size="sm"
                                disabled={isSubmitting || !controlEnvelope}
                                onClick={async () => {
                                  try {
                                    await submitHitlResponse(message, 'acknowledge', currentInput)
                                  } catch (error) {
                                    console.error('Failed submitting escalation acknowledgment', error)
                                  }
                                }}
                              >
                                Acknowledge
                              </Button>
                            )}

                            {isSubmitting && (
                              <Badge variant="outline">Submitting...</Badge>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ConversationViewer

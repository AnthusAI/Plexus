"use client"
import React, { useState, useEffect } from "react"
import { getClient } from '@/utils/data-operations'
import {
  Conversation,
  ConversationContent,
  ConversationEmptyState,
  ConversationScrollButton,
} from "@/components/ai-elements/conversation"
import { Message, MessageContent } from "@/components/ai-elements/message"
import { Shimmer } from "@/components/ai-elements/shimmer"
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
  type ToolState,
} from "@/components/ai-elements/tool"
import {
  PromptInput,
  PromptInputBody,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Textarea } from "@/components/ui/textarea"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  MessageSquare,
  PanelLeftOpen,
  PanelLeftClose,
  MoreHorizontal,
  Trash2,
  AlertCircle,
  Plus
} from "lucide-react"
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
import { cn } from "@/lib/utils"

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
  accountId?: string
  procedureId?: string
  name?: string
  category?: string
  createdAt: string
  updatedAt?: string
  messageCount?: number
}

type ConversationRow = {
  id: string
  from: 'assistant' | 'user'
  message: ChatMessage
}

type PendingAssistantState = {
  requestedAt: string
  baselineAssistantCreatedAt?: string | null
  triggerMessageId?: string
}

type ConsoleToolViewModel = {
  type: string
  toolName: string
  state: ToolState
  input?: unknown
  output?: unknown
  errorText?: string | null
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
  defaultSidebarCollapsed?: boolean
  enableSidebarResize?: boolean
  defaultSidebarWidth?: number
  forceProcedureIdForDispatch?: string
  defaultAccountIdForNewSession?: string
}

const START_CONSOLE_RUN_MUTATION = `
  mutation StartConsoleRun(
    $sessionId: String!
    $procedureId: String!
    $triggerMessageId: String!
    $clientInstrumentation: AWSJSON
  ) {
    startConsoleRun(
      sessionId: $sessionId
      procedureId: $procedureId
      triggerMessageId: $triggerMessageId
      clientInstrumentation: $clientInstrumentation
    ) {
      runId
      taskId
      accepted
      queuedAt
    }
  }
`

const API_KEY_AUTH_OPTIONS = { authMode: 'apiKey' as const }

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

const getErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message.trim()) {
    return error.message
  }
  if (error && typeof error === "object") {
    const maybeMessage = (error as { message?: unknown }).message
    if (typeof maybeMessage === "string" && maybeMessage.trim()) {
      return maybeMessage
    }
    const maybeErrors = (error as { errors?: unknown }).errors
    if (Array.isArray(maybeErrors)) {
      const first = maybeErrors.find(
        (entry) => entry && typeof entry === "object" && typeof (entry as { message?: unknown }).message === "string",
      ) as { message?: string } | undefined
      if (first?.message?.trim()) {
        return first.message
      }
    }
  }
  return fallback
}

const getUserFacingDispatchErrorMessage = (rawMessage: string): string => {
  const normalized = rawMessage.toLowerCase()
  if (
    normalized.includes("fieldundefined")
    || (normalized.includes("startconsolerun") && normalized.includes("undefined"))
  ) {
    return "Run dispatch is not available in this environment."
  }
  return "Run dispatch failed. Check browser console for details."
}

const parseRawChatMessage = (msg: any): ChatMessage | null => {
  if (!msg || typeof msg !== 'object' || !msg.id) {
    return null
  }

  // Parse tool call data from content if structured fields are missing
  let parsedToolName = msg.toolName
  let parsedToolParameters = parseJsonField(msg.toolParameters)

  if (msg.messageType === 'TOOL_CALL' && !msg.toolName && msg.content) {
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
}

const isVisibleChatMessage = (msg: ChatMessage): boolean => {
  if (msg.humanInteraction === 'INTERNAL') {
    return msg.messageType === 'TOOL_CALL' || msg.messageType === 'TOOL_RESPONSE'
  }
  return true
}

const isUserFacingMessage = (message: ChatMessage): boolean => {
  if (message.role === 'USER' || message.humanInteraction === 'RESPONSE') {
    return true
  }
  if (message.role === 'ASSISTANT') {
    return true
  }
  return false
}

const compareChatMessages = (a: ChatMessage, b: ChatMessage): number => {
  const sameSession = Boolean(a.sessionId && b.sessionId && a.sessionId === b.sessionId)
  const aSequence = typeof a.sequenceNumber === 'number' ? a.sequenceNumber : null
  const bSequence = typeof b.sequenceNumber === 'number' ? b.sequenceNumber : null

  if (sameSession && aSequence !== null && bSequence !== null && aSequence !== bSequence) {
    return aSequence - bSequence
  }

  const aCreatedMs = toEpochMs(a.createdAt) ?? 0
  const bCreatedMs = toEpochMs(b.createdAt) ?? 0
  if (aCreatedMs !== bCreatedMs) {
    return aCreatedMs - bCreatedMs
  }

  if (sameSession) {
    const aUserFacing = isUserFacingMessage(a)
    const bUserFacing = isUserFacingMessage(b)
    if (aUserFacing !== bUserFacing) {
      return aUserFacing ? -1 : 1
    }

    const aIsUserTurn = a.role === 'USER' || a.humanInteraction === 'RESPONSE'
    const bIsUserTurn = b.role === 'USER' || b.humanInteraction === 'RESPONSE'
    if (aIsUserTurn !== bIsUserTurn) {
      return aIsUserTurn ? -1 : 1
    }

    if (aSequence !== null && bSequence !== null && aSequence !== bSequence) {
      return aSequence - bSequence
    }
  }

  return a.id.localeCompare(b.id)
}

const sortChatMessages = (messages: ChatMessage[]): ChatMessage[] => {
  return [...messages].sort(compareChatMessages)
}

const normalizeAndSortVisibleMessages = (rawMessages: any[]): ChatMessage[] => {
  const parsed = rawMessages
    .map(parseRawChatMessage)
    .filter((msg): msg is ChatMessage => Boolean(msg))
    .filter(isVisibleChatMessage)
  const dedupedById = new Map<string, ChatMessage>()
  for (const message of parsed) {
    const existing = dedupedById.get(message.id)
    if (!existing || compareChatMessages(existing, message) <= 0) {
      dedupedById.set(message.id, message)
    }
  }
  return sortChatMessages([...dedupedById.values()])
}

const getMetadataFingerprint = (metadata: unknown): string => {
  try {
    return JSON.stringify(metadata ?? null)
  } catch {
    return '__unserializable__'
  }
}

const areMessagesEquivalent = (left: ChatMessage, right: ChatMessage): boolean => {
  return (
    left.id === right.id
    && left.content === right.content
    && left.role === right.role
    && left.messageType === right.messageType
    && left.humanInteraction === right.humanInteraction
    && left.toolName === right.toolName
    && getMetadataFingerprint(left.toolParameters) === getMetadataFingerprint(right.toolParameters)
    && getMetadataFingerprint(left.toolResponse) === getMetadataFingerprint(right.toolResponse)
    && getMetadataFingerprint(left.metadata) === getMetadataFingerprint(right.metadata)
    && left.parentMessageId === right.parentMessageId
    && left.accountId === right.accountId
    && left.procedureId === right.procedureId
    && left.createdAt === right.createdAt
    && left.sequenceNumber === right.sequenceNumber
    && left.sessionId === right.sessionId
  )
}

const hasMessageListChanged = (prevMessages: ChatMessage[], nextMessages: ChatMessage[]): boolean => {
  if (prevMessages.length !== nextMessages.length) {
    return true
  }

  for (let i = 0; i < nextMessages.length; i += 1) {
    const previous = prevMessages[i]
    const next = nextMessages[i]
    if (!previous || !next || previous.id !== next.id || !areMessagesEquivalent(previous, next)) {
      return true
    }
  }

  return false
}

const toEpochMs = (value?: string | null): number | null => {
  if (!value || typeof value !== 'string') {
    return null
  }
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : null
}

const isAssistantChatMessage = (message: ChatMessage): boolean => (
  message.role === 'ASSISTANT'
  && message.messageType === 'MESSAGE'
  && (
    !message.humanInteraction
    || message.humanInteraction === 'CHAT_ASSISTANT'
    || message.humanInteraction === 'CHAT'
  )
)

const CLIENT_HISTORY_SNAPSHOT_LIMIT = 24
const CLIENT_HISTORY_SNAPSHOT_MAX_CHARS = 600

const isSnapshotReadyAssistantMessage = (message: ChatMessage): boolean => {
  if (message.role !== 'ASSISTANT') {
    return true
  }
  if ((message.content || '').trim() === 'Assistant turn completed.') {
    return false
  }
  const metadata = message.metadata
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    return true
  }
  const streaming = (metadata as Record<string, unknown>).streaming
  if (!streaming || typeof streaming !== 'object' || Array.isArray(streaming)) {
    return true
  }
  const state = (streaming as Record<string, unknown>).state
  if (typeof state === 'string' && state.toLowerCase() === 'streaming') {
    return false
  }
  return true
}

const buildClientHistorySnapshot = (
  allMessages: ChatMessage[],
  sessionId: string,
  pendingUserMessage?: string,
): Array<{ role: 'USER' | 'ASSISTANT'; content: string }> => {
  if (!sessionId) {
    return []
  }

  const sessionMessages = sortChatMessages(
    allMessages.filter((message) => (
      message.sessionId === sessionId
      && (message.role === 'USER' || message.role === 'ASSISTANT')
      && (message.messageType || 'MESSAGE') === 'MESSAGE'
      && typeof message.content === 'string'
      && message.content.trim().length > 0
      && isSnapshotReadyAssistantMessage(message)
    )),
  )

  const snapshot: Array<{ role: 'USER' | 'ASSISTANT'; content: string }> = sessionMessages
    .map((message) => {
      const trimmed = message.content.trim()
      const content = trimmed.length > CLIENT_HISTORY_SNAPSHOT_MAX_CHARS
        ? `${trimmed.slice(0, CLIENT_HISTORY_SNAPSHOT_MAX_CHARS)}...`
        : trimmed
      return {
        role: message.role as 'USER' | 'ASSISTANT',
        content,
      }
    })
    .filter((entry) => Boolean(entry.content))

  const trimmedPending = (pendingUserMessage || '').trim()
  if (trimmedPending) {
    const lastEntry = snapshot[snapshot.length - 1]
    if (!lastEntry || lastEntry.role !== 'USER' || lastEntry.content !== trimmedPending) {
      snapshot.push({
        role: 'USER',
        content: trimmedPending.length > CLIENT_HISTORY_SNAPSHOT_MAX_CHARS
          ? `${trimmedPending.slice(0, CLIENT_HISTORY_SNAPSHOT_MAX_CHARS)}...`
          : trimmedPending,
      })
    }
  }

  if (snapshot.length > CLIENT_HISTORY_SNAPSHOT_LIMIT) {
    return snapshot.slice(snapshot.length - CLIENT_HISTORY_SNAPSHOT_LIMIT)
  }
  return snapshot
}

const getLatestAssistantCreatedAtForSession = (messages: ChatMessage[], sessionId: string): string | null => {
  let latest: string | null = null
  let latestMs: number | null = null

  for (const message of messages) {
    if (message.sessionId !== sessionId || !isAssistantChatMessage(message)) {
      continue
    }
    const candidateMs = toEpochMs(message.createdAt)
    if (candidateMs === null) {
      continue
    }
    if (latestMs === null || candidateMs > latestMs) {
      latestMs = candidateMs
      latest = message.createdAt
    }
  }

  return latest
}

const toToolType = (toolName?: string): string => {
  if (!toolName) {
    return 'tool-unknown'
  }
  return `tool-${toolName.replace(/[^a-zA-Z0-9_-]/g, '_')}`
}

const extractToolErrorText = (message: ChatMessage): string | null => {
  const candidates: unknown[] = [
    message.toolResponse,
    message.metadata,
  ]

  for (const candidate of candidates) {
    if (!candidate || typeof candidate !== 'object' || Array.isArray(candidate)) {
      continue
    }
    const record = candidate as Record<string, unknown>
    if (typeof record.errorText === 'string' && record.errorText.trim()) {
      return record.errorText
    }
    if (typeof record.error === 'string' && record.error.trim()) {
      return record.error
    }
    if (record.success === false && typeof message.content === 'string' && message.content.trim()) {
      return message.content
    }
  }

  return null
}

const mapMessageToToolViewModel = (message: ChatMessage): ConsoleToolViewModel | null => {
  if (message.messageType !== 'TOOL_CALL' && message.messageType !== 'TOOL_RESPONSE') {
    return null
  }

  const toolName = message.toolName || 'tool'
  const type = toToolType(toolName)

  if (message.messageType === 'TOOL_CALL') {
    return {
      type,
      toolName,
      state: message.toolParameters ? 'input-available' : 'input-streaming',
      input: message.toolParameters || {},
      output: undefined,
      errorText: null,
    }
  }

  const errorText = extractToolErrorText(message)
  const output = message.toolResponse
    ?? (message.content ? message.content : undefined)

  return {
    type,
    toolName,
    state: errorText ? 'output-error' : 'output-available',
    input: undefined,
    output,
    errorText,
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

const getMessageTypeColor = (role?: string, messageType?: string, humanInteraction?: string) => {
  const badgeStyles = {
    blue: 'border-transparent bg-blue-100 text-blue-800 dark:bg-blue-800/40 dark:text-blue-200',
    yellow: 'border-transparent bg-yellow-100 text-yellow-800 dark:bg-yellow-800/40 dark:text-yellow-200',
    red: 'border-transparent bg-red-100 text-red-800 dark:bg-red-800/40 dark:text-red-200',
    redCritical: 'border-transparent bg-red-200 text-red-900 dark:bg-red-800/60 dark:text-red-100',
    green: 'border-transparent bg-green-100 text-green-800 dark:bg-green-800/40 dark:text-green-200',
    purple: 'border-transparent bg-purple-100 text-purple-800 dark:bg-purple-800/40 dark:text-purple-200',
    orange: 'border-transparent bg-orange-100 text-orange-800 dark:bg-orange-800/40 dark:text-orange-200',
    gray: 'border-transparent bg-gray-100 text-gray-800 dark:bg-gray-700/50 dark:text-gray-200',
  } as const

  // Check humanInteraction first for special message types
  if (humanInteraction === 'NOTIFICATION') return badgeStyles.blue
  if (humanInteraction === 'ALERT_INFO') return badgeStyles.blue
  if (humanInteraction === 'ALERT_WARNING') return badgeStyles.yellow
  if (humanInteraction === 'ALERT_ERROR') return badgeStyles.red
  if (humanInteraction === 'ALERT_CRITICAL') return badgeStyles.redCritical
  if (humanInteraction === 'PENDING_APPROVAL' || humanInteraction === 'PENDING_INPUT' || humanInteraction === 'PENDING_REVIEW' || humanInteraction === 'PENDING_ESCALATION') {
    return badgeStyles.yellow
  }
  if (humanInteraction === 'RESPONSE') return badgeStyles.green

  if (messageType === 'TOOL_CALL') return badgeStyles.blue
  if (messageType === 'TOOL_RESPONSE') return badgeStyles.green

  switch (role) {
    case 'SYSTEM':
      return badgeStyles.purple
    case 'ASSISTANT':
      return badgeStyles.blue
    case 'USER':
      return badgeStyles.green
    case 'TOOL':
      return badgeStyles.orange
    default:
      return badgeStyles.gray
  }
}

const getMessageTypeLabel = (message: ChatMessage) => {
  if (message.humanInteraction === 'NOTIFICATION') return 'Notification'
  if (message.humanInteraction === 'ALERT_INFO') return 'Info'
  if (message.humanInteraction === 'ALERT_WARNING') return 'Warning'
  if (message.humanInteraction === 'ALERT_ERROR') return 'Error'
  if (message.humanInteraction === 'ALERT_CRITICAL') return 'Critical'
  if (message.humanInteraction === 'PENDING_APPROVAL') return 'Pending Approval'
  if (message.humanInteraction === 'PENDING_INPUT') return 'Pending Input'
  if (message.humanInteraction === 'PENDING_REVIEW') return 'Pending Review'
  if (message.humanInteraction === 'PENDING_ESCALATION') return 'Pending Escalation'
  if (message.humanInteraction === 'RESPONSE') return 'Response'
  if (message.messageType === 'TOOL_CALL') return 'Tool Call'
  if (message.messageType === 'TOOL_RESPONSE') return 'Tool Response'
  if (message.role === 'SYSTEM') return 'System'
  if (message.role === 'ASSISTANT') return 'Assistant'
  if (message.role === 'USER') return 'User'
  if (message.role === 'TOOL') return 'Tool'
  return message.messageType || message.role || 'Message'
}

const shouldShowMessageTypeBadge = (message: ChatMessage): boolean => {
  return [
    'NOTIFICATION',
    'ALERT_INFO',
    'ALERT_WARNING',
    'ALERT_ERROR',
    'ALERT_CRITICAL',
    'PENDING_APPROVAL',
    'PENDING_INPUT',
    'PENDING_REVIEW',
    'PENDING_ESCALATION',
    'RESPONSE',
  ].includes(message.humanInteraction || '')
}

const getRowFromMessage = (message: ChatMessage): ConversationRow => {
  if (message.role === 'USER' || message.humanInteraction === 'RESPONSE') {
    return {
      id: message.id,
      from: 'user',
      message,
    }
  }

  return {
    id: message.id,
    from: 'assistant',
    message,
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
  defaultSidebarCollapsed = true,
  enableSidebarResize = false,
  defaultSidebarWidth = 320,
  forceProcedureIdForDispatch,
  defaultAccountIdForNewSession,
}: ConversationViewerProps) {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(defaultSidebarCollapsed)
  const [sidebarWidth, setSidebarWidth] = useState(() => Math.min(Math.max(defaultSidebarWidth, 240), 520))
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = useState(0)
  
  // Internal state for data loading mode
  const [internalSessions, setInternalSessions] = useState<ChatSession[]>([])
  const [internalMessages, setInternalMessages] = useState<ChatMessage[]>([])
  const [internalSelectedSessionId, setInternalSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(false)
  const [hitlTextByMessage, setHitlTextByMessage] = useState<Record<string, string>>({})
  const [submittingMessageIds, setSubmittingMessageIds] = useState<Set<string>>(new Set())
  const [submittedMessageIds, setSubmittedMessageIds] = useState<Set<string>>(new Set())
  const [hitlSubmitErrors, setHitlSubmitErrors] = useState<Record<string, string>>({})
  const [promptValue, setPromptValue] = useState("")
  const [isPromptSubmitting, setIsPromptSubmitting] = useState(false)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [pendingAssistantBySession, setPendingAssistantBySession] = useState<Record<string, PendingAssistantState>>({})
  const selectedSessionIdRef = React.useRef<string | undefined>(undefined)
  const promptSubmitLockRef = React.useRef(false)

  useEffect(() => {
    const node = containerRef.current
    if (!node) return

    const update = () => setContainerWidth(node.getBoundingClientRect().width)
    update()
    const observer = new ResizeObserver(update)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  const maxSidebarWidth = React.useMemo(() => {
    if (!containerWidth) return 520
    return Math.max(240, Math.min(520, Math.floor(containerWidth * 0.55)))
  }, [containerWidth])

  useEffect(() => {
    setSidebarWidth((current) => Math.min(current, maxSidebarWidth))
  }, [maxSidebarWidth])

  // Determine which data source to use
  const sessions = propSessions || internalSessions
  const messages = propMessages || internalMessages  
  const selectedSessionId = propSelectedSessionId || internalSelectedSessionId
  const isExternallyControlledSession = Boolean(propSelectedSessionId?.trim())

  useEffect(() => {
    selectedSessionIdRef.current = selectedSessionId
  }, [selectedSessionId])

  useEffect(() => {
    if (propMessages) {
      return
    }

    const sessionCounts = internalMessages.reduce((acc: Record<string, number>, message) => {
      if (message.sessionId) {
        acc[message.sessionId] = (acc[message.sessionId] || 0) + 1
      }
      return acc
    }, {})

    setInternalSessions((prevSessions) => {
      let changed = false
      const nextSessions = prevSessions.map((session) => {
        const nextCount = sessionCounts[session.id] || 0
        if ((session.messageCount || 0) === nextCount) {
          return session
        }
        changed = true
        return {
          ...session,
          messageCount: nextCount,
        }
      })

      return changed ? nextSessions : prevSessions
    })
  }, [internalMessages, propMessages])
  
  // Use either experimentId or procedureId (they're synonymous in this context)
  const effectiveId = experimentId || procedureId
  const dispatchProcedureId = forceProcedureIdForDispatch?.trim() || null
  
  // Notify parent of session count changes
  useEffect(() => {
    if (onSessionCountChange) {
      onSessionCountChange(sessions.length)
    }
  }, [sessions.length, onSessionCountChange])

  const markPendingAssistant = React.useCallback((
    sessionId: string,
    requestedAt: string,
    triggerMessageId?: string,
  ) => {
    const baselineAssistantCreatedAt = getLatestAssistantCreatedAtForSession(messages, sessionId)
    setPendingAssistantBySession((prev) => ({
      ...prev,
      [sessionId]: {
        requestedAt,
        baselineAssistantCreatedAt,
        triggerMessageId,
      },
    }))
  }, [messages])

  const clearPendingAssistant = React.useCallback((sessionId: string) => {
    setPendingAssistantBySession((prev) => {
      if (!prev[sessionId]) {
        return prev
      }
      const next = { ...prev }
      delete next[sessionId]
      return next
    })
  }, [])

  useEffect(() => {
    const pendingEntries = Object.entries(pendingAssistantBySession)
    if (!pendingEntries.length) {
      return
    }

    const sessionsToClear: string[] = []
    for (const [sessionId, pendingState] of pendingEntries) {
      const baselineMs = toEpochMs(pendingState.baselineAssistantCreatedAt ?? null) ?? -Infinity
      const requestedMs = toEpochMs(pendingState.requestedAt) ?? -Infinity
      const threshold = Math.max(baselineMs, requestedMs)

      const hasNewAssistantMessage = messages.some((message) => {
        if (message.sessionId !== sessionId || !isAssistantChatMessage(message)) {
          return false
        }
        const messageMs = toEpochMs(message.createdAt)
        return messageMs !== null && messageMs > threshold
      })

      if (hasNewAssistantMessage) {
        sessionsToClear.push(sessionId)
      }
    }

    if (!sessionsToClear.length) {
      return
    }

    setPendingAssistantBySession((prev) => {
      let changed = false
      const next = { ...prev }
      for (const sessionId of sessionsToClear) {
        if (next[sessionId]) {
          delete next[sessionId]
          changed = true
        }
      }
      return changed ? next : prev
    })
  }, [messages, pendingAssistantBySession])
  
  const handleSessionSelect = (sessionId: string) => {
    setInternalSelectedSessionId(sessionId)
    if (onSessionSelect) {
      onSessionSelect(sessionId)
    }
  }

  const handleSidebarResizeStart = (e: React.MouseEvent) => {
    e.preventDefault()
    const startX = e.pageX
    const startWidth = sidebarWidth

    const handleDrag = (event: MouseEvent) => {
      const delta = event.pageX - startX
      const newWidth = Math.min(Math.max(startWidth + delta, 240), maxSidebarWidth)
      setSidebarWidth(newWidth)
    }

    const handleDragEnd = () => {
      document.removeEventListener('mousemove', handleDrag)
      document.removeEventListener('mouseup', handleDragEnd)
    }

    document.addEventListener('mousemove', handleDrag)
    document.addEventListener('mouseup', handleDragEnd)
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

  const startConsoleRun = React.useCallback(async (
    sessionId: string,
    procedureIdToRun: string,
    triggerMessageId: string,
    clientInstrumentation: Record<string, unknown> = {},
  ): Promise<{ taskId: string; runId: string; queuedAt: string }> => {
    const client = getClient() as any
    const response = await client.graphql({
      query: START_CONSOLE_RUN_MUTATION,
      variables: {
        sessionId,
        procedureId: procedureIdToRun,
        triggerMessageId,
        clientInstrumentation: JSON.stringify(clientInstrumentation),
      },
      authMode: 'apiKey',
    })

    const result = response?.data?.startConsoleRun
    if (!result?.accepted || !result?.taskId || !result?.runId || !result?.queuedAt) {
      throw new Error('Failed to queue procedure run after chat input')
    }
    return {
      taskId: result.taskId,
      runId: result.runId,
      queuedAt: result.queuedAt,
    }
  }, [])

  const enqueueProcedureRunTask = async (
    procedureIdToRun: string,
    sessionId: string,
    pendingMessageId: string,
    responseMessageId: string,
    requestId: string
  ) => {
    await startConsoleRun(
      sessionId,
      procedureIdToRun,
      responseMessageId,
      {
        hitl_resume: {
          pending_message_id: pendingMessageId,
          response_message_id: responseMessageId,
          request_id: requestId,
        },
      },
    )
  }

  const enqueueProcedureRunFromChat = React.useCallback(async (
    procedureIdToRun: string,
    triggerMessageId: string,
    sessionId: string,
    clientTiming: Record<string, unknown> = {},
  ) => {
    const instrumentation: Record<string, unknown> = {
      ...clientTiming,
      client_dispatch_request_started_at: new Date().toISOString(),
    }

    try {
      const dispatchResult = await startConsoleRun(
        sessionId,
        procedureIdToRun,
        triggerMessageId,
        instrumentation,
      )
      instrumentation.client_dispatch_request_completed_at = new Date().toISOString()
      instrumentation.client_dispatch_request_accepted = true
      instrumentation.queue_task_id = dispatchResult.taskId
      instrumentation.queue_run_id = dispatchResult.runId
      instrumentation.queue_accepted_at = dispatchResult.queuedAt
    } catch (error) {
      instrumentation.client_dispatch_request_completed_at = new Date().toISOString()
      instrumentation.client_dispatch_request_accepted = false
      throw error
    }
  }, [startConsoleRun])

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
      }, API_KEY_AUTH_OPTIONS)
      const responseMessageId = created?.data?.id
      if (!responseMessageId) {
        throw new Error('Failed to persist RESPONSE message')
      }

      await enqueueProcedureRunTask(
        pendingMessage.procedureId,
        pendingMessage.sessionId,
        pendingMessage.id,
        responseMessageId,
        control.request_id
      )
      markPendingAssistant(pendingMessage.sessionId, respondedAt, responseMessageId)

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
      if (pendingMessage.sessionId) {
        clearPendingAssistant(pendingMessage.sessionId)
      }
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
          limit: 100,
          authMode: 'apiKey',
        }, API_KEY_AUTH_OPTIONS)

        const fetchedSessions = Array.isArray(sessionsData) ? sessionsData : []
        const selectedId = selectedSessionIdRef.current?.trim()
        let mergedSessions = fetchedSessions

        // GSI reads can lag behind writes. If the URL points at a freshly created session
        // that's not in the index list yet, fetch by id and inject it.
        if (selectedId && !fetchedSessions.some((session: any) => session?.id === selectedId)) {
          try {
            const selectedSessionResponse = await (client.models.ChatSession.get as any)({ id: selectedId }, API_KEY_AUTH_OPTIONS)
            const selectedSession = selectedSessionResponse?.data
            if (selectedSession && (!effectiveId || selectedSession.procedureId === effectiveId)) {
              mergedSessions = [selectedSession, ...fetchedSessions]
            }
          } catch (error) {
            console.warn('Unable to fetch selected session by id during initial load:', error)
          }
        }

        if (mergedSessions.length > 0) {
          const dedupedSessions = mergedSessions.filter((session: any, index: number, array: any[]) => (
            session?.id && array.findIndex((candidate) => candidate?.id === session.id) === index
          ))

          const formattedSessions: ChatSession[] = dedupedSessions.map((session: any) => ({
            id: session.id,
            accountId: session.accountId,
            procedureId: session.procedureId,
            name: session.name,
            category: session.category,
            createdAt: session.createdAt,
            updatedAt: session.updatedAt,
            messageCount: 0 // Will be updated when we load messages
          }))
          
          // Sort sessions by createdAt in descending order (most recent first)
          const sortedSessions = formattedSessions.sort((a, b) => 
            new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
          )
          
          setInternalSessions(sortedSessions)
          
          if (!isExternallyControlledSession && sortedSessions.length > 0) {
            // Select the most recent session (first in sorted array)
            setInternalSelectedSessionId(sortedSessions[0].id)
          }
        } else {
          setInternalSessions([])
        }

        // Load ALL messages for this experiment with proper pagination
        let allMessages: any[] = []
        let nextToken: string | null = null
        
        do {
          const response: { data?: any[], nextToken?: string } = await (client.models.ChatMessage.listChatMessageByProcedureIdAndCreatedAt as any)({
            procedureId: effectiveId,
            limit: 1000,
            nextToken,
            authMode: 'apiKey',
          }, {
            authMode: 'apiKey',
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
          const sortedMessages = normalizeAndSortVisibleMessages(allMessages)
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
  }, [effectiveId, isExternallyControlledSession])

  // Real-time subscription for new chat sessions - notification-based pattern
  useEffect(() => {
    if (!effectiveId) return

    const checkForNewSessions = async () => {
      try {
        const client = getClient()
        
        // Query for sessions in the current procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: effectiveId,
          limit: 100,
          authMode: 'apiKey',
        }, API_KEY_AUTH_OPTIONS)

        const fetchedSessions = Array.isArray(sessionsData) ? sessionsData : []
        const selectedId = selectedSessionIdRef.current?.trim()
        let mergedSessions = fetchedSessions

        if (selectedId && !fetchedSessions.some((session: any) => session?.id === selectedId)) {
          try {
            const selectedSessionResponse = await (client.models.ChatSession.get as any)({ id: selectedId }, API_KEY_AUTH_OPTIONS)
            const selectedSession = selectedSessionResponse?.data
            if (selectedSession && (!effectiveId || selectedSession.procedureId === effectiveId)) {
              mergedSessions = [selectedSession, ...fetchedSessions]
            }
          } catch (error) {
            console.warn('Unable to fetch selected session by id during session refresh:', error)
          }
        }

        if (mergedSessions.length > 0) {
          const dedupedSessions = mergedSessions.filter((session: any, index: number, array: any[]) => (
            session?.id && array.findIndex((candidate) => candidate?.id === session.id) === index
          ))

          const formattedSessions: ChatSession[] = dedupedSessions.map((session: any) => ({
            id: session.id,
            accountId: session.accountId,
            procedureId: session.procedureId,
            name: session.name,
            category: session.category,
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
            const previousById = new Map(prevSessions.map(session => [session.id, session]))
            const mergedSessions = sortedSessions.map((session) => {
              const previous = previousById.get(session.id)
              return {
                ...session,
                messageCount: previous?.messageCount ?? session.messageCount ?? 0,
              }
            })

            const changed =
              mergedSessions.length !== prevSessions.length
              || mergedSessions.some((session) => {
                const previous = previousById.get(session.id)
                if (!previous) {
                  return true
                }
                return (
                  previous.updatedAt !== session.updatedAt
                  || previous.name !== session.name
                  || previous.category !== session.category
                )
              })

            if (!changed) {
              return prevSessions
            }

            const currentSelectedSessionId = selectedSessionIdRef.current
            const selectedStillExists = currentSelectedSessionId
              ? mergedSessions.some(session => session.id === currentSelectedSessionId)
              : false

            if (!selectedStillExists && !isExternallyControlledSession && mergedSessions.length > 0) {
              const newestSessionId = mergedSessions[0].id
              setInternalSelectedSessionId(newestSessionId)
            }

            return mergedSessions
          })
        } else {
          setInternalSessions([])
        }
      } catch (error) {
        console.error('Error checking for new chat sessions:', error)
      }
    }

    const pollTimer = window.setInterval(checkForNewSessions, 15000)
    checkForNewSessions()

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      const subscription = getClient().models.ChatSession.onCreate(API_KEY_AUTH_OPTIONS as any).subscribe({
        next: () => {
          // Don't rely on the subscription data, just use it as a notification
          checkForNewSessions()
        },
        error: (error: Error) => {
          console.error('Chat session subscription error:', error)
        }
      })

      return () => {
        window.clearInterval(pollTimer)
        subscription.unsubscribe()
      }
    } catch (error) {
      console.error('Error setting up chat session notification:', error)
    }
    return () => {
      window.clearInterval(pollTimer)
    }
  }, [effectiveId, isExternallyControlledSession, onSessionSelect])

  const applyRealtimeMessageMutation = React.useCallback((rawMessage: any) => {
    const parsed = parseRawChatMessage(rawMessage)
    if (!parsed) {
      return
    }

    if (parsed.procedureId && parsed.procedureId !== effectiveId) {
      return
    }

    const parsedSessionId = parsed.sessionId
    if (parsedSessionId && isAssistantChatMessage(parsed)) {
      setPendingAssistantBySession((prev) => {
        if (!prev[parsedSessionId]) {
          return prev
        }
        const next = { ...prev }
        delete next[parsedSessionId]
        return next
      })
    }

    setInternalMessages((prevMessages) => {
      const existingIndex = prevMessages.findIndex((message) => message.id === parsed.id)
      const visible = isVisibleChatMessage(parsed)

      if (!visible) {
        if (existingIndex === -1) {
          return prevMessages
        }
        return prevMessages.filter((message) => message.id !== parsed.id)
      }

      if (existingIndex === -1) {
        return sortChatMessages([...prevMessages, parsed])
      }

      const previous = prevMessages[existingIndex]
      if (areMessagesEquivalent(previous, parsed)) {
        return prevMessages
      }

      const next = [...prevMessages]
      next[existingIndex] = parsed
      return sortChatMessages(next)
    })
  }, [effectiveId])

  // Real-time subscription for chat messages. onCreate/onUpdate are primary; polling is fallback.
  useEffect(() => {
    if (!effectiveId) return

    let isCancelled = false

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
            authMode: 'apiKey',
          }, {
            authMode: 'apiKey',
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

        if (isCancelled) {
          return
        }

        const sortedMessages = normalizeAndSortVisibleMessages(allMessages)
        setInternalMessages((prevMessages) => (
          hasMessageListChanged(prevMessages, sortedMessages)
            ? sortedMessages
            : prevMessages
        ))
      } catch (error) {
        console.error('Error checking for new messages:', error)
      }
    }

    const extractSubscriptionMessage = (payload: any): any | null => {
      const directData = payload?.data
      if (directData && typeof directData === 'object') {
        if ('onCreateChatMessage' in directData) {
          return directData.onCreateChatMessage
        }
        if ('onUpdateChatMessage' in directData) {
          return directData.onUpdateChatMessage
        }
        if ('id' in directData) {
          return directData
        }
      }
      if (payload && typeof payload === 'object' && 'id' in payload) {
        return payload
      }
      return null
    }

    let createSubscription: { unsubscribe: () => void } | null = null
    let updateSubscription: { unsubscribe: () => void } | null = null
    const pollTimer = window.setInterval(() => {
      checkForNewMessages()
    }, 15000)

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      createSubscription = getClient().models.ChatMessage.onCreate(API_KEY_AUTH_OPTIONS as any).subscribe({
        next: (payload: any) => {
          const incoming = extractSubscriptionMessage(payload)
          if (incoming) {
            applyRealtimeMessageMutation(incoming)
            return
          }
          checkForNewMessages()
        },
        error: (error: Error) => {
          console.error('Chat message create subscription error:', error)
        }
      })
    } catch (error) {
      console.error('Error setting up chat message create notification:', error)
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      updateSubscription = getClient().models.ChatMessage.onUpdate(API_KEY_AUTH_OPTIONS as any).subscribe({
        next: (payload: any) => {
          const incoming = extractSubscriptionMessage(payload)
          if (incoming) {
            applyRealtimeMessageMutation(incoming)
            return
          }
          checkForNewMessages()
        },
        error: (error: Error) => {
          console.error('Chat message update subscription error:', error)
        }
      })
    } catch (error) {
      console.error('Error setting up chat message update notification:', error)
    }

    // Initial load + reconciliation on mount.
    checkForNewMessages()

    return () => {
      isCancelled = true
      window.clearInterval(pollTimer)
      createSubscription?.unsubscribe()
      updateSubscription?.unsubscribe()
    }
  }, [applyRealtimeMessageMutation, effectiveId])
  
  // Sort sessions by last update date in reverse chronological order (most recent first)
  const sortedSessions = [...sessions].sort((a, b) => {
    const aTime = new Date(a.updatedAt || a.createdAt).getTime()
    const bTime = new Date(b.updatedAt || b.createdAt).getTime()
    return bTime - aTime
  })

  // Filter messages for selected session
  const filteredMessages = selectedSessionId
    ? messages.filter(msg => (msg as any).sessionId === selectedSessionId)
    : []

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
    return compareChatMessages(a, b)
  })

  
  // Get the current selected session
  const selectedSession = selectedSessionId ? sessions.find(s => s.id === selectedSessionId) : null
  const selectedSessionMissing = Boolean(selectedSessionId && !selectedSession)
  const pendingAssistantState = selectedSessionId ? pendingAssistantBySession[selectedSessionId] : undefined
  const showThinkingPlaceholder = React.useMemo(() => {
    if (!selectedSession || !pendingAssistantState) {
      return false
    }

    const baselineMs = toEpochMs(pendingAssistantState.baselineAssistantCreatedAt ?? null) ?? -Infinity
    const requestedMs = toEpochMs(pendingAssistantState.requestedAt) ?? -Infinity
    const threshold = Math.max(baselineMs, requestedMs)

    const hasAssistantSincePending = sortedMessages.some((message) => {
      if (message.sessionId !== selectedSession.id || !isAssistantChatMessage(message)) {
        return false
      }
      const messageMs = toEpochMs(message.createdAt)
      return messageMs !== null && messageMs > threshold
    })

    return !hasAssistantSincePending
  }, [pendingAssistantState, selectedSession, sortedMessages])
  const isPromptDisabled = !selectedSession
  const conversationRows = sortedMessages.map(getRowFromMessage)
  const pendingMessageForPrompt = React.useMemo(
    () => [...sortedMessages].reverse().find(message => unresolvedPendingMessageIds.has(message.id)) || null,
    [sortedMessages, unresolvedPendingMessageIds]
  )
  const selectedSessionAccountId = selectedSession?.accountId
    || sortedMessages.find(message => message.accountId)?.accountId
  const selectedSessionProcedureId = dispatchProcedureId
    || selectedSession?.procedureId
    || sortedMessages.find(message => message.procedureId)?.procedureId
    || effectiveId
  const fallbackSessionAccountId = React.useMemo(
    () => (
      defaultAccountIdForNewSession
      || 
      selectedSessionAccountId
      || sessions.find(session => session.accountId)?.accountId
      || messages.find(message => message.accountId)?.accountId
    ),
    [defaultAccountIdForNewSession, messages, selectedSessionAccountId, sessions]
  )
  const fallbackSessionProcedureId = React.useMemo(
    () => (
      dispatchProcedureId
      || selectedSessionProcedureId
      || sessions.find(session => session.procedureId)?.procedureId
      || messages.find(message => message.procedureId)?.procedureId
      || effectiveId
    ),
    [dispatchProcedureId, effectiveId, messages, selectedSessionProcedureId, sessions]
  )
  const canCreateSession = Boolean(fallbackSessionAccountId && fallbackSessionProcedureId)

  const createNewSession = React.useCallback(async () => {
    if (!fallbackSessionAccountId || !fallbackSessionProcedureId) {
      throw new Error('Missing account or procedure context to create a session')
    }

    const client = getClient()
    const createdAt = new Date().toISOString()
    const created = await (client.models.ChatSession.create as any)({
      accountId: fallbackSessionAccountId,
      procedureId: fallbackSessionProcedureId,
      category: 'Console Chat',
      createdAt,
      updatedAt: createdAt,
    }, API_KEY_AUTH_OPTIONS)

    const sessionId = created?.data?.id
    if (!sessionId) {
      throw new Error('Failed to create chat session')
    }

    const createdSession: ChatSession = {
      id: sessionId,
      accountId: fallbackSessionAccountId,
      procedureId: fallbackSessionProcedureId,
      category: created?.data?.category || 'Console Chat',
      name: created?.data?.name,
      createdAt: created?.data?.createdAt || createdAt,
      updatedAt: created?.data?.updatedAt || createdAt,
      messageCount: 0,
    }

    setInternalSessions(prev => [createdSession, ...prev.filter(session => session.id !== sessionId)])
    if (onSessionSelect) {
      onSessionSelect(sessionId)
    } else {
      setInternalSelectedSessionId(sessionId)
    }

    return createdSession
  }, [fallbackSessionAccountId, fallbackSessionProcedureId, onSessionSelect])

  const handleCreateSession = React.useCallback(async () => {
    if (isCreatingSession) {
      return
    }
    if (!canCreateSession) {
      toast.error('Unable to create a session until account and procedure context are available')
      return
    }

    setIsCreatingSession(true)
    try {
      await createNewSession()
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to create session'
      console.error('[ConsoleChat] session create failed', {
        error,
        accountId: fallbackSessionAccountId,
        procedureId: fallbackSessionProcedureId,
        selectedSessionId,
      })
      toast.error(message)
    } finally {
      setIsCreatingSession(false)
    }
  }, [canCreateSession, createNewSession, isCreatingSession])

  const handlePromptSubmit = React.useCallback(
    async ({ text }: { text?: string }) => {
      const nextValue = (text || '').trim()
      if (!nextValue) {
        return
      }

      if (promptSubmitLockRef.current || isPromptSubmitting || isCreatingSession) {
        return
      }

      promptSubmitLockRef.current = true
      try {
        let targetSessionId = selectedSessionId
        let targetSessionAccountId = selectedSessionAccountId
        let targetSessionProcedureId = selectedSessionProcedureId

        if (!selectedSession && targetSessionId) {
          toast.info('Select a valid chat session first')
          return
        }

        if (!targetSessionId) {
          try {
            const newSession = await createNewSession()
            targetSessionId = newSession.id
            targetSessionAccountId = newSession.accountId
            targetSessionProcedureId = newSession.procedureId
          } catch (error) {
            const message = error instanceof Error ? error.message : 'Failed to create a fresh session before send'
            toast.error(message)
            return
          }
        }

        if (!targetSessionId) {
          toast.info('Select or create a chat session first')
          return
        }

        if (pendingMessageForPrompt) {
          setIsPromptSubmitting(true)
          try {
            await submitHitlResponse(pendingMessageForPrompt, 'submit', nextValue)
            setPromptValue('')
          } finally {
            setIsPromptSubmitting(false)
          }
          return
        }

        if (!targetSessionAccountId || !targetSessionProcedureId) {
          toast.error('Missing required session metadata to send chat input')
          return
        }

        const clientSendStartedAt = new Date().toISOString()
        const nowIso = new Date().toISOString()
        const optimisticMessageId = `tmp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        const optimisticMessage: ChatMessage = {
          id: optimisticMessageId,
          accountId: targetSessionAccountId,
          sessionId: targetSessionId,
          procedureId: targetSessionProcedureId,
          role: 'USER',
          messageType: 'MESSAGE',
          humanInteraction: 'CHAT',
          content: nextValue,
          createdAt: nowIso,
        }

        setIsPromptSubmitting(true)
        setInternalMessages(prev => [...prev, optimisticMessage])
        setInternalSessions(prev => prev.map(session => (
          session.id === targetSessionId
            ? { ...session, messageCount: (session.messageCount || 0) + 1, updatedAt: nowIso }
            : session
        )))

        let messagePersisted = false
        try {
          const client = getClient()
          const created = await (client.models.ChatMessage.create as any)({
            accountId: targetSessionAccountId,
            sessionId: targetSessionId,
            procedureId: targetSessionProcedureId,
            role: 'USER',
            messageType: 'MESSAGE',
            humanInteraction: 'CHAT',
            content: nextValue,
            metadata: JSON.stringify({
              source: 'console-prompt-input',
              sent_at: nowIso,
              instrumentation: {
                client_send_started_at: clientSendStartedAt,
              },
            }),
          }, API_KEY_AUTH_OPTIONS)

          const createdMessageId = created?.data?.id
          if (!createdMessageId) {
            throw new Error('Failed to persist chat message')
          }
          messagePersisted = true

          const persistedCreatedAt = created?.data?.createdAt || nowIso
          setInternalMessages(prev => prev.map(message => (
            message.id === optimisticMessageId
              ? { ...optimisticMessage, id: createdMessageId, createdAt: persistedCreatedAt }
              : message
          )))

          const dispatchMessageText = nextValue.length > 4000
            ? `${nextValue.slice(0, 4000)}…`
            : nextValue
          const clientHistorySnapshot = buildClientHistorySnapshot(
            messages,
            targetSessionId,
            nextValue,
          )

          await enqueueProcedureRunFromChat(
            targetSessionProcedureId,
            createdMessageId,
            targetSessionId,
            {
              client_send_started_at: clientSendStartedAt,
              client_user_message_created_at: persistedCreatedAt,
              client_prompt_length_chars: nextValue.length,
              client_user_message_text: dispatchMessageText,
              client_history_snapshot: clientHistorySnapshot,
            },
          )
          markPendingAssistant(targetSessionId, persistedCreatedAt, createdMessageId)

          setPromptValue('')
        } catch (error) {
          clearPendingAssistant(targetSessionId)
          if (!messagePersisted) {
            setInternalMessages(prev => prev.filter(message => message.id !== optimisticMessageId))
            setInternalSessions(prev => prev.map(session => (
              session.id === targetSessionId
                ? { ...session, messageCount: Math.max(0, (session.messageCount || 1) - 1) }
                : session
            )))
          }

          const errorMessage = getErrorMessage(error, 'Failed to send chat message')
          console.error('[ConsoleChat] send/dispatch failure', {
            messagePersisted,
            sessionId: targetSessionId,
            procedureId: targetSessionProcedureId,
            errorMessage,
            error,
          })
          if (messagePersisted) {
            toast.error(`Message saved, but ${getUserFacingDispatchErrorMessage(errorMessage)}`)
          } else {
            toast.error(errorMessage)
          }
          throw error
        } finally {
          setIsPromptSubmitting(false)
        }
      } finally {
        promptSubmitLockRef.current = false
      }
    },
    [
      selectedSessionAccountId,
      selectedSessionId,
      selectedSession,
      selectedSessionProcedureId,
      pendingMessageForPrompt,
      isPromptSubmitting,
      isCreatingSession,
      messages,
      createNewSession,
      enqueueProcedureRunFromChat,
      clearPendingAssistant,
      markPendingAssistant,
      submitHitlResponse,
    ]
  )

  // Show loading state when loading data in effectiveId mode
  if (isLoading && effectiveId) {
    return (
      <div className={`flex h-full bg-background ${className} items-center justify-center`}>
        <div className="text-muted-foreground">Loading conversation...</div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className={`flex h-full bg-background min-w-0 ${className}`}>
      {/* Left Sidebar - Session List */}
      <div
        className={`${isSidebarCollapsed ? 'w-12' : 'shrink-0'} transition-all duration-200 border-r border-border flex flex-col`}
        style={!isSidebarCollapsed ? { width: sidebarWidth } : undefined}
      >
        {/* Sidebar Header */}
        <div className="p-3 border-b border-border flex items-center justify-between">
          {!isSidebarCollapsed && (
            <h3 className="text-sm font-medium">Chat Sessions ({sortedSessions.length})</h3>
          )}
          <div className="flex items-center gap-1">
            {!isSidebarCollapsed && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCreateSession}
                className="h-8 w-8 p-0"
                disabled={!canCreateSession || isCreatingSession}
                title="New session"
              >
                <Plus className="h-4 w-4" />
              </Button>
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

      {!isSidebarCollapsed && enableSidebarResize && (
        <div
          className="w-[12px] relative cursor-col-resize flex-shrink-0 group"
          onMouseDown={handleSidebarResizeStart}
        >
          <div className="absolute inset-0 rounded-full transition-colors duration-150 group-hover:bg-accent" />
        </div>
      )}

      {/* Main Content - Messages */}
      <div className="flex-1 min-w-0 flex flex-col">
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
                    <span>
                      {selectedSession.messageCount ? `${selectedSession.messageCount} messages` : 'No messages'}
                    </span>
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
        <div className="min-h-0 flex-1">
          <Conversation className="h-full">
            <ConversationContent className="gap-4 px-3 py-3">
              {!selectedSessionId ? (
                <ConversationEmptyState
                  title="No session selected"
                  description="Select a chat session to view messages"
                  icon={<MessageSquare className="h-12 w-12 opacity-50" />}
                />
              ) : selectedSessionMissing ? (
                <div className="flex h-full flex-col items-center justify-center gap-3">
                  <ConversationEmptyState
                    title="Session not found"
                    description="The session in this URL is unavailable for the current account. Select another session or create a new one."
                    icon={<AlertCircle className="h-12 w-12 opacity-50" />}
                  />
                  <Button
                    size="sm"
                    onClick={handleCreateSession}
                    disabled={!canCreateSession || isCreatingSession}
                  >
                    Create New Session
                  </Button>
                </div>
              ) : conversationRows.length === 0 ? (
                <ConversationEmptyState
                  title="No messages in this session"
                  description="Run the console REPL or send a message to start this session."
                  icon={<MessageSquare className="h-12 w-12 opacity-50" />}
                />
              ) : (
                conversationRows.map((row) => {
                  const message = row.message
                  const toolViewModel = mapMessageToToolViewModel(message)
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
                  const messageTypeLabel = getMessageTypeLabel(message)
                  const showMessageTypeBadge = shouldShowMessageTypeBadge(message)
                  const showToolNameBadge = Boolean(message.toolName) && !toolViewModel
                  const showMetadataBadges = showMessageTypeBadge || showToolNameBadge

                  return (
                    <Message
                      key={row.id}
                      from={row.from}
                      data-message-id={row.id}
                      data-from={row.from}
                      className="max-w-full"
                    >
                      <div className="flex items-start">
                        <MessageContent className="max-w-full p-0 sm:max-w-[85%]">
                          {showMetadataBadges && (
                            <div className="mb-2 flex items-center gap-2">
                              {showMessageTypeBadge && (
                                <Badge
                                  variant="secondary"
                                  className={`text-xs ${getMessageTypeColor(message.role, message.messageType, message.humanInteraction)}`}
                                >
                                  {messageTypeLabel}
                                </Badge>
                              )}

                              {showToolNameBadge && (
                                <Badge variant="outline" className="text-xs">
                                  {message.toolName}
                                </Badge>
                              )}
                            </div>
                          )}

                          {toolViewModel ? (
                            <Tool
                              defaultOpen={
                                toolViewModel.state === 'output-available'
                                || toolViewModel.state === 'output-error'
                                || toolViewModel.state === 'output-denied'
                              }
                            >
                              <ToolHeader
                                toolType={toolViewModel.type}
                                state={toolViewModel.state}
                                toolName={toolViewModel.toolName}
                              />
                              <ToolContent>
                                {message.messageType === 'TOOL_CALL' && (
                                  <ToolInput input={toolViewModel.input} />
                                )}
                                {message.messageType === 'TOOL_RESPONSE' && (
                                  <ToolOutput
                                    errorText={toolViewModel.errorText}
                                    output={
                                      <div className="font-mono whitespace-pre-wrap break-words">
                                        {toolViewModel.output === undefined || toolViewModel.output === null
                                          ? 'No output'
                                          : typeof toolViewModel.output === 'string'
                                            ? toolViewModel.output
                                            : formatJsonWithNewlines(toolViewModel.output)}
                                      </div>
                                    }
                                  />
                                )}
                              </ToolContent>
                            </Tool>
                          ) : (
                            <div className="text-sm">
                              <CollapsibleText content={message.content} maxLines={10} />
                            </div>
                          )}

                          {messageIsPending && (
                            <div className="mt-3 space-y-3 rounded-md border border-border p-3">
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
                                  <Badge
                                    variant="outline"
                                    className="border-green-700/60 bg-green-50 text-green-700 dark:border-green-400/40 dark:bg-green-900/40 dark:text-green-200"
                                  >
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
                        </MessageContent>
                      </div>
                    </Message>
                  )
                })
              )}
              {showThinkingPlaceholder && (
                <Message
                  key={`thinking-${selectedSessionId}`}
                  from="assistant"
                  data-message-id={`thinking-${selectedSessionId}`}
                  data-from="assistant"
                  className="max-w-full"
                >
                  <div className="flex items-start">
                    <MessageContent className="max-w-full p-0 sm:max-w-[85%]">
                      <Shimmer className="text-sm">Thinking</Shimmer>
                    </MessageContent>
                  </div>
                </Message>
              )}
            </ConversationContent>
            <ConversationScrollButton />
          </Conversation>
        </div>
        <div className="border-t border-border bg-background px-3 py-3">
          <PromptInput className="w-full" onPromptSubmit={handlePromptSubmit}>
            <PromptInputBody>
                <PromptInputTextarea
                  value={promptValue}
                  onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setPromptValue(event.target.value)}
                  disabled={isPromptDisabled || isPromptSubmitting}
                  placeholder={isPromptDisabled ? "Select a session to compose a message" : "Type a message"}
                />
            </PromptInputBody>
            <PromptInputFooter className="justify-end">
              <PromptInputSubmit disabled={isPromptDisabled || !promptValue.trim() || isPromptSubmitting} />
            </PromptInputFooter>
          </PromptInput>
          {isPromptDisabled && (
            <p className="pt-2 text-xs text-muted-foreground">
              {selectedSessionMissing
                ? "Select an available session or create a new one to enable prompt input."
                : "Select a chat session to enable prompt input."}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

export default ConversationViewer

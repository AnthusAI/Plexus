"use client"
import React, { useState, useEffect, useRef } from "react"
import { Virtuoso, type VirtuosoHandle } from "react-virtuoso"
import { getClient } from '@/utils/data-operations'
import { formatAmplifyError } from '@/utils/amplify-client'
import {
  Conversation,
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
  PromptInputSelect,
  PromptInputSelectContent,
  PromptInputSelectItem,
  PromptInputSelectTrigger,
  PromptInputSelectValue,
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
  ChevronDownIcon,
  MoreHorizontal,
  Pencil,
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
import { Input } from "@/components/ui/input"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"

const EvaluationToolOutput = React.lazy(() => import('./evaluation-tool-output'))
const STANDARD_SESSION_CATEGORY = 'Optimize'

const EVALUATION_TOOL_NAMES = new Set([
  'plexus_evaluation_run',
  'plexus_evaluation_info',
])

const CONSOLE_CHAT_MODEL_OPTIONS = [
  { value: 'gpt-5.4', label: 'GPT-5.4' },
  { value: 'gpt-5.3', label: 'GPT-5.3' },
  { value: 'gpt-5.2', label: 'GPT-5.2' },
  { value: 'gpt-5.1', label: 'GPT-5.1' },
  { value: 'gpt-5.4-mini', label: 'GPT-5.4 mini' },
  { value: 'gpt-5-mini', label: 'GPT-5 mini' },
  { value: 'gpt-5.4-nano', label: 'GPT-5.4 nano' },
  { value: 'gpt-5-nano', label: 'GPT-5 nano' },
] as const

const DEFAULT_CONSOLE_CHAT_MODEL = 'gpt-5.4-mini'

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
  responseTarget?: string
  responseStatus?: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  responseOwner?: string
  responseStartedAt?: string
  responseCompletedAt?: string
  responseError?: string
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
  metadata?: any
  createdAt: string
  updatedAt?: string
  messageCount?: number
}

type MessageConversationRow = {
  id: string
  from: 'assistant' | 'user'
  message: ChatMessage
  kind: 'message'
}

type ThinkingConversationRow = {
  id: string
  from: 'assistant'
  kind: 'thinking'
}

type ConversationRow = MessageConversationRow | ThinkingConversationRow

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

const parseSessionMetadata = (value: unknown): Record<string, any> => {
  const parsed = parseJsonField(value)
  if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
    return parsed as Record<string, any>
  }
  return {}
}

const serializeSessionMetadata = (value: unknown): string | undefined => {
  if (value === undefined || value === null) {
    return undefined
  }
  if (typeof value === "string") {
    const trimmed = value.trim()
    return trimmed || undefined
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value)
    } catch {
      return undefined
    }
  }
  return undefined
}

const getSessionDisplayName = (session: Pick<ChatSession, "id" | "name">): string => {
  const explicitName = String(session.name || "").trim()
  if (explicitName) {
    return explicitName
  }
  const sessionId = String(session.id || "").trim()
  if (!sessionId) {
    return "New Chat"
  }
  return `Session ${sessionId.slice(0, 8)}`
}

const getSessionHeaderTitle = (session: Pick<ChatSession, "id" | "name" | "metadata">): string => {
  const explicitName = String(session.name || "").trim()
  if (explicitName) {
    return explicitName
  }
  if (isHiddenUntilNamedSession(session)) {
    return "New Chat"
  }
  const sessionId = String(session.id || "").trim()
  if (!sessionId) {
    return "New Chat"
  }
  return `Session ${sessionId.slice(0, 8)}`
}

const isHiddenUntilNamedSession = (session: Pick<ChatSession, "name" | "metadata">): boolean => {
  const explicitName = String(session.name || "").trim()
  if (explicitName) {
    return false
  }
  const metadata = parseSessionMetadata(session.metadata)
  const consoleMetadata = metadata.console
  if (!consoleMetadata || typeof consoleMetadata !== "object") {
    return false
  }
  return Boolean((consoleMetadata as { hidden_until_named?: boolean }).hidden_until_named)
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

const isUnauthorizedError = (error: unknown): boolean => {
  if (!error) {
    return false
  }

  const messages: string[] = []
  const statusCandidates: Array<number | undefined> = []

  if (error instanceof Error) {
    messages.push(error.message)
  }

  if (typeof error === "object" && error !== null) {
    const record = error as Record<string, unknown>
    if (typeof record.message === "string") {
      messages.push(record.message)
    }
    if (typeof record.statusCode === "number") {
      statusCandidates.push(record.statusCode)
    }
    if (typeof record.status === "number") {
      statusCandidates.push(record.status)
    }

    if (Array.isArray(record.errors)) {
      for (const entry of record.errors) {
        if (entry && typeof entry === "object") {
          const entryMessage = (entry as Record<string, unknown>).message
          if (typeof entryMessage === "string") {
            messages.push(entryMessage)
          }
        }
      }
    }
  }

  if (statusCandidates.includes(401)) {
    return true
  }

  const normalized = messages.join(" ").toLowerCase()
  return (
    normalized.includes("unauthorized")
    || normalized.includes("not authorized")
    || normalized.includes("unauthenticated")
    || normalized.includes("forbidden")
    || normalized.includes("401")
  )
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
    responseTarget: msg.responseTarget,
    responseStatus: msg.responseStatus,
    responseOwner: msg.responseOwner,
    responseStartedAt: msg.responseStartedAt,
    responseCompletedAt: msg.responseCompletedAt,
    responseError: msg.responseError,
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
    if (message.toolResponse !== undefined && message.toolResponse !== null) {
      // Tool call has completed — show as a single completed component
      const errorText = extractToolErrorText(message)
      const output = message.toolResponse
      return {
        type,
        toolName,
        state: errorText ? 'output-error' : 'output-available',
        input: message.toolParameters || {},
        output,
        errorText,
      }
    }
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
  maxLines,
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
  const shouldTruncate = maxLines != null && lines.length > maxLines
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
    blue: 'bg-info text-primary-foreground',
    yellow: 'bg-warning text-primary-foreground',
    red: 'bg-false text-primary-foreground',
    redCritical: 'bg-false text-primary-foreground',
    green: 'bg-true text-primary-foreground',
    purple: 'bg-info text-primary-foreground',
    orange: 'bg-warning text-primary-foreground',
    gray: 'bg-neutral text-primary-foreground',
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

const getRowFromMessage = (message: ChatMessage): MessageConversationRow => {
  if (message.role === 'USER' || message.humanInteraction === 'RESPONSE') {
    return {
      id: message.id,
      from: 'user',
      message,
      kind: 'message',
    }
  }

  return {
    id: message.id,
    from: 'assistant',
    message,
    kind: 'message',
  }
}

type MessageCostSummary = {
  schema_version?: number
  total_usd?: number
  llm_calls?: number
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
  cached_tokens?: number
  breakdown?: Array<Record<string, unknown>>
}

type MessageCostMetadata = {
  kind?: string
  billing_mode?: string
  live?: boolean
  summary?: MessageCostSummary
}

const hasMeaningfulCostSummary = (summary: MessageCostSummary | null | undefined): boolean => {
  if (!summary || typeof summary !== 'object') {
    return false
  }
  const totalUsd = typeof summary.total_usd === 'number' ? summary.total_usd : 0
  const llmCalls = typeof summary.llm_calls === 'number' ? summary.llm_calls : 0
  const promptTokens = typeof summary.prompt_tokens === 'number' ? summary.prompt_tokens : 0
  const completionTokens = typeof summary.completion_tokens === 'number' ? summary.completion_tokens : 0
  const totalTokens = typeof summary.total_tokens === 'number' ? summary.total_tokens : 0
  const cachedTokens = typeof summary.cached_tokens === 'number' ? summary.cached_tokens : 0
  const hasBreakdown = Array.isArray(summary.breakdown) && summary.breakdown.length > 0
  return (
    totalUsd > 0
    || llmCalls > 0
    || promptTokens > 0
    || completionTokens > 0
    || totalTokens > 0
    || cachedTokens > 0
    || hasBreakdown
  )
}

const getMessageCostMetadata = (message: ChatMessage): MessageCostMetadata | null => {
  const metadata = message.metadata
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) {
    return null
  }
  const cost = (metadata as Record<string, unknown>).cost
  if (!cost || typeof cost !== 'object' || Array.isArray(cost)) {
    return null
  }
  return cost as MessageCostMetadata
}

const formatUsd = (value: number | undefined): string => `$${(value || 0).toFixed(4)}`

// Props passed into each virtualized row
interface MessageRowProps {
  row: MessageConversationRow
  enableHitlActions: boolean
  responseParentIds: Set<string>
  submittedMessageIds: Set<string>
  submittingMessageIds: Set<string>
  hitlTextByMessage: Record<string, string>
  hitlSubmitErrors: Record<string, string>
  setHitlTextByMessage: React.Dispatch<React.SetStateAction<Record<string, string>>>
  submitHitlResponse: (message: ChatMessage, action: string, text?: string) => Promise<void>
}

const MemoizedMessageRow = React.memo(function MessageRow({
  row,
  enableHitlActions,
  responseParentIds,
  submittedMessageIds,
  submittingMessageIds,
  hitlTextByMessage,
  hitlSubmitErrors,
  setHitlTextByMessage,
  submitHitlResponse,
}: MessageRowProps) {
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
  const costMetadata = getMessageCostMetadata(message)
  const costSummary = costMetadata?.summary
  const hasCostSummary = hasMeaningfulCostSummary(costSummary)
  const costTotal = typeof costSummary?.total_usd === 'number' ? costSummary.total_usd : undefined
  const showInlineCostBadge = !(
    message.role === 'ASSISTANT' && message.messageType === 'MESSAGE'
  )
  const costBadgeLabel = costMetadata && hasCostSummary && showInlineCostBadge
    ? `${costMetadata.billing_mode === 'reused' ? 'Reused' : 'Spent'} ${formatUsd(costTotal)}`
    : null
  const showMetadataBadges = showMessageTypeBadge || showToolNameBadge || Boolean(costBadgeLabel)

  return (
    <Message
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
                  variant="pill"
                  className={`text-xs px-1.5 py-0 font-normal ${getMessageTypeColor(message.role, message.messageType, message.humanInteraction)}`}
                >
                  {messageTypeLabel}
                </Badge>
              )}
              {showToolNameBadge && (
                <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal bg-neutral text-primary-foreground">
                  {message.toolName}
                </Badge>
              )}
              {costBadgeLabel && (
                <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal bg-info text-primary-foreground">
                  {costBadgeLabel}
                </Badge>
              )}
            </div>
          )}

          {toolViewModel ? (
            <div className="space-y-2">
              <Tool
                defaultOpen={
                  EVALUATION_TOOL_NAMES.has(toolViewModel.toolName) ||
                  toolViewModel.state === 'output-error'
                }
              >
                <ToolHeader
                  toolType={toolViewModel.type}
                  state={toolViewModel.state}
                  toolName={toolViewModel.toolName}
                />
                <ToolContent>
                  {(message.messageType === 'TOOL_CALL' || message.messageType === 'TOOL_RESPONSE') && toolViewModel.input !== undefined && (
                    <ToolInput input={toolViewModel.input} />
                  )}
                  {(message.messageType === 'TOOL_RESPONSE' || (message.messageType === 'TOOL_CALL' && toolViewModel.output !== undefined)) && (
                    EVALUATION_TOOL_NAMES.has(toolViewModel.toolName) && toolViewModel.state !== 'output-error' && toolViewModel.output != null ? (
                      <React.Suspense fallback={
                        <div className="rounded-md bg-card p-3">
                          <div className="h-4 w-40 animate-pulse rounded bg-muted mb-2" />
                          <div className="h-3 w-full animate-pulse rounded bg-muted/80" />
                        </div>
                      }>
                        <EvaluationToolOutput toolOutput={toolViewModel.output} />
                      </React.Suspense>
                    ) : (
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
                    )
                  )}
                </ToolContent>
              </Tool>
              {costMetadata && costSummary && hasCostSummary && (
                <details className="group inline-block w-64 max-w-full rounded-md bg-card/60 text-xs">
                  <summary className="list-none cursor-pointer rounded-md px-3 py-2 text-left text-xs font-medium text-foreground hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center justify-between gap-2">
                      <span>{`${costMetadata.billing_mode === 'reused' ? 'Reused' : 'Spent'} ${formatUsd(costSummary.total_usd)}`}</span>
                      <ChevronDownIcon className="size-4 shrink-0 transition-transform group-open:rotate-180" />
                    </span>
                  </summary>
                  <div className="space-y-1 px-3 pb-3 tabular-nums">
                    <div>Total: {formatUsd(costSummary.total_usd)}</div>
                    <div>LLM calls: {costSummary.llm_calls ?? 0}</div>
                    <div>Tokens: {costSummary.total_tokens ?? 0}</div>
                    {Array.isArray(costSummary.breakdown) && costSummary.breakdown.length > 0 && (
                      <table className="w-full mt-2">
                        <thead className="text-muted-foreground/70">
                          <tr>
                            <th className="text-left font-medium">Model</th>
                            <th className="text-right font-medium">Spent</th>
                            <th className="text-right font-medium">Reused</th>
                            <th className="text-right font-medium">Tokens</th>
                          </tr>
                        </thead>
                        <tbody>
                          {costSummary.breakdown.map((row: any, idx: number) => (
                            <tr key={`${row.provider ?? 'none'}|${row.model ?? 'none'}|${idx}`}>
                              <td className="py-0.5 pr-2">{row.provider || 'unknown'} / {row.model || 'unknown'}</td>
                              <td className="py-0.5 text-right">{formatUsd(Number(row.spent_usd ?? 0))}</td>
                              <td className="py-0.5 text-right">{formatUsd(Number(row.reused_usd ?? 0))}</td>
                              <td className="py-0.5 text-right">{Number(row.total_tokens ?? 0)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </details>
              )}
            </div>
          ) : (
            <div className="text-base space-y-2">
              <CollapsibleText content={message.content} />
              {costMetadata && costSummary && hasCostSummary && (
                <details className="group inline-block w-64 max-w-full rounded-md bg-card/60 text-xs">
                  <summary className="list-none cursor-pointer rounded-md px-3 py-2 text-left text-xs font-medium text-foreground hover:bg-muted/50 [&::-webkit-details-marker]:hidden">
                    <span className="flex items-center justify-between gap-2">
                      <span>{`${costMetadata.billing_mode === 'reused' ? 'Reused' : 'Spent'} ${formatUsd(costSummary.total_usd)}`}</span>
                      <ChevronDownIcon className="size-4 shrink-0 transition-transform group-open:rotate-180" />
                    </span>
                  </summary>
                  <div className="space-y-1 px-3 pb-3 tabular-nums">
                    <div>Total: {formatUsd(costSummary.total_usd)}</div>
                    <div>LLM calls: {costSummary.llm_calls ?? 0}</div>
                    <div>Prompt tokens: {costSummary.prompt_tokens ?? 0}</div>
                    <div>Completion tokens: {costSummary.completion_tokens ?? 0}</div>
                    {Array.isArray(costSummary.breakdown) && costSummary.breakdown.length > 0 && (
                      <table className="w-full mt-2">
                        <thead className="text-muted-foreground/70">
                          <tr>
                            <th className="text-left font-medium">Model</th>
                            <th className="text-right font-medium">Spent</th>
                            <th className="text-right font-medium">Tokens</th>
                          </tr>
                        </thead>
                        <tbody>
                          {costSummary.breakdown.map((row: any, idx: number) => (
                            <tr key={`${row.provider ?? 'none'}|${row.model ?? 'none'}|${idx}`}>
                              <td className="py-0.5 pr-2">{row.provider || 'unknown'} / {row.model || 'unknown'}</td>
                              <td className="py-0.5 text-right">{formatUsd(Number(row.referenced_usd ?? row.spent_usd ?? 0))}</td>
                              <td className="py-0.5 text-right">{Number(row.total_tokens ?? 0)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </details>
              )}
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
                    variant="pill"
                    className="bg-true text-primary-foreground text-xs px-1.5 py-0 font-normal"
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
                  <Badge variant="pill" className="bg-warning text-primary-foreground text-xs px-1.5 py-0 font-normal">Submitting...</Badge>
                )}
              </div>
            </div>
          )}
        </MessageContent>
      </div>
    </Message>
  )
})

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
  const [sessionOverridesById, setSessionOverridesById] = useState<Record<string, Partial<ChatSession>>>({})
  const [internalMessages, setInternalMessages] = useState<ChatMessage[]>([])
  const [internalSelectedSessionId, setInternalSelectedSessionId] = useState<string>()
  const [isLoading, setIsLoading] = useState(false)
  const [isAuthUnavailable, setIsAuthUnavailable] = useState(false)
  const [hitlTextByMessage, setHitlTextByMessage] = useState<Record<string, string>>({})
  const [submittingMessageIds, setSubmittingMessageIds] = useState<Set<string>>(new Set())
  const [submittedMessageIds, setSubmittedMessageIds] = useState<Set<string>>(new Set())
  const [hitlSubmitErrors, setHitlSubmitErrors] = useState<Record<string, string>>({})
  const [promptValue, setPromptValue] = useState("")
  const [selectedModel, setSelectedModel] = useState(DEFAULT_CONSOLE_CHAT_MODEL)
  const [isPromptSubmitting, setIsPromptSubmitting] = useState(false)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [renameSessionValue, setRenameSessionValue] = useState("")
  const [isRenamingSession, setIsRenamingSession] = useState(false)
  const [pendingAssistantBySession, setPendingAssistantBySession] = useState<Record<string, PendingAssistantState>>({})
  const selectedSessionIdRef = React.useRef<string | undefined>(undefined)
  const manualScrollLockRef = React.useRef(false)
  const lastScrollerTopRef = React.useRef<number | null>(null)
  const promptSubmitLockRef = React.useRef(false)
  const virtuosoRef = useRef<VirtuosoHandle>(null)
  const [atBottom, setAtBottom] = useState(true)
  const [autoFollowEnabled, setAutoFollowEnabled] = useState(true)
  const authFailureReportedRef = React.useRef(false)

  const markAuthUnavailable = React.useCallback((error: unknown, source: string): boolean => {
    if (!isUnauthorizedError(error)) {
      return false
    }
    setIsAuthUnavailable(true)
    setIsLoading(false)
    if (!authFailureReportedRef.current) {
      authFailureReportedRef.current = true
      console.warn('[ConsoleChat] GraphQL auth unavailable; suspending live refresh', { source, error })
    }
    return true
  }, [])

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
  const baseSessions = propSessions || internalSessions
  const sessions = React.useMemo(
    () => baseSessions.map((session) => ({
      ...session,
      ...(sessionOverridesById[session.id] || {}),
    })),
    [baseSessions, sessionOverridesById]
  )
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
    setAutoFollowEnabled(true)
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
    if (isAuthUnavailable) {
      return
    }

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

  const getConsoleResponseTarget = React.useCallback(() => (
    process.env.NEXT_PUBLIC_CONSOLE_RESPONSE_TARGET?.trim() || 'cloud'
  ), [])

  const getConsoleSelectedModel = React.useCallback(() => selectedModel, [selectedModel])

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
      const responseTarget = getConsoleResponseTarget()
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
        responseTarget,
        responseStatus: 'PENDING',
        createdAt: respondedAt,
      })
      const responseMessageId = created?.data?.id
      if (!responseMessageId) {
        throw new Error('Failed to persist RESPONSE message')
      }

      markPendingAssistant(
        pendingMessage.sessionId,
        respondedAt,
        responseMessageId,
      )

      toast.success('Response submitted.')

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
          responseTarget,
          responseStatus: 'PENDING',
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
    if (!effectiveId || isAuthUnavailable) return

    const loadConversationData = async () => {
      try {
        setIsLoading(true)
        const client = getClient()
        
        // Load chat sessions for the procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: effectiveId,
          limit: 100,
        })

        const fetchedSessions = Array.isArray(sessionsData) ? sessionsData : []
        const selectedId = selectedSessionIdRef.current?.trim()
        let mergedSessions = fetchedSessions

        // GSI reads can lag behind writes. If the URL points at a freshly created session
        // that's not in the index list yet, fetch by id and inject it.
        if (selectedId && !fetchedSessions.some((session: any) => session?.id === selectedId)) {
          try {
            const selectedSessionResponse = await (client.models.ChatSession.get as any)({ id: selectedId })
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
            metadata: parseSessionMetadata(session.metadata),
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
        if (markAuthUnavailable(error, 'conversation_initial_load')) {
          return
        }
        console.error('Error loading conversation data:', error)
      } finally {
        setIsLoading(false)
      }
    }

    loadConversationData()
  }, [effectiveId, isAuthUnavailable, isExternallyControlledSession, markAuthUnavailable])

  // Real-time subscription for new chat sessions - notification-based pattern
  useEffect(() => {
    if (!effectiveId || isAuthUnavailable) return

    const checkForNewSessions = async () => {
      try {
        const client = getClient()
        
        // Query for sessions in the current procedure
        const { data: sessionsData } = await (client.models.ChatSession.listChatSessionByProcedureIdAndCreatedAt as any)({
          procedureId: effectiveId,
          limit: 100,
        })

        const fetchedSessions = Array.isArray(sessionsData) ? sessionsData : []
        const selectedId = selectedSessionIdRef.current?.trim()
        let mergedSessions = fetchedSessions

        if (selectedId && !fetchedSessions.some((session: any) => session?.id === selectedId)) {
          try {
            const selectedSessionResponse = await (client.models.ChatSession.get as any)({ id: selectedId })
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
            metadata: parseSessionMetadata(session.metadata),
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
                  || JSON.stringify(previous.metadata || {}) !== JSON.stringify(session.metadata || {})
                )
              })

            if (!changed) {
              return prevSessions
            }

            const currentSelectedSessionId = selectedSessionIdRef.current
            const selectedStillExists = currentSelectedSessionId
              ? mergedSessions.some(session => session.id === currentSelectedSessionId)
              : false

            if (!selectedStillExists && !isExternallyControlledSession) {
              if (currentSelectedSessionId) {
                // Preserve a neutral sidebar state when the active session is temporarily
                // unavailable (for example hidden-until-named sessions during refresh lag).
                setInternalSelectedSessionId(undefined)
              } else if (mergedSessions.length > 0) {
                const newestSessionId = mergedSessions[0].id
                setInternalSelectedSessionId(newestSessionId)
              }
            }

            return mergedSessions
          })
        } else {
          setInternalSessions([])
        }
      } catch (error) {
        if (markAuthUnavailable(error, 'session_refresh_poll')) {
          return
        }
        console.error('Error checking for new chat sessions:', error)
      }
    }

    const pollTimer = window.setInterval(checkForNewSessions, 15000)
    checkForNewSessions()

    let createSubscription: { unsubscribe: () => void } | null = null
    let updateSubscription: { unsubscribe: () => void } | null = null

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      createSubscription = getClient().models.ChatSession.onCreate().subscribe({
        next: () => {
          // Don't rely on the subscription data, just use it as a notification
          checkForNewSessions()
        },
        error: (error: Error) => {
          if (markAuthUnavailable(error, 'session_on_create_subscription')) {
            return
          }
          console.error('Chat session create subscription error:', error)
        }
      })
    } catch (error) {
      if (markAuthUnavailable(error, 'session_create_subscription_setup')) {
        return () => {
          window.clearInterval(pollTimer)
        }
      }
      console.error('Error setting up chat session create notification:', error)
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      updateSubscription = getClient().models.ChatSession.onUpdate().subscribe({
        next: () => {
          checkForNewSessions()
        },
        error: (error: Error) => {
          if (markAuthUnavailable(error, 'session_on_update_subscription')) {
            return
          }
          console.error('Chat session update subscription error:', error)
        }
      })
    } catch (error) {
      if (markAuthUnavailable(error, 'session_update_subscription_setup')) {
        return () => {
          window.clearInterval(pollTimer)
        }
      }
      console.error('Error setting up chat session update notification:', error)
    }
    return () => {
      window.clearInterval(pollTimer)
      createSubscription?.unsubscribe()
      updateSubscription?.unsubscribe()
    }
  }, [effectiveId, isAuthUnavailable, isExternallyControlledSession, markAuthUnavailable, onSessionSelect])

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
    if (!effectiveId || isAuthUnavailable) return

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
        if (markAuthUnavailable(error, 'message_refresh_poll')) {
          return
        }
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
      createSubscription = getClient().models.ChatMessage.onCreate().subscribe({
        next: (payload: any) => {
          const incoming = extractSubscriptionMessage(payload)
          if (incoming) {
            applyRealtimeMessageMutation(incoming)
            return
          }
          checkForNewMessages()
        },
        error: (error: Error) => {
          if (markAuthUnavailable(error, 'message_on_create_subscription')) {
            return
          }
          console.error('Chat message create subscription error:', error)
        }
      })
    } catch (error) {
      if (!markAuthUnavailable(error, 'message_create_subscription_setup')) {
        console.error('Error setting up chat message create notification:', error)
      }
    }

    try {
      // @ts-ignore - Amplify Gen2 typing issue with subscriptions
      updateSubscription = getClient().models.ChatMessage.onUpdate().subscribe({
        next: (payload: any) => {
          const incoming = extractSubscriptionMessage(payload)
          if (incoming) {
            applyRealtimeMessageMutation(incoming)
            return
          }
          checkForNewMessages()
        },
        error: (error: Error) => {
          if (markAuthUnavailable(error, 'message_on_update_subscription')) {
            return
          }
          console.error('Chat message update subscription error:', error)
        }
      })
    } catch (error) {
      if (!markAuthUnavailable(error, 'message_update_subscription_setup')) {
        console.error('Error setting up chat message update notification:', error)
      }
    }

    // Initial load + reconciliation on mount.
    checkForNewMessages()

    return () => {
      isCancelled = true
      window.clearInterval(pollTimer)
      createSubscription?.unsubscribe()
      updateSubscription?.unsubscribe()
    }
  }, [applyRealtimeMessageMutation, effectiveId, isAuthUnavailable, markAuthUnavailable])
  
  // Sort sessions by last update date in reverse chronological order (most recent first)
  const sortedSessions = [...sessions].sort((a, b) => {
    const aTime = new Date(a.updatedAt || a.createdAt).getTime()
    const bTime = new Date(b.updatedAt || b.createdAt).getTime()
    return bTime - aTime
  })
  const visibleSessions = sortedSessions.filter((session) => !isHiddenUntilNamedSession(session))

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
  const isPromptDisabled = !selectedSession || isAuthUnavailable
  const conversationRows = sortedMessages.map(getRowFromMessage)
  const renderRows = React.useMemo<ConversationRow[]>(() => {
    if (!showThinkingPlaceholder || !selectedSessionId) {
      return conversationRows
    }
    return [
      ...conversationRows,
      {
        id: `thinking-${selectedSessionId}`,
        from: 'assistant',
        kind: 'thinking',
      },
    ]
  }, [conversationRows, selectedSessionId, showThinkingPlaceholder])
  const hasStreamingAssistantTail = React.useMemo(() => {
    const lastMessage = sortedMessages[sortedMessages.length - 1]
    if (!lastMessage || !isAssistantChatMessage(lastMessage)) {
      return false
    }
    const streamingState = (lastMessage.metadata as { streaming?: { state?: string } } | undefined)?.streaming?.state
    if (!streamingState) {
      return false
    }
    return streamingState !== 'complete'
  }, [sortedMessages])
  const latestConversationRenderSignature = React.useMemo(() => {
    const lastMessage = sortedMessages[sortedMessages.length - 1]
    if (!lastMessage) {
      return `${selectedSessionId || 'none'}:empty:${showThinkingPlaceholder ? 'thinking' : 'idle'}`
    }
    return [
      selectedSessionId || 'none',
      sortedMessages.length,
      lastMessage.id,
      lastMessage.createdAt,
      lastMessage.content.length,
      lastMessage.responseStatus || '',
      showThinkingPlaceholder ? 'thinking' : 'idle',
    ].join(':')
  }, [selectedSessionId, showThinkingPlaceholder, sortedMessages])
  const shouldForceFollow = autoFollowEnabled
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

  const openRenameDialog = React.useCallback(() => {
    if (!selectedSession) {
      return
    }
    setRenameSessionValue((selectedSession.name || "").trim())
    setRenameDialogOpen(true)
  }, [selectedSession])

  const handleRenameSession = React.useCallback(async () => {
    if (!selectedSession || isRenamingSession) {
      return
    }
    const nextName = renameSessionValue.trim()
    if (!nextName) {
      toast.error("Session title cannot be empty")
      return
    }
    setIsRenamingSession(true)
    try {
      const client = getClient()
      const updatedAt = new Date().toISOString()
      const nextMetadata = {
        ...parseSessionMetadata(selectedSession.metadata),
        title_source: "manual",
        console: {
          ...(parseSessionMetadata(selectedSession.metadata).console || {}),
          hidden_until_named: false,
        },
      }
      await (client.models.ChatSession.update as any)({
        id: selectedSession.id,
        name: nextName,
        metadata: serializeSessionMetadata(nextMetadata),
        updatedAt,
      })
      setInternalSessions(prev => prev.map(session => (
        session.id === selectedSession.id
          ? { ...session, name: nextName, metadata: nextMetadata, updatedAt }
          : session
      )))
      setSessionOverridesById(prev => ({
        ...prev,
        [selectedSession.id]: {
          name: nextName,
          metadata: nextMetadata,
          updatedAt,
        },
      }))
      setRenameDialogOpen(false)
      toast.success("Session renamed")
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to rename session"
      toast.error(message)
    } finally {
      setIsRenamingSession(false)
    }
  }, [isRenamingSession, renameSessionValue, selectedSession])

  const handleAtBottomStateChange = React.useCallback((isNowAtBottom: boolean) => {
    setAtBottom(isNowAtBottom)
    if (isNowAtBottom) {
      setAutoFollowEnabled(true)
      manualScrollLockRef.current = false
      lastScrollerTopRef.current = null
      return
    }
    if (manualScrollLockRef.current) {
      setAutoFollowEnabled(false)
    }
  }, [])

  useEffect(() => {
    setAutoFollowEnabled(true)
    setAtBottom(true)
    manualScrollLockRef.current = false
    lastScrollerTopRef.current = null
  }, [selectedSessionId])

  const handleScrollerScroll = React.useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const currentTop = event.currentTarget.scrollTop
    const previousTop = lastScrollerTopRef.current
    if (previousTop !== null && currentTop < previousTop - 1) {
      manualScrollLockRef.current = true
    }
    lastScrollerTopRef.current = currentTop
  }, [])

  const handleScrollerWheel = React.useCallback((event: React.WheelEvent<HTMLDivElement>) => {
    if (event.deltaY < 0) {
      manualScrollLockRef.current = true
    }
  }, [])

  const VirtuosoScroller = React.useMemo(
    () =>
      React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<"div">>(
        function ConversationVirtuosoScroller({ onScroll, onWheel, ...props }, ref) {
          return (
            <div
              ref={ref}
              {...props}
              onScroll={(event) => {
                handleScrollerScroll(event)
                onScroll?.(event)
              }}
              onWheel={(event) => {
                handleScrollerWheel(event)
                onWheel?.(event)
              }}
            />
          )
        }
      ),
    [handleScrollerScroll, handleScrollerWheel]
  )

  useEffect(() => {
    if (!shouldForceFollow) {
      return
    }

    if (!selectedSessionId) {
      return
    }

    if (!latestConversationRenderSignature) {
      return
    }

    const rafId = window.requestAnimationFrame(() => {
      virtuosoRef.current?.scrollToIndex({ index: "LAST", align: "end", behavior: "auto" })
    })

    return () => {
      window.cancelAnimationFrame(rafId)
    }
  }, [latestConversationRenderSignature, selectedSessionId, shouldForceFollow])

  const previousThinkingStateRef = React.useRef(false)
  useEffect(() => {
    const transitionedFromThinkingToMessage = previousThinkingStateRef.current && !showThinkingPlaceholder
    previousThinkingStateRef.current = showThinkingPlaceholder

    if (!transitionedFromThinkingToMessage || !shouldForceFollow || !selectedSessionId) {
      return
    }

    const rafId = window.requestAnimationFrame(() => {
      virtuosoRef.current?.scrollToIndex({ index: "LAST", align: "end", behavior: "auto" })
    })
    return () => {
      window.cancelAnimationFrame(rafId)
    }
  }, [selectedSessionId, shouldForceFollow, showThinkingPlaceholder])

  const createNewSession = React.useCallback(async (options?: { hiddenUntilNamed?: boolean }) => {
    if (!fallbackSessionAccountId || !fallbackSessionProcedureId) {
      throw new Error('Missing account or procedure context to create a session')
    }

    const client = getClient()
    const createdAt = new Date().toISOString()
    const hiddenUntilNamed = Boolean(options?.hiddenUntilNamed)
    const sessionMetadata = hiddenUntilNamed ? { console: { hidden_until_named: true } } : undefined
    const created = await (client.models.ChatSession.create as any)({
      accountId: fallbackSessionAccountId,
      procedureId: fallbackSessionProcedureId,
      category: STANDARD_SESSION_CATEGORY,
      metadata: serializeSessionMetadata(sessionMetadata),
      createdAt,
      updatedAt: createdAt,
    })

    const sessionId = created?.data?.id
    if (!sessionId) {
      throw new Error('Failed to create chat session')
    }

    const createdSession: ChatSession = {
      id: sessionId,
      accountId: fallbackSessionAccountId,
      procedureId: fallbackSessionProcedureId,
      category: created?.data?.category || STANDARD_SESSION_CATEGORY,
      name: created?.data?.name,
      metadata: parseSessionMetadata(created?.data?.metadata || sessionMetadata),
      createdAt: created?.data?.createdAt || createdAt,
      updatedAt: created?.data?.updatedAt || createdAt,
      messageCount: 0,
    }

    setInternalSessions(prev => [createdSession, ...prev.filter(session => session.id !== sessionId)])
    if (hiddenUntilNamed) {
      setSessionOverridesById(prev => ({
        ...prev,
        [sessionId]: {
          metadata: {
            ...parseSessionMetadata(createdSession.metadata),
            console: {
              ...(parseSessionMetadata(createdSession.metadata).console || {}),
              hidden_until_named: true,
            },
          },
        },
      }))
    }
    if (onSessionSelect) {
      onSessionSelect(sessionId)
    } else {
      setInternalSelectedSessionId(sessionId)
    }

    return createdSession
  }, [fallbackSessionAccountId, fallbackSessionProcedureId, onSessionSelect])

  const handleCreateSession = React.useCallback(async () => {
    if (isAuthUnavailable) {
      return
    }
    if (isCreatingSession) {
      return
    }
    if (!canCreateSession) {
      toast.error('Unable to create a session until account and procedure context are available')
      return
    }

    setIsCreatingSession(true)
    try {
      await createNewSession({ hiddenUntilNamed: true })
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
  }, [canCreateSession, createNewSession, isAuthUnavailable, isCreatingSession])

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
            const newSession = await createNewSession({ hiddenUntilNamed: true })
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
            setAutoFollowEnabled(true)
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
        const responseTarget = getConsoleResponseTarget()
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
          responseTarget,
          responseStatus: 'PENDING',
          createdAt: nowIso,
        }

        setIsPromptSubmitting(true)
        setAutoFollowEnabled(true)
        setInternalMessages(prev => [...prev, optimisticMessage])
        setInternalSessions(prev => prev.map(session => (
          session.id === targetSessionId
            ? { ...session, messageCount: (session.messageCount || 0) + 1, updatedAt: nowIso }
            : session
        )))

        let messagePersisted = false
        try {
          const client = getClient()
          const dispatchMessageText = nextValue.length > 4000
            ? `${nextValue.slice(0, 4000)}…`
            : nextValue
          const model = getConsoleSelectedModel()
          const clientHistorySnapshot = buildClientHistorySnapshot(
            messages,
            targetSessionId,
            nextValue,
          )
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
              model: {
                id: model,
              },
              instrumentation: {
                client_send_started_at: clientSendStartedAt,
                client_prompt_length_chars: nextValue.length,
                client_user_message_text: dispatchMessageText,
                client_selected_model: model,
                client_history_snapshot: clientHistorySnapshot,
              },
            }),
            responseTarget,
            responseStatus: 'PENDING',
          })

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

          markPendingAssistant(
            targetSessionId,
            persistedCreatedAt,
            createdMessageId,
          )

          setPromptValue('')
        } catch (error) {
          clearPendingAssistant(targetSessionId)
          const isAuthFailure = markAuthUnavailable(error, 'prompt_submit_dispatch')
          if (!messagePersisted) {
            setInternalMessages(prev => prev.filter(message => message.id !== optimisticMessageId))
            setInternalSessions(prev => prev.map(session => (
              session.id === targetSessionId
                ? { ...session, messageCount: Math.max(0, (session.messageCount || 1) - 1) }
                : session
            )))
          }

          const errorMessage = formatAmplifyError(error) || getErrorMessage(error, 'Failed to send chat message')
          console.error('[ConsoleChat] send/dispatch failure', {
            messagePersisted,
            sessionId: targetSessionId,
            procedureId: targetSessionProcedureId,
            errorMessage,
            error,
          })
          if (!isAuthFailure && messagePersisted) {
            toast.error(`Message saved, but ${getUserFacingDispatchErrorMessage(errorMessage)}`)
          } else if (!isAuthFailure) {
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
      clearPendingAssistant,
      getConsoleResponseTarget,
      getConsoleSelectedModel,
      markAuthUnavailable,
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
        <div data-testid="conversation-sidebar-header" className="h-12 px-3 border-b border-border flex items-center justify-between">
          {!isSidebarCollapsed && (
            <h3 className="text-sm font-medium">Chat Sessions ({visibleSessions.length})</h3>
          )}
          <div className="flex items-center gap-1">
            {!isSidebarCollapsed && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCreateSession}
                className="h-8 w-8 p-0"
                disabled={isAuthUnavailable || !canCreateSession || isCreatingSession}
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
            {visibleSessions.map((session) => (
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
                      {getSessionDisplayName(session)}
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
            {visibleSessions.slice(0, 5).map((session) => (
              <Button
                key={session.id}
                variant={selectedSessionId === session.id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => handleSessionSelect(session.id)}
                className="w-full h-8 p-0"
                title={getSessionDisplayName(session)}
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
          <div data-testid="conversation-main-header" className="h-12 border-b border-border px-3 pt-0.5">
            <div className="flex h-full items-center justify-between">
              <div className="flex min-w-0 items-center gap-2">
                <MessageSquare className="h-4 w-4 text-muted-foreground shrink-0" />
                <div className="min-w-0 flex items-center gap-2">
                  <h3 className="font-medium text-sm truncate">
                    {getSessionHeaderTitle(selectedSession)}
                  </h3>
                  <span className="text-xs text-muted-foreground truncate">
                    {selectedSession.messageCount ? `${selectedSession.messageCount} messages` : 'No messages'}
                  </span>
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
                    onSelect={(event) => {
                      event.preventDefault()
                      openRenameDialog()
                    }}
                  >
                    <Pencil className="mr-2 h-4 w-4" />
                    Rename session
                  </DropdownMenuItem>
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

        <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
          <DialogContent className="sm:max-w-md">
            <DialogHeader>
              <DialogTitle>Rename Session</DialogTitle>
              <DialogDescription>Set a custom title for this chat session.</DialogDescription>
            </DialogHeader>
            <Input
              value={renameSessionValue}
              onChange={(event) => setRenameSessionValue(event.target.value)}
              placeholder="Session title"
              autoFocus
            />
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setRenameDialogOpen(false)}
                disabled={isRenamingSession}
              >
                Cancel
              </Button>
              <Button
                onClick={handleRenameSession}
                disabled={isRenamingSession || !renameSessionValue.trim()}
              >
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        
        {/* Messages List */}
        <div className="min-h-0 flex-1">
          <Conversation className="h-full">
            {isAuthUnavailable ? (
              <ConversationEmptyState
                title="Console unavailable"
                description="GraphQL access is unauthorized in this environment. Check API URL/key and restart dev."
                icon={<AlertCircle className="h-12 w-12 opacity-50" />}
              />
            ) : !selectedSessionId ? (
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
            ) : renderRows.length === 0 ? (
              <ConversationEmptyState
                title="No messages in this session"
                description="Run the console REPL or send a message to start this session."
                icon={<MessageSquare className="h-12 w-12 opacity-50" />}
              />
            ) : (
              <Virtuoso
                ref={virtuosoRef}
                className="h-full"
                data={renderRows}
                followOutput={(isAtBottom) => (shouldForceFollow || isAtBottom ? "auto" : false)}
                initialTopMostItemIndex={Math.max(0, renderRows.length - 1)}
                atBottomStateChange={handleAtBottomStateChange}
                atBottomThreshold={50}
                overscan={600}
                increaseViewportBy={{ top: 400, bottom: 400 }}
                itemContent={(_index, row) => (
                  row.kind === 'thinking' ? (
                    <div className="px-3 py-2 pb-8">
                      <Message
                        from="assistant"
                        data-message-id={row.id}
                        data-from="assistant"
                        className="max-w-full"
                      >
                        <div className="flex items-start">
                          <MessageContent className="max-w-full p-0 sm:max-w-[85%]">
                            <Shimmer className="text-base">Thinking</Shimmer>
                          </MessageContent>
                        </div>
                      </Message>
                    </div>
                  ) : (
                    <div className="px-3 py-2">
                      <MemoizedMessageRow
                        row={row}
                        enableHitlActions={enableHitlActions}
                        responseParentIds={responseParentIds}
                        submittedMessageIds={submittedMessageIds}
                        submittingMessageIds={submittingMessageIds}
                        hitlTextByMessage={hitlTextByMessage}
                        hitlSubmitErrors={hitlSubmitErrors}
                        setHitlTextByMessage={setHitlTextByMessage}
                        submitHitlResponse={submitHitlResponse}
                      />
                    </div>
                  )
                )}
                components={{
                  Scroller: VirtuosoScroller,
                  Footer: () => (!showThinkingPlaceholder ? <div aria-hidden className="h-8" /> : null),
                }}
              />
            )}
            <ConversationScrollButton
              isAtBottom={atBottom}
              virtuosoRef={virtuosoRef}
            />
          </Conversation>
        </div>
        <div className="border-t border-border bg-background px-3 py-3">
          <PromptInput
            className="w-full"
            onSubmit={({ text }) => handlePromptSubmit({ text })}
          >
            <PromptInputBody>
                <PromptInputTextarea
                  value={promptValue}
                  onChange={(event: React.ChangeEvent<HTMLTextAreaElement>) => setPromptValue(event.target.value)}
                  disabled={isPromptDisabled || isPromptSubmitting}
                  placeholder={
                    isAuthUnavailable
                      ? "Console unavailable"
                      : isPromptDisabled
                        ? "Select a session to compose a message"
                        : "Type a message"
                  }
                />
            </PromptInputBody>
            <PromptInputFooter className="justify-between gap-2">
              <PromptInputSelect
                value={selectedModel}
                onValueChange={setSelectedModel}
                disabled={isPromptDisabled || isPromptSubmitting}
              >
                <PromptInputSelectTrigger className="h-8 w-40 text-xs">
                  <PromptInputSelectValue placeholder="Model" />
                </PromptInputSelectTrigger>
                <PromptInputSelectContent>
                  {CONSOLE_CHAT_MODEL_OPTIONS.map((option) => (
                    <PromptInputSelectItem key={option.value} value={option.value}>
                      {option.label}
                    </PromptInputSelectItem>
                  ))}
                </PromptInputSelectContent>
              </PromptInputSelect>
              <PromptInputSubmit disabled={isPromptDisabled || !promptValue.trim() || isPromptSubmitting} />
            </PromptInputFooter>
          </PromptInput>
          {isPromptDisabled && (
            <p className="pt-2 text-xs text-muted-foreground">
              {isAuthUnavailable
                ? "Console is unavailable due to GraphQL authorization failure."
                : selectedSessionMissing
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

"use client"

import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { Button } from "@/components/ui/button"
import {
  MessageSquare,
  User,
  Bot,
  Settings,
  Wrench,
  Terminal,
  Bell,
  Info,
  AlertTriangle,
  AlertCircle,
  XCircle,
  MessageCircleQuestion,
  ThumbsUp,
  CircleCheckBig
} from "lucide-react"

export function CollapsibleText({
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
export const getMessageIcon = (role?: string, messageType?: string, humanInteraction?: string) => {
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
  if (humanInteraction === 'PENDING_INPUT') {
    return <MessageCircleQuestion className="h-4 w-4 text-purple-600" />
  }
  if (humanInteraction === 'PENDING_APPROVAL') {
    return <ThumbsUp className="h-4 w-4 text-green-600" />
  }
  if (humanInteraction === 'PENDING_REVIEW') {
    return <CircleCheckBig className="h-4 w-4 text-blue-600" />
  }
  if (humanInteraction === 'RESPONSE' || humanInteraction === 'TIMED_OUT' || humanInteraction === 'CANCELLED') {
    return <Info className="h-4 w-4 text-gray-600" />
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

export const getMessageTypeColor = (role?: string, messageType?: string, humanInteraction?: string) => {
  // Check humanInteraction first for special message types
  if (humanInteraction === 'NOTIFICATION') return 'bg-blue-100 text-blue-800'
  if (humanInteraction === 'ALERT_INFO') return 'bg-blue-100 text-blue-800'
  if (humanInteraction === 'ALERT_WARNING') return 'bg-yellow-100 text-yellow-800'
  if (humanInteraction === 'ALERT_ERROR') return 'bg-red-100 text-red-800'
  if (humanInteraction === 'ALERT_CRITICAL') return 'bg-red-200 text-red-900'

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

export const getMessageTypeLabel = (role?: string, messageType?: string, humanInteraction?: string) => {
  if (humanInteraction === 'NOTIFICATION') return 'Notification'
  if (humanInteraction === 'ALERT_INFO') return 'Info'
  if (humanInteraction === 'ALERT_WARNING') return 'Warning'
  if (humanInteraction === 'ALERT_ERROR') return 'Error'
  if (humanInteraction === 'ALERT_CRITICAL') return 'Critical'
  if (humanInteraction === 'PENDING_APPROVAL') return 'Pending Approval'
  if (humanInteraction === 'PENDING_INPUT') return 'Pending Input'
  if (humanInteraction === 'PENDING_REVIEW') return 'Pending Review'

  if (messageType === 'TOOL_CALL') return 'Tool Call'
  if (messageType === 'TOOL_RESPONSE') return 'Tool Response'

  if (role === 'SYSTEM') return 'System'
  if (role === 'ASSISTANT') return 'Assistant'
  if (role === 'USER') return 'User'
  if (role === 'TOOL') return 'Tool'

  return messageType || role || 'Message'
}

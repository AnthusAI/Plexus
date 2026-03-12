"use client"

import { ChatFeedView, type ChatMessage } from '@/components/chat-feed'

// Re-export message example data for server components
export { MessageExampleData as MessageExamples } from './message-example-data'

interface MessageExampleProps {
  title?: string
  description?: string
  messages: ChatMessage[]
  className?: string
  height?: string
}

/**
 * MessageExample Component
 *
 * Displays live message examples in documentation using the actual ChatFeedView component.
 * This provides a realistic preview of how messages appear in the real application.
 *
 * Usage in server components:
 * ```tsx
 * import { MessageExample, MessageExamples } from '@/components/documentation/message-examples'
 *
 * <MessageExample
 *   title="Example Title"
 *   messages={MessageExamples.simpleApproval}
 *   height="h-64"
 * />
 * ```
 */
export function MessageExample({
  title,
  description,
  messages,
  className = '',
  height = 'h-96'
}: MessageExampleProps) {
  return (
    <div className={`border rounded-lg overflow-hidden ${className}`}>
      {(title || description) && (
        <div className="bg-muted/50 px-4 py-3 border-b">
          {title && <h4 className="font-medium text-sm mb-1">{title}</h4>}
          {description && <p className="text-xs text-muted-foreground">{description}</p>}
        </div>
      )}
      <div className={height}>
        <ChatFeedView messages={messages} isLoading={false} />
      </div>
    </div>
  )
}

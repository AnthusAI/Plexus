/**
 * YAML Linter Panel Component
 * 
 * Displays linting results in a user-friendly format with clickable links to documentation.
 * Can be integrated with Monaco editor to show inline errors and suggestions.
 */

import React from 'react'
import { OctagonX, ThumbsUp, Info, AlertTriangle, ExternalLink, Lightbulb } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { LintResult, LintMessage } from '@/lib/yaml-linter'

interface YamlLinterPanelProps {
  /** Linting results to display */
  result?: LintResult
  /** Additional CSS class */
  className?: string
  /** Callback when user clicks on a message with line/column info */
  onMessageClick?: (message: LintMessage) => void
  /** Whether to show line numbers in messages */
  showLineNumbers?: boolean
}

export function YamlLinterPanel({
  result,
  className,
  onMessageClick,
  showLineNumbers = true
}: YamlLinterPanelProps) {

  if (!result) {
    return null
  }

  const hasMessages = result.messages.length > 0
  const hasErrors = result.error_count > 0
  const hasWarnings = result.warning_count > 0

  // Determine panel color and icon based on status
  const getPanelVariant = () => {
    if (hasErrors) return 'error'
    if (hasWarnings) return 'warning'
    if (result.is_valid) return 'success'
    return 'info'
  }

  const variant = getPanelVariant()

  const getIcon = () => {
    switch (variant) {
      case 'error':
        return <OctagonX className="h-4 w-4" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4" />
      case 'success':
        return <ThumbsUp className="h-4 w-4" />
      default:
        return <Info className="h-4 w-4" />
    }
  }

  const getVariantClasses = () => {
    return 'text-foreground'
  }

  const getSummaryText = () => {
    // For success cases, show "Validation Successful" as the summary text
    if (result.is_valid && result.messages.length === 1 && result.messages[0].level === 'success') {
      return 'Validation Successful'
    }
    
    if (result.success_message) {
      return result.success_message
    }

    const parts = []
    if (hasErrors) parts.push(`${result.error_count} error${result.error_count !== 1 ? 's' : ''}`)
    if (hasWarnings) parts.push(`${result.warning_count} warning${result.warning_count !== 1 ? 's' : ''}`)
    if (result.info_count > 0) parts.push(`${result.info_count} info`)

    if (parts.length === 0) {
      return 'YAML validation completed'
    }

    return `Found ${parts.join(', ')}`
  }

  const summaryText = getSummaryText()

  return (
    <div className={cn(getVariantClasses(), className)}>
      {/* Simple header - only show if we have summary text */}
      {summaryText && (
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            {getIcon()}
            <span className="text-sm font-medium">
              {summaryText}
            </span>
          </div>
          {hasMessages && (
            <div className="flex gap-1">
              {hasErrors && (
                <Badge variant="destructive" className="h-5 text-xs">
                  {result.error_count}
                </Badge>
              )}
              {hasWarnings && (
                <Badge variant="secondary" className="h-5 text-xs bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300">
                  {result.warning_count}
                </Badge>
              )}
              {result.info_count > 0 && (
                <Badge variant="outline" className="h-5 text-xs">
                  {result.info_count}
                </Badge>
              )}
            </div>
          )}
        </div>
      )}

      {/* Always visible messages */}
      {hasMessages && (
        <div className="space-y-2">
          {result.messages.map((message, index) => {
            // For success cases, show only the description text, not the full message item
            if (message.level === 'success' && result.is_valid && result.messages.length === 1) {
              return (
                <div key={index} className="text-sm text-muted-foreground">
                  {message.message}
                </div>
              )
            }
            
            return (
              <LintMessageItem
                key={index}
                message={message}
                onClick={onMessageClick}
                showLineNumber={showLineNumbers}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}

interface LintMessageItemProps {
  message: LintMessage
  onClick?: (message: LintMessage) => void
  showLineNumber?: boolean
}

function LintMessageItem({ message, onClick, showLineNumber = true }: LintMessageItemProps) {
  const getMessageIcon = () => {
    switch (message.level) {
      case 'error':
        return <OctagonX className="h-4 w-4 text-destructive flex-shrink-0 mt-0.5" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-yellow-500 flex-shrink-0 mt-0.5" />
      case 'success':
        return <ThumbsUp className="h-4 w-4 text-green-500 flex-shrink-0 mt-0.5" />
      default:
        return <Info className="h-4 w-4 text-blue-500 flex-shrink-0 mt-0.5" />
    }
  }

  const getMessageClasses = () => {
    return 'text-foreground'
  }

  const hasLocation = message.line !== undefined && message.line !== null
  const isClickable = hasLocation && onClick

  return (
    <div
      className={cn(
        'flex gap-2 text-xs',
        isClickable && 'cursor-pointer hover:bg-black/5 dark:hover:bg-white/5'
      )}
      onClick={isClickable ? () => onClick(message) : undefined}
    >
      {getMessageIcon()}
      <div className="flex-1 min-w-0">
        <div className="flex items-start gap-2">
          <div className="flex-1">
            <div className={cn('font-medium', getMessageClasses())}>
              {message.title}
              {showLineNumber && hasLocation && (
                <span className="ml-1 text-muted-foreground font-normal">
                  (Line {message.line}{message.column ? `, Col ${message.column}` : ''})
                </span>
              )}
            </div>
            <div className="text-muted-foreground mt-0.5">
              {message.message}
            </div>
            {message.suggestion && (
              <div className="mt-1 text-xs italic text-foreground flex items-center gap-1">
                <Lightbulb className="h-3 w-3" />
                {message.suggestion}
              </div>
            )}
          </div>
          {message.doc_url && (
            <Button
              variant="ghost"
              size="sm"
              className="h-auto p-1 opacity-60 hover:opacity-100"
              asChild
              onClick={(e) => e.stopPropagation()}
            >
              <a
                href={message.doc_url}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="View documentation"
              >
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

export default YamlLinterPanel
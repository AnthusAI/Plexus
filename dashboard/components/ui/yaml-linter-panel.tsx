/**
 * YAML Linter Panel Component
 * 
 * Displays linting results in a user-friendly format with clickable links to documentation.
 * Can be integrated with Monaco editor to show inline errors and suggestions.
 */

import React from 'react'
import { AlertCircle, CheckCircle, Info, AlertTriangle, ExternalLink, ChevronDown, ChevronRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import type { LintResult, LintMessage } from '@/lib/yaml-linter'

interface YamlLinterPanelProps {
  /** Linting results to display */
  result?: LintResult
  /** Whether to show the panel in expanded state by default */
  defaultExpanded?: boolean
  /** Additional CSS class */
  className?: string
  /** Callback when user clicks on a message with line/column info */
  onMessageClick?: (message: LintMessage) => void
  /** Whether to show line numbers in messages */
  showLineNumbers?: boolean
}

export function YamlLinterPanel({
  result,
  defaultExpanded = false,
  className,
  onMessageClick,
  showLineNumbers = true
}: YamlLinterPanelProps) {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded)

  // Auto-expand if there are errors
  React.useEffect(() => {
    if (result && result.error_count > 0) {
      setIsExpanded(true)
    }
  }, [result])

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
        return <AlertCircle className="h-4 w-4" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4" />
      case 'success':
        return <CheckCircle className="h-4 w-4" />
      default:
        return <Info className="h-4 w-4" />
    }
  }

  const getVariantClasses = () => {
    switch (variant) {
      case 'error':
        return 'border-destructive/50 bg-destructive/5 text-destructive'
      case 'warning':
        return 'border-yellow-500/50 bg-yellow-500/5 text-yellow-700 dark:text-yellow-400'
      case 'success':
        return 'border-green-500/50 bg-green-500/5 text-green-700 dark:text-green-400'
      default:
        return 'border-blue-500/50 bg-blue-500/5 text-blue-700 dark:text-blue-400'
    }
  }

  const getSummaryText = () => {
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

  return (
    <div className={cn('border rounded-lg', getVariantClasses(), className)}>
      <Collapsible open={isExpanded} onOpenChange={setIsExpanded}>
        <CollapsibleTrigger asChild>
          <Button
            variant="ghost"
            className="w-full justify-between p-3 h-auto font-normal hover:bg-transparent"
          >
            <div className="flex items-center gap-2">
              {getIcon()}
              <span className="text-sm font-medium">
                {getSummaryText()}
              </span>
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
            {hasMessages && (
              <div className="flex items-center">
                {isExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4" />
                )}
              </div>
            )}
          </Button>
        </CollapsibleTrigger>

        {hasMessages && (
          <CollapsibleContent>
            <div className="px-3 pb-3 space-y-2">
              {result.messages.map((message, index) => (
                <LintMessageItem
                  key={index}
                  message={message}
                  onClick={onMessageClick}
                  showLineNumber={showLineNumbers}
                />
              ))}
            </div>
          </CollapsibleContent>
        )}
      </Collapsible>
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
        return <AlertCircle className="h-3 w-3 text-destructive flex-shrink-0 mt-0.5" />
      case 'warning':
        return <AlertTriangle className="h-3 w-3 text-yellow-500 flex-shrink-0 mt-0.5" />
      case 'success':
        return <CheckCircle className="h-3 w-3 text-green-500 flex-shrink-0 mt-0.5" />
      default:
        return <Info className="h-3 w-3 text-blue-500 flex-shrink-0 mt-0.5" />
    }
  }

  const getMessageClasses = () => {
    switch (message.level) {
      case 'error':
        return 'text-destructive'
      case 'warning':
        return 'text-yellow-700 dark:text-yellow-400'
      case 'success':
        return 'text-green-700 dark:text-green-400'
      default:
        return 'text-blue-700 dark:text-blue-400'
    }
  }

  const hasLocation = message.line !== undefined && message.line !== null
  const isClickable = hasLocation && onClick

  return (
    <div
      className={cn(
        'flex gap-2 p-2 rounded text-xs',
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
              <div className={cn('mt-1 text-xs italic', getMessageClasses())}>
                💡 {message.suggestion}
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
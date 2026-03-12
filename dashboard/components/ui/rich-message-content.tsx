"use client"

import { useState } from 'react'
import { ChevronDown, ChevronUp } from "lucide-react"
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { CollapsibleText } from './message-utils'

/**
 * Collapsible Section
 *
 * A section that can be expanded/collapsed by the user.
 * Available to ALL message types (notifications, alerts, chat, etc.)
 *
 * Visual structure:
 * ```
 * Title (always visible)
 * [Content appears here when expanded]
 * ─────────────────────
 *       ▼ / ▲
 * ```
 */
export interface CollapsibleSection {
  /** Section title, always visible at top */
  title: string

  /** Section content (markdown supported), appears when expanded */
  content: string

  /** Whether section starts expanded (default: false) */
  defaultOpen?: boolean
}

/**
 * Rich Message Metadata
 *
 * Universal metadata format for ALL message types (notifications, alerts, chat, etc.)
 * Supports markdown content and collapsible sections.
 *
 * For interactive messages (PENDING_APPROVAL/INPUT/REVIEW), see InteractiveMessageMetadata
 * which extends this with buttons and input fields.
 *
 * @see message-metadata-spec.md for complete specification
 */
export interface RichMessageMetadata {
  /**
   * Main message content (markdown supported)
   * Always appears at top when present
   */
  content?: string

  /**
   * Collapsible sections with expand/collapse functionality
   * Available to ALL message types
   */
  collapsibleSections?: CollapsibleSection[]
}

interface RichMessageContentProps {
  // Plain content (legacy, from message.content field)
  content?: string

  // Rich metadata (new, from message.metadata field)
  metadata?: RichMessageMetadata

  className?: string
}

/**
 * Rich Message Content Component
 *
 * Renders message content with support for:
 * - Plain markdown content (legacy)
 * - Structured content from metadata (new)
 * - Collapsible sections
 *
 * Used for ALL message types (notifications, alerts, chat, etc.)
 */
export function RichMessageContent({
  content,
  metadata,
  className = ''
}: RichMessageContentProps) {
  const [openSections, setOpenSections] = useState<Record<number, boolean>>(() => {
    const initial: Record<number, boolean> = {}
    metadata?.collapsibleSections?.forEach((section, index) => {
      initial[index] = section.defaultOpen ?? false
    })
    return initial
  })

  const toggleSection = (index: number) => {
    setOpenSections(prev => ({ ...prev, [index]: !prev[index] }))
  }

  // If metadata exists, use structured rendering
  if (metadata) {
    return (
      <div className={`space-y-4 ${className}`}>
        {/* Main Content (from metadata) */}
        {metadata.content && (
          <div className="prose prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {metadata.content}
            </ReactMarkdown>
          </div>
        )}

        {/* Collapsible Sections */}
        {metadata.collapsibleSections && metadata.collapsibleSections.length > 0 && (
          <div className="space-y-3">
            {metadata.collapsibleSections.map((section, index) => (
              <div key={index}>
                {/* Header (always shown at top) */}
                <div className="text-sm font-medium text-foreground mb-2">
                  {section.title}
                </div>

                {/* Expanded content (shown between header and caret when open) */}
                {openSections[index] && (
                  <div className="prose prose-sm max-w-none mb-2">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {section.content}
                    </ReactMarkdown>
                  </div>
                )}

                {/* HR with caret button at bottom */}
                <div className="border-t border-border pt-1">
                  <button
                    type="button"
                    onClick={() => toggleSection(index)}
                    aria-label={openSections[index] ? `Collapse ${section.title}` : `Expand ${section.title}`}
                    className="flex items-center justify-center w-full text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {openSections[index] ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  // Fallback to legacy plain content rendering
  return (
    <CollapsibleText
      content={content || ''}
      maxLines={10}
      enableMarkdown={true}
      className={className}
    />
  )
}

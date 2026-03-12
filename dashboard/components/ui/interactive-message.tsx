"use client"

import { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Spinner } from "@/components/ui/spinner"
import { RichMessageContent, type CollapsibleSection } from './rich-message-content'
import { ArtifactEditor } from './artifact-editor'

/**
 * Message Button
 *
 * Action button for interactive messages (PENDING_APPROVAL/INPUT/REVIEW only)
 */
export interface MessageButton {
  /** Button display text (keep concise, ~20 chars max) */
  label: string

  /** Value returned when button is clicked */
  value: string

  /** Button visual style (default: 'default') */
  variant?: 'default' | 'secondary' | 'destructive' | 'outline' | 'ghost'
}

/**
 * Input Field
 *
 * Form input for collecting user data (PENDING_INPUT messages only)
 */
export interface InputField {
  /** Field name in submitted data object */
  name: string

  /** Field label displayed to user */
  label: string

  /** Optional help text displayed below label */
  description?: string

  /** Input placeholder text (provide examples) */
  placeholder?: string

  /** Input type (default: 'text') */
  type?: 'text' | 'textarea'

  /** Whether field is required (shows asterisk, enforces validation) */
  required?: boolean
}

/**
 * Interactive Message Metadata
 *
 * Extends RichMessageMetadata with buttons and inputs for interactive messages.
 * ONLY used for PENDING_APPROVAL, PENDING_INPUT, and PENDING_REVIEW messages.
 *
 * All other message types use RichMessageMetadata directly.
 *
 * @see RichMessageMetadata for base metadata (content + collapsible sections)
 * @see message-metadata-spec.md for complete specification
 */
export interface InteractiveMessageMetadata {
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

  /**
   * Action buttons for user selection
   * Required for PENDING_APPROVAL/REVIEW, at least 1 button recommended
   */
  buttons?: MessageButton[]

  /**
   * Input fields for collecting user data
   * Required for PENDING_INPUT messages, at least 1 field expected
   */
  inputs?: InputField[]

  /**
   * Artifact to be reviewed (PENDING_REVIEW only)
   * Can be any structured data (JSON object, array, etc.)
   */
  artifact?: any

  /**
   * Type identifier for the artifact (PENDING_REVIEW only)
   * Examples: 'score_promotion', 'document', 'configuration'
   */
  artifact_type?: string
}

interface InteractiveMessageProps {
  metadata: InteractiveMessageMetadata
  onSubmit?: (data: Record<string, any>) => void | Promise<void>
  disabled?: boolean
  className?: string
}

/**
 * Interactive Message Component
 *
 * Handles different interactive message types based on metadata:
 * - Approval messages (buttons only)
 * - Input requests (inputs + buttons)
 * - Review requests (content + buttons)
 */
export function InteractiveMessage({
  metadata,
  onSubmit,
  disabled = false,
  className = ''
}: InteractiveMessageProps) {
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [editedArtifact, setEditedArtifact] = useState<any>(null)

  const handleInputChange = (name: string, value: string) => {
    setFormData(prev => ({ ...prev, [name]: value }))
  }

  const handleButtonClick = async (buttonValue: string) => {
    if (!onSubmit || isSubmitting || disabled) {
      return
    }

    setIsSubmitting(true)
    try {
      // Combine form data with button value and edited artifact
      const submissionData = {
        ...formData,
        action: buttonValue,
        edited_artifact: editedArtifact // Include edited artifact if present
      }
      await onSubmit(submissionData)
    } catch (error) {
      console.error('[InteractiveMessage] Error submitting:', error)
    } finally {
      setIsSubmitting(false)
    }
  }

  const hasInputs = metadata.inputs && metadata.inputs.length > 0
  const hasButtons = metadata.buttons && metadata.buttons.length > 0

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Rich content and collapsible sections */}
      <RichMessageContent
        metadata={{
          content: metadata.content,
          collapsibleSections: metadata.collapsibleSections,
        }}
      />

      {/* Input Fields */}
      {hasInputs && (
        <div className="space-y-4">
          {metadata.inputs!.map((field) => (
            <div key={field.name} className="space-y-2">
              <Label htmlFor={field.name}>
                {field.label}
                {field.required && <span className="text-destructive ml-1">*</span>}
              </Label>
              {field.description && (
                <p className="text-sm text-muted-foreground">{field.description}</p>
              )}
              {field.type === 'textarea' ? (
                <Textarea
                  id={field.name}
                  name={field.name}
                  placeholder={field.placeholder}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  disabled={disabled || isSubmitting}
                  required={field.required}
                  className="min-h-[100px]"
                />
              ) : (
                <Input
                  id={field.name}
                  name={field.name}
                  type="text"
                  placeholder={field.placeholder}
                  value={formData[field.name] || ''}
                  onChange={(e) => handleInputChange(field.name, e.target.value)}
                  disabled={disabled || isSubmitting}
                  required={field.required}
                />
              )}
            </div>
          ))}
        </div>
      )}

      {/* Artifact Editor (for REVIEW messages) */}
      {metadata.artifact && (
        <ArtifactEditor
          artifact={metadata.artifact}
          artifactType={metadata.artifact_type || 'generic'}
          onChange={setEditedArtifact}
          disabled={disabled || isSubmitting}
        />
      )}

      {/* Action Buttons */}
      {hasButtons && (
        <div className="flex gap-2 flex-wrap">
          {isSubmitting && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner size="sm" />
              <span>Submitting response...</span>
            </div>
          )}
          {!isSubmitting && metadata.buttons!.map((button, index) => (
            <Button
              key={`${button.value}-${index}`}
              variant={button.variant || 'default'}
              onClick={() => handleButtonClick(button.value)}
              disabled={disabled || isSubmitting}
            >
              {button.label}
            </Button>
          ))}
        </div>
      )}
    </div>
  )
}

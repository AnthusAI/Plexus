import React from 'react'

export interface BlockProps {
  /** The block's configuration from the markdown */
  config: Record<string, any>
  /** The block's output data from the backend */
  output: Record<string, any>
  /** Optional log messages from the block's execution */
  log?: string
  /** The block's name if specified */
  name?: string
  /** The block's position in the report */
  position: number
  /** Child components */
  children?: React.ReactNode
}

/**
 * Base interface for all report block components.
 * Each block type should implement this interface.
 */
export interface BlockComponent extends React.FC<BlockProps> {
  /** The block class name this component handles */
  blockClass: string
}

export interface BaseBlockProps {
  children: React.ReactNode
  className?: string
}

/**
 * Base component that all block components should extend.
 * Provides common functionality and styling.
 */
export const BaseBlock: React.FC<BaseBlockProps> = ({ children, className = '' }) => {
  return (
    <div className={`border-4 border-dashed border-fuchsia-500 p-4 my-4 ${className}`}>
      <pre className="bg-muted p-2 rounded">
        <code>{children}</code>
      </pre>
    </div>
  )
} 
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
  children?: React.ReactNode
  className?: string
  output?: string | Record<string, any>
  name?: string
  log?: string
}

/**
 * Base component that all block components should extend.
 * Provides common functionality and styling.
 */
export const BaseBlock: React.FC<BaseBlockProps> = ({ 
  children, 
  className = '', 
  output,
  name,
  log
}) => {
  return (
    <div className="border rounded-lg p-4 my-4 w-full min-w-0 max-w-full overflow-hidden">
      {/* Block Header */}
      {name && (
        <div className="font-semibold mb-2">{name}</div>
      )}
      
      {children ? (
        // Render custom content if provided
        children
      ) : (
        // Default content rendering - just show raw output
        <div className="w-full min-w-0 max-w-full">
          {output && (
            <div className="w-full min-w-0 max-w-full overflow-hidden">
              <div className="bg-muted rounded p-2 w-full min-w-0 max-w-full overflow-x-auto">
                <pre className="text-xs whitespace-pre-wrap break-all w-full min-w-0 max-w-full">
                  {JSON.stringify(output, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
} 
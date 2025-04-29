import React from 'react'

/**
 * Props for all report block components
 */
export interface ReportBlockProps {
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
  /** Optional className for styling */
  className?: string
}

/**
 * Interface for block component classes
 * Each specialized block type should implement this interface
 */
export interface BlockComponent extends React.FC<ReportBlockProps> {
  /** The block class name this component handles */
  blockClass: string
}

/**
 * ReportBlock component serves as the default renderer for unknown block types.
 * Renders the internal content, assuming the BlockRenderer provides the outer container.
 */
const ReportBlock: BlockComponent = ({ 
  children, 
  className = '', // className might still be useful for internal styling
  output,
  name,
  log,
  config,
  position
}) => {
  // Return only the inner content structure
  return (
    <>
      {/* Block Header */}
      {name && (
        <div className="font-semibold mb-2">{name}</div>
      )}
      
      {children ? (
        // Render custom content if provided
        children
      ) : (
        // Default content rendering - just show raw output
        <div className={`w-full min-w-0 max-w-full ${className}`}> {/* Apply className here if needed */}
          {output && (
            <div className="w-full min-w-0 max-w-full overflow-hidden">
              <div className="w-full min-w-0 max-w-full overflow-x-auto">
                <pre className="text-xs whitespace-pre-wrap break-all w-full min-w-0 max-w-full">
                  {JSON.stringify(output, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </>
  )
}

// Set the blockClass to indicate this is the default block handler
ReportBlock.blockClass = 'default'

export default ReportBlock 
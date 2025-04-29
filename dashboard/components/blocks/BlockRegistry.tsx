import React from 'react'
import { BlockComponent, BaseBlock } from './BaseBlock'

// Registry of block components
const blockRegistry = new Map<string, BlockComponent>()

/**
 * Register a block component
 */
export function registerBlock(type: string, component: BlockComponent) {
  blockRegistry.set(type, component)
}

/**
 * Get a block component by type
 */
export function getBlock(type: string): BlockComponent | undefined {
  return blockRegistry.get(type)
}

/**
 * Check if a block type is registered
 */
export function hasBlock(type: string): boolean {
  return blockRegistry.has(type)
}

/**
 * Get all registered block types
 */
export function getRegisteredBlockTypes(): string[] {
  return Array.from(blockRegistry.keys())
}

/**
 * Default block renderer for when a specific block component isn't available
 */
const DefaultBlock: React.FC<Omit<BlockRendererProps, 'type'>> = (props) => {
  return (
    <BaseBlock
      output={props.output}
      name={props.name}
      log={props.log}
    />
  )
}

export interface BlockRendererProps {
  type: string
  config: Record<string, any>
  output: Record<string, any>
  log?: string
  name?: string
  position: number
}

/**
 * Block component that renders the appropriate block based on type
 */
export function BlockRenderer(props: BlockRendererProps) {
  const { type, ...blockProps } = props
  const BlockComponent = getBlock(type)

  if (!BlockComponent) {
    console.warn(`No block component registered for type: ${type}`)
    return (
      <div className="border-2 border-red-500 bg-red-50 p-4 rounded-lg w-full min-w-0 max-w-full overflow-hidden">
        <div className="text-red-700 font-semibold">Block Type Not Found: {type}</div>
        <div className="mt-2 w-full min-w-0 max-w-full overflow-hidden">
          <div className="bg-muted rounded p-2 w-full min-w-0 max-w-full overflow-x-auto">
            <pre className="text-xs whitespace-pre-wrap break-all w-full min-w-0 max-w-full">
              {JSON.stringify(blockProps.output, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    )
  }

  // Use DefaultBlock component as a fallback if the BlockComponent isn't properly initialized
  return (
    <div className="w-full min-w-0 max-w-full overflow-hidden">
      {type === 'default' ? (
        <DefaultBlock {...blockProps} />
      ) : (
        <BlockComponent {...blockProps} />
      )}
    </div>
  )
} 
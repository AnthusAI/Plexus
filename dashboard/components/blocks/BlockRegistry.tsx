import React from 'react'
import { BlockComponent } from './BaseBlock'

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
 * Block component that renders the appropriate block based on type
 */
export function BlockRenderer(props: {
  type: string
  config: Record<string, any>
  output: Record<string, any>
  log?: string
  name?: string
  position: number
}) {
  const { type, ...blockProps } = props
  const BlockComponent = getBlock(type)

  if (!BlockComponent) {
    console.warn(`No block component registered for type: ${type}`)
    return (
      <div className="border-2 border-red-500 bg-red-50 p-4 rounded-lg">
        <div className="text-red-700 font-semibold">Block Type Not Found: {type}</div>
        <pre className="mt-2 text-sm text-red-600">
          {JSON.stringify(blockProps, null, 2)}
        </pre>
      </div>
    )
  }

  return (
    <div className="border-2 border-green-500 bg-green-50 p-4 rounded-lg">
      <div className="text-green-700 font-semibold">Block Type: {type}</div>
      <BlockComponent {...blockProps} />
    </div>
  )
} 
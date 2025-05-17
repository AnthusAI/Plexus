import React from 'react'
import ReportBlock, { BlockComponent, ReportBlockProps } from './ReportBlock'

// Registry of block components
const blockRegistry = new Map<string, BlockComponent>()

/**
 * Register a block component
 */
export function registerBlock(type: string, component: BlockComponent) {
  console.log(`Registering block component: ${type}`);
  blockRegistry.set(type, component)
}

/**
 * Get a block component by type
 */
export function getBlock(type: string): BlockComponent | undefined {
  const blockComponent = blockRegistry.get(type);
  console.log(`Getting block component for type: ${type}, Found: ${!!blockComponent}`);
  return blockComponent;
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
 * Props for the BlockRenderer component
 */
export type BlockRendererProps = ReportBlockProps

/**
 * Block component that renders the appropriate block based on type.
 * Only uses a container for the default block type or error states.
 */
export function BlockRenderer(props: BlockRendererProps) {
  const { config, ...blockProps } = props
  const type = blockProps.type || 'default'  // Use type from block data, fallback to default
  let BlockComponent = getBlock(type)
  let componentProps = props; // Store props to potentially modify
  let isDefaultOrError = false;

  if (!BlockComponent) {
    console.warn(`No block component registered for type: ${type}`)
    const DefaultBlock = getBlock('default');
    if (DefaultBlock) {
      BlockComponent = DefaultBlock;
      // Modify props for the default block case
      componentProps = {
        ...props,
        name: `Block Type Not Found: ${type}`, // Set the error message as the name
      };
      isDefaultOrError = true;
    } else {
      // Critical error: Default block not found
      // Keep border here for critical error visibility
      return (
        <div className="rounded-lg bg-background p-4 border my-4 text-destructive font-semibold">
          Critical Error: Default ReportBlock not found and requested block type '{type}' not found.
        </div>
      )
    }
  }
  
  // Check if we're using the default block type
  isDefaultOrError = isDefaultOrError || type === 'default';

  // For default block or error states, use the container
  if (isDefaultOrError) {
    return (
      <div className="rounded-lg bg-background p-4 my-4 w-full min-w-0 max-w-full overflow-hidden border">
        <BlockComponent {...componentProps} /> 
      </div>
    )
  }
  
  // For custom block components, render directly without the container
  return <BlockComponent {...componentProps} />
} 